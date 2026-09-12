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
