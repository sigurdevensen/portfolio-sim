"""Core backtesting engine — drives the simulation loop."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from backtesting.metrics import BacktestResult
from backtesting.portfolio import Portfolio
from execution.fill import FillSimulator
from execution.order import Order

if TYPE_CHECKING:
    from data.market import MarketData
    from strategies.base import Strategy

TRADE_COLUMNS = [
    "date", "ticker", "direction", "quantity", "fill_price", "commission", "value", "cash_after", "reason",
]


@dataclass
class BacktestConfig:
    start: str
    end: str
    initial_capital: float = 100_000.0
    commission: float = 0.001      # fraction, e.g. 0.001 = 0.1%
    slippage: float = 0.0005       # fraction, e.g. 0.0005 = 5 bps
    execution_lag: int = 1         # bars between signal and fill (1 = next close)
    rebalance: bool = True         # resize held positions on a fresh long signal
    max_weight: float | None = None  # cap on per-ticker target weight
    risk_free_rate: float = 0.0    # annualised, used for Sharpe/Sortino
    sizing: str = "fixed"          # "fixed": 1/n_tickers each; "active": 1/n_active_longs each
    rebalance_band: float = 0.0    # skip resizing a held name unless |target/current - 1| exceeds this

    def __post_init__(self) -> None:
        if self.execution_lag < 0:
            raise ValueError("execution_lag must be >= 0")
        if self.max_weight is not None and not (0 < self.max_weight <= 1):
            raise ValueError("max_weight must be in (0, 1]")
        if self.sizing not in ("fixed", "active"):
            raise ValueError("sizing must be 'fixed' or 'active'")
        if self.rebalance_band < 0:
            raise ValueError("rebalance_band must be >= 0")


class BacktestEngine:
    """Runs a strategy against historical price data.

    Signal semantics (per ticker, per bar, after applying ``execution_lag``):

    * ``1`` when previously not ``1``: open a position at the target weight, or,
      if already held and ``rebalance`` is on, resize to the target weight.
    * ``-1`` when previously not ``-1``: close the position.
    * ``0`` or an unchanged signal: do nothing.

    Sizing: ``fixed`` gives every ticker a target weight of ``1 / n_tickers`` (a
    top-5-of-36 strategy is then ~86 % cash). ``active`` gives each held name
    ``1 / n_active`` where ``n_active`` is the number of tickers whose current signal
    is ``1``; when that count changes, held positions are rebalanced to the new
    weight, so cross-sectional strategies stay (near) fully invested.

    Stops (``strategy.stop_loss`` / ``take_profit`` / ``trailing_stop``) are
    evaluated on each bar close before signals and exit the whole position. After a
    stop the position is not re-opened until the signal leaves ``1`` and returns.
    """

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def run(
        self,
        strategy: "Strategy",
        prices: pd.DataFrame,
        benchmark: pd.Series | None = None,
        market: "MarketData | None" = None,
    ) -> BacktestResult:
        """Execute backtest and return a result object.

        Args:
            strategy: A Strategy instance.
            prices: DataFrame with UTC DatetimeIndex, one column per ticker (adjusted close).
            benchmark: Optional benchmark price series for alpha/beta.
            market: Optional OHLCV bundle; when given, signals come from
                ``strategy.generate_signals_market(market)``.
        """
        start = pd.Timestamp(self.config.start, tz="UTC")
        end = pd.Timestamp(self.config.end, tz="UTC")
        prices_in_range = prices.loc[start:end]

        if prices_in_range.empty:
            raise ValueError(f"No price data between {self.config.start} and {self.config.end}")

        if market is not None:
            raw_signals = strategy.generate_signals_market(market.slice(start, end))
        else:
            raw_signals = strategy.generate_signals(prices_in_range)
        signals = self._prepare_signals(raw_signals, prices_in_range)

        portfolio = Portfolio(self.config.initial_capital)
        fill_sim = FillSimulator(slippage=self.config.slippage, commission_rate=self.config.commission)

        tickers = prices_in_range.columns.tolist()
        fixed_weight = 1.0 / len(tickers)
        if self.config.max_weight is not None:
            fixed_weight = min(fixed_weight, self.config.max_weight)
        active = self.config.sizing == "active"
        prev_n_active = 0

        stop_loss = getattr(strategy, "stop_loss", None)
        take_profit = getattr(strategy, "take_profit", None)
        trailing_stop = getattr(strategy, "trailing_stop", None)
        has_stops = any(v is not None for v in (stop_loss, take_profit, trailing_stop))

        prior: dict[str, int] = {t: 0 for t in tickers}
        peak: dict[str, float] = {}
        fills_log: list[dict] = []

        for date in prices_in_range.index:
            prices_today = prices_in_range.loc[date]
            valid_prices = {
                t: float(prices_today[t]) for t in tickers if not pd.isna(prices_today[t])
            }
            if not valid_prices:
                continue

            # ── stops, evaluated on this bar's close ──────────────────────
            if has_stops:
                for ticker, pos in list(portfolio.positions.items()):
                    if ticker not in valid_prices:
                        continue
                    price = valid_prices[ticker]
                    peak[ticker] = max(peak.get(ticker, pos.avg_cost), price)
                    reason = None
                    if stop_loss is not None and price <= pos.avg_cost * (1 - stop_loss):
                        reason = "stop_loss"
                    elif take_profit is not None and price >= pos.avg_cost * (1 + take_profit):
                        reason = "take_profit"
                    elif trailing_stop is not None and price <= peak[ticker] * (1 - trailing_stop):
                        reason = "trailing_stop"
                    if reason:
                        self._sell(portfolio, fill_sim, fills_log, ticker, pos.shares, price, date, reason)
                        peak.pop(ticker, None)

            nav = portfolio.market_value(valid_prices)
            current = signals.loc[date]

            if active:
                n_active = int(sum(1 for t in tickers if t in valid_prices and int(current[t]) == 1))
                weight = 1.0 / n_active if n_active else 0.0
                if self.config.max_weight is not None:
                    weight = min(weight, self.config.max_weight)
                # The active set changed: resize every held name that stays long.
                if self.config.rebalance and n_active != prev_n_active:
                    for ticker, pos in list(portfolio.positions.items()):
                        if ticker not in valid_prices or int(current[ticker]) != 1 or int(prior[ticker]) != 1:
                            continue
                        price = valid_prices[ticker]
                        target_shares = self._target_shares(nav * weight, price, fill_sim)
                        if not self._outside_band(target_shares, pos.shares):
                            continue
                        delta = target_shares - pos.shares
                        if delta < 0:
                            self._sell(portfolio, fill_sim, fills_log, ticker, -delta, price, date, "rebalance")
                        elif delta > 0:
                            self._buy(portfolio, fill_sim, fills_log, ticker, delta, price, date, "rebalance")
                prev_n_active = n_active
            else:
                weight = fixed_weight

            for ticker in tickers:
                if ticker not in valid_prices:
                    continue
                sig = int(current[ticker])
                prev = prior[ticker]
                if sig == prev:
                    continue

                price = valid_prices[ticker]
                held = portfolio.positions.get(ticker)

                if sig == 1:
                    target_shares = self._target_shares(nav * weight, price, fill_sim)
                    if held is None:
                        if target_shares > 0:
                            self._buy(portfolio, fill_sim, fills_log, ticker, target_shares, price, date, "signal")
                            peak[ticker] = price
                    elif self.config.rebalance and self._outside_band(target_shares, held.shares):
                        delta = target_shares - held.shares
                        if delta > 0:
                            self._buy(portfolio, fill_sim, fills_log, ticker, delta, price, date, "rebalance")
                        elif delta < 0:
                            self._sell(portfolio, fill_sim, fills_log, ticker, -delta, price, date, "rebalance")

                elif sig == -1 and held is not None:
                    self._sell(portfolio, fill_sim, fills_log, ticker, held.shares, price, date, "signal")
                    peak.pop(ticker, None)

            portfolio.record_nav(date, valid_prices)
            prior = {t: int(current[t]) for t in tickers}

        trades_df = pd.DataFrame(fills_log, columns=TRADE_COLUMNS)
        return BacktestResult(
            nav=portfolio.nav_series,
            trades=trades_df,
            benchmark=benchmark,
            risk_free_rate=self.config.risk_free_rate,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _prepare_signals(self, raw: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
        """Align signals to the price grid, apply execution lag, coerce to int."""
        sig = raw.reindex(index=prices.index, columns=prices.columns).fillna(0)
        if self.config.execution_lag > 0:
            sig = sig.shift(self.config.execution_lag).fillna(0)
        return sig.astype(int)

    def _outside_band(self, target_shares: float, current_shares: float) -> bool:
        """True when the resize is large enough to be worth the transaction costs."""
        if self.config.rebalance_band <= 0 or current_shares <= 0:
            return True
        return abs(target_shares / current_shares - 1.0) > self.config.rebalance_band

    @staticmethod
    def _target_shares(target_value: float, price: float, fill_sim: FillSimulator) -> float:
        # Include slippage and commission in per-share cost so the cash check never
        # rejects an order that was sized against the raw close.
        cost_per_share = price * (1 + fill_sim.slippage) * (1 + fill_sim.commission_rate)
        return float(math.floor(target_value / cost_per_share))

    @staticmethod
    def _buy(portfolio, fill_sim, log, ticker, shares, price, date, reason) -> None:
        if shares <= 0:
            return
        fill = fill_sim.execute(Order(ticker=ticker, direction=1, quantity=float(shares), timestamp=date), price)
        cost = fill.order.quantity * fill.fill_price * (1 + fill.commission_rate)
        if cost > portfolio.cash:
            # Size down to what cash allows rather than silently skipping.
            affordable = math.floor(portfolio.cash / (fill.fill_price * (1 + fill.commission_rate)))
            if affordable <= 0:
                return
            fill = fill_sim.execute(Order(ticker=ticker, direction=1, quantity=float(affordable), timestamp=date), price)
        portfolio.buy(ticker, fill.order.quantity, fill.fill_price, fill.commission_rate)
        BacktestEngine._log(log, portfolio, fill, date, 1, reason)

    @staticmethod
    def _sell(portfolio, fill_sim, log, ticker, shares, price, date, reason) -> None:
        if shares <= 0:
            return
        fill = fill_sim.execute(Order(ticker=ticker, direction=-1, quantity=float(shares), timestamp=date), price)
        portfolio.sell(ticker, fill.order.quantity, fill.fill_price, fill.commission_rate)
        BacktestEngine._log(log, portfolio, fill, date, -1, reason)

    @staticmethod
    def _log(log: list[dict], portfolio: Portfolio, fill, date: pd.Timestamp, direction: int, reason: str) -> None:
        value = fill.order.quantity * fill.fill_price
        log.append({
            "date": date,
            "ticker": fill.order.ticker,
            "direction": direction,
            "quantity": fill.order.quantity,
            "fill_price": fill.fill_price,
            "commission": value * fill.commission_rate,
            "value": value,
            "cash_after": portfolio.cash,
            "reason": reason,
        })
