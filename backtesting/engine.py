"""Core backtesting engine — drives the simulation loop."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from backtesting.metrics import BacktestResult
from backtesting.portfolio import Portfolio
from execution.fill import FillSimulator
from execution.order import Order

if TYPE_CHECKING:
    from strategies.base import Strategy


@dataclass
class BacktestConfig:
    start: str
    end: str
    initial_capital: float = 100_000.0
    commission: float = 0.001   # fraction, e.g. 0.001 = 0.1%
    slippage: float = 0.0005    # fraction, e.g. 0.0005 = 5 bps


class BacktestEngine:
    """Runs a strategy against historical price data."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def run(self, strategy: "Strategy", prices: pd.DataFrame) -> BacktestResult:
        """Execute backtest and return a result object.

        Args:
            strategy: A Strategy instance with generate_signals().
            prices: DataFrame with UTC DatetimeIndex, one column per ticker (adjusted close).

        Returns:
            BacktestResult with NAV series, trades DataFrame, and computed metrics.
        """
        start = pd.Timestamp(self.config.start, tz="UTC")
        end = pd.Timestamp(self.config.end, tz="UTC")
        prices_in_range = prices.loc[start:end]

        if prices_in_range.empty:
            raise ValueError(f"No price data between {self.config.start} and {self.config.end}")

        signals_df = strategy.generate_signals(prices_in_range)

        portfolio = Portfolio(self.config.initial_capital)
        fill_sim = FillSimulator(
            slippage=self.config.slippage,
            commission_rate=self.config.commission,
        )

        tickers = prices_in_range.columns.tolist()
        n_tickers = len(tickers)
        prior_signals: dict[str, int] = {t: 0 for t in tickers}
        fills_log: list[dict] = []

        for date in prices_in_range.index:
            if date not in signals_df.index:
                continue

            current_signals = signals_df.loc[date]
            prices_today = prices_in_range.loc[date]
            valid_prices = {
                t: float(prices_today[t])
                for t in tickers
                if not pd.isna(prices_today[t])
            }

            if not valid_prices:
                continue

            nav_start = portfolio.market_value(valid_prices)

            for ticker in tickers:
                if ticker not in valid_prices:
                    continue

                sig = int(current_signals.get(ticker, 0))
                prev_sig = prior_signals.get(ticker, 0)

                if sig == prev_sig:
                    continue

                price = valid_prices[ticker]

                if sig == 1 and ticker not in portfolio.positions:
                    target_alloc = nav_start / n_tickers
                    shares = math.floor(target_alloc / price)
                    if shares <= 0:
                        continue
                    order = Order(ticker=ticker, direction=1, quantity=float(shares), timestamp=date)
                    fill = fill_sim.execute(order, price)
                    try:
                        portfolio.buy(ticker, fill.order.quantity, fill.fill_price, fill.commission_rate)
                        fills_log.append({
                            "date": date,
                            "ticker": ticker,
                            "direction": 1,
                            "quantity": fill.order.quantity,
                            "fill_price": fill.fill_price,
                            "commission": fill.order.quantity * fill.fill_price * fill.commission_rate,
                        })
                    except ValueError:
                        pass

                elif sig == -1 and ticker in portfolio.positions:
                    shares = portfolio.positions[ticker].shares
                    order = Order(ticker=ticker, direction=-1, quantity=shares, timestamp=date)
                    fill = fill_sim.execute(order, price)
                    try:
                        portfolio.sell(ticker, fill.order.quantity, fill.fill_price, fill.commission_rate)
                        fills_log.append({
                            "date": date,
                            "ticker": ticker,
                            "direction": -1,
                            "quantity": fill.order.quantity,
                            "fill_price": fill.fill_price,
                            "commission": fill.order.quantity * fill.fill_price * fill.commission_rate,
                        })
                    except ValueError:
                        pass

            portfolio.record_nav(date, valid_prices)
            prior_signals = {t: int(current_signals.get(t, 0)) for t in tickers}

        trades_df = (
            pd.DataFrame(fills_log)
            if fills_log
            else pd.DataFrame(columns=["date", "ticker", "direction", "quantity", "fill_price", "commission"])
        )
        return BacktestResult(nav=portfolio.nav_series, trades=trades_df)
