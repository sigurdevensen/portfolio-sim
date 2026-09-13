import math
import pandas as pd
import numpy as np
import pytest
from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.metrics import BacktestResult
from strategies.base import Strategy


def _prices(n_days: int = 50, tickers: list[str] | None = None) -> pd.DataFrame:
    """Synthetic price DataFrame: flat prices, UTC-indexed."""
    if tickers is None:
        tickers = ["AAA"]
    idx = pd.date_range("2023-01-02", periods=n_days, freq="B", tz="UTC")
    data = {t: np.full(n_days, 100.0) for t in tickers}
    return pd.DataFrame(data, index=idx)


class AlwaysBuyStrategy(Strategy):
    name = "always_buy"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(1, index=data.index, columns=data.columns)


class HoldStrategy(Strategy):
    name = "hold"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(0, index=data.index, columns=data.columns)


def _config(start: str = "2023-01-02", end: str = "2023-04-01") -> BacktestConfig:
    return BacktestConfig(
        start=start,
        end=end,
        initial_capital=10_000.0,
        commission=0.0,
        slippage=0.0,
    )


def test_run_returns_backtest_result():
    prices = _prices()
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert isinstance(result, BacktestResult)


def test_nav_series_not_empty():
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert len(result.nav) > 0


def test_hold_strategy_nav_stays_at_initial():
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(HoldStrategy(), prices)
    # no trades — NAV = initial capital throughout
    assert result.nav.iloc[0] == pytest.approx(10_000.0)
    assert result.nav.iloc[-1] == pytest.approx(10_000.0)


def test_buy_signal_generates_trade():
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert not result.trades.empty
    assert "ticker" in result.trades.columns


def test_nav_stays_close_to_initial_on_flat_prices():
    """With flat prices and no commission, NAV should not drift far from initial."""
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    # Allow small rounding from share quantity flooring
    assert abs(result.nav.iloc[-1] - 10_000.0) < 500.0


def test_multi_ticker_both_traded():
    prices = _prices(50, tickers=["AAA", "BBB"])
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    traded_tickers = set(result.trades["ticker"].unique())
    assert "AAA" in traded_tickers
    assert "BBB" in traded_tickers


def test_empty_date_range_raises():
    prices = _prices(50)
    engine = BacktestEngine(BacktestConfig(start="2030-01-01", end="2030-12-31"))
    with pytest.raises(ValueError, match="No price data"):
        engine.run(AlwaysBuyStrategy(), prices)


# ── Execution lag ──────────────────────────────────────────────────────────

def test_default_execution_lag_fills_on_next_bar():
    prices = _prices(10)
    engine = BacktestEngine(_config())  # execution_lag defaults to 1
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert result.trades["date"].iloc[0] == prices.index[1]


def test_zero_execution_lag_fills_on_signal_bar():
    prices = _prices(10)
    cfg = _config()
    cfg.execution_lag = 0
    result = BacktestEngine(cfg).run(AlwaysBuyStrategy(), prices)
    assert result.trades["date"].iloc[0] == prices.index[0]


def test_nav_recorded_for_every_bar_even_with_lag():
    prices = _prices(10)
    result = BacktestEngine(_config()).run(AlwaysBuyStrategy(), prices)
    assert len(result.nav) == 10


# ── Rebalancing ────────────────────────────────────────────────────────────

class PulseStrategy(Strategy):
    """Signal 1 on bars 0 and 2, 0 elsewhere — forces a re-entry signal while held."""

    name = "pulse"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        sig = pd.DataFrame(0, index=data.index, columns=data.columns)
        sig.iloc[0] = 1
        sig.iloc[2] = 1
        return sig


def _rebalance_prices() -> pd.DataFrame:
    idx = pd.date_range("2023-01-02", periods=4, freq="B", tz="UTC")
    return pd.DataFrame({"AAA": [100.0, 100.0, 200.0, 200.0], "BBB": [100.0] * 4}, index=idx)


def test_rebalance_trims_overweight_position():
    cfg = _config()
    cfg.execution_lag = 0
    result = BacktestEngine(cfg).run(PulseStrategy(), _rebalance_prices())
    sells = result.trades[(result.trades["ticker"] == "AAA") & (result.trades["direction"] == -1)]
    assert len(sells) == 1
    # NAV on bar 2 = 50*200 + 50*100 = 15000; target 7500 / 200 = 37 shares -> sell 13
    assert sells["quantity"].iloc[0] == 13.0


def test_rebalance_tops_up_underweight_position():
    cfg = _config()
    cfg.execution_lag = 0
    result = BacktestEngine(cfg).run(PulseStrategy(), _rebalance_prices())
    buys = result.trades[(result.trades["ticker"] == "BBB") & (result.trades["direction"] == 1)]
    assert len(buys) == 2
    assert buys["quantity"].iloc[1] == 25.0  # 7500 / 100 - 50


def test_rebalance_disabled_leaves_positions_alone():
    cfg = _config()
    cfg.execution_lag = 0
    cfg.rebalance = False
    result = BacktestEngine(cfg).run(PulseStrategy(), _rebalance_prices())
    assert len(result.trades) == 2  # only the two initial buys


def test_max_weight_caps_allocation():
    cfg = _config()
    cfg.execution_lag = 0
    cfg.max_weight = 0.25
    result = BacktestEngine(cfg).run(AlwaysBuyStrategy(), _prices(5, ["AAA"]))
    # 10_000 * 0.25 / 100 = 25 shares
    assert result.trades["quantity"].iloc[0] == 25.0


# ── Trade log ──────────────────────────────────────────────────────────────

def test_trade_log_has_value_and_cash_after():
    result = BacktestEngine(_config()).run(AlwaysBuyStrategy(), _prices(5))
    for col in ("value", "cash_after"):
        assert col in result.trades.columns
    row = result.trades.iloc[0]
    assert row["value"] == pytest.approx(row["quantity"] * row["fill_price"])
    assert row["cash_after"] == pytest.approx(10_000.0 - row["value"] - row["commission"])
