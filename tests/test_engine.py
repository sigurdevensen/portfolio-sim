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


# ── Stops and market-aware strategies ──────────────────────────────────────

from data.market import MarketData


def _path_prices(path: list[float], ticker: str = "AAA") -> pd.DataFrame:
    idx = pd.date_range("2023-01-02", periods=len(path), freq="B", tz="UTC")
    return pd.DataFrame({ticker: path}, index=idx)


def _cfg0() -> BacktestConfig:
    cfg = _config()
    cfg.execution_lag = 0
    return cfg


class BuyOnceStrategy(Strategy):
    """Long from bar 0 onward (signal stays 1)."""

    name = "buy_once"

    def __init__(self, stop_loss=None, take_profit=None, trailing_stop=None) -> None:
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop = trailing_stop

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(1, index=data.index, columns=data.columns)


def test_stop_loss_exits_at_first_breach_with_reason():
    prices = _path_prices([100, 98, 95, 89, 85, 90])
    result = BacktestEngine(_cfg0()).run(BuyOnceStrategy(stop_loss=0.10), prices)
    sells = result.trades[result.trades["direction"] == -1]
    assert len(sells) == 1
    assert sells["date"].iloc[0] == prices.index[3]      # 89 < 90 = 100 * 0.9
    assert sells["reason"].iloc[0] == "stop_loss"
    assert result.trades["reason"].iloc[0] == "signal"


def test_no_reentry_while_signal_stays_long_after_stop():
    prices = _path_prices([100, 89, 95, 100, 105])
    result = BacktestEngine(_cfg0()).run(BuyOnceStrategy(stop_loss=0.10), prices)
    buys = result.trades[result.trades["direction"] == 1]
    assert len(buys) == 1


def test_take_profit_exits_with_reason():
    prices = _path_prices([100, 105, 112, 120])
    result = BacktestEngine(_cfg0()).run(BuyOnceStrategy(take_profit=0.10), prices)
    sells = result.trades[result.trades["direction"] == -1]
    assert len(sells) == 1
    assert sells["date"].iloc[0] == prices.index[2]
    assert sells["reason"].iloc[0] == "take_profit"


def test_trailing_stop_tracks_peak():
    prices = _path_prices([100, 110, 120, 115, 107, 100])
    result = BacktestEngine(_cfg0()).run(BuyOnceStrategy(trailing_stop=0.10), prices)
    sells = result.trades[result.trades["direction"] == -1]
    assert len(sells) == 1
    assert sells["date"].iloc[0] == prices.index[4]      # 107 < 108 = 120 * 0.9
    assert sells["reason"].iloc[0] == "trailing_stop"


def test_no_stop_without_attributes():
    prices = _path_prices([100, 50, 25])
    result = BacktestEngine(_cfg0()).run(BuyOnceStrategy(), prices)
    assert (result.trades["direction"] == 1).all()


def test_rebalance_trade_has_rebalance_reason():
    cfg = _cfg0()
    result = BacktestEngine(cfg).run(PulseStrategy(), _rebalance_prices())
    reasons = set(result.trades["reason"])
    assert "rebalance" in reasons


class VolumeStrategy(Strategy):
    """Long a ticker only on bars where volume exceeds 1000 — needs MarketData."""

    name = "volume_test"
    requires = {"close", "volume"}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(0, index=data.index, columns=data.columns)

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        sig = pd.DataFrame(-1, index=market.close.index, columns=market.close.columns)
        sig[market.volume > 1000] = 1
        return sig


def test_market_aware_strategy_receives_volume():
    close = _path_prices([100] * 6)
    market = MarketData.from_close(close)
    market.volume.iloc[2] = 5000.0
    result = BacktestEngine(_cfg0()).run(VolumeStrategy(), close, market=market)
    buys = result.trades[result.trades["direction"] == 1]
    assert len(buys) == 1
    assert buys["date"].iloc[0] == close.index[2]


def test_default_market_dispatch_uses_close():
    close = _path_prices([100] * 4)
    market = MarketData.from_close(close)
    result = BacktestEngine(_cfg0()).run(AlwaysBuyStrategy(), close, market=market)
    assert len(result.trades) == 1


# ── active sizing: spread capital across the names actually held ───────────

class TopTwoStrategy(Strategy):
    """Long AAA and BBB from bar 0, never CCC/DDD (a cross-sectional top-N pattern)."""

    name = "top_two"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        sig = pd.DataFrame(-1, index=data.index, columns=data.columns)
        sig[["AAA", "BBB"]] = 1
        return sig


def test_fixed_sizing_leaves_cash_for_unheld_names():
    prices = _prices(5, ["AAA", "BBB", "CCC", "DDD"])
    cfg = _cfg0()
    result = BacktestEngine(cfg).run(TopTwoStrategy(), prices)
    # 1/4 weight each -> 2 names -> half the capital invested
    assert result.trades["value"].sum() == pytest.approx(5_000.0, rel=0.01)


def test_active_sizing_invests_across_held_names():
    prices = _prices(5, ["AAA", "BBB", "CCC", "DDD"])
    cfg = _cfg0()
    cfg.sizing = "active"
    result = BacktestEngine(cfg).run(TopTwoStrategy(), prices)
    # 2 active longs -> 1/2 weight each -> (almost) fully invested
    assert result.trades["value"].sum() == pytest.approx(10_000.0, rel=0.01)
    assert (result.trades["quantity"] == 50.0).all()


def test_active_sizing_respects_max_weight():
    prices = _prices(5, ["AAA", "BBB", "CCC", "DDD"])
    cfg = _cfg0()
    cfg.sizing = "active"
    cfg.max_weight = 0.3
    result = BacktestEngine(cfg).run(TopTwoStrategy(), prices)
    assert result.trades["value"].sum() == pytest.approx(6_000.0, rel=0.01)


def test_active_sizing_rebalances_when_active_set_changes():
    """AAA long from bar 0; BBB joins at bar 2 -> AAA is trimmed to 1/2 on the fresh signal."""
    class JoinStrategy(Strategy):
        name = "join"

        def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
            sig = pd.DataFrame(-1, index=data.index, columns=data.columns)
            sig["AAA"] = 1
            sig.loc[sig.index[2]:, "BBB"] = 1
            return sig

    prices = _prices(6, ["AAA", "BBB"])
    cfg = _cfg0()
    cfg.sizing = "active"
    result = BacktestEngine(cfg).run(JoinStrategy(), prices)
    aaa = result.trades[result.trades["ticker"] == "AAA"]
    assert aaa["quantity"].iloc[0] == 100.0                       # alone: 100% -> 100 shares @100
    trims = aaa[aaa["direction"] == -1]
    assert len(trims) == 1 and trims["reason"].iloc[0] == "rebalance"
    assert trims["quantity"].iloc[0] == 50.0                      # down to 50% weight


def test_invalid_sizing_rejected():
    with pytest.raises(ValueError, match="sizing"):
        BacktestConfig(start="2023-01-01", end="2023-02-01", sizing="magic")


# ── rebalance band ─────────────────────────────────────────────────────────

def test_rebalance_band_skips_small_resizes_on_fresh_signal():
    """Prices drift 5 %; a 25 % band means the fresh long signal does not trigger a resize."""
    idx = pd.date_range("2023-01-02", periods=4, freq="B", tz="UTC")
    prices = pd.DataFrame({"AAA": [100.0, 100.0, 105.0, 105.0], "BBB": [100.0] * 4}, index=idx)
    cfg = _cfg0()
    cfg.rebalance_band = 0.25
    result = BacktestEngine(cfg).run(PulseStrategy(), prices)
    assert len(result.trades) == 2                        # two entries only, no rebalance trades
    cfg.rebalance_band = 0.0
    result2 = BacktestEngine(cfg).run(PulseStrategy(), prices)
    assert len(result2.trades) > 2                        # without a band the resize happens


def test_rebalance_band_still_allows_large_resizes():
    cfg = _cfg0()
    cfg.rebalance_band = 0.10
    result = BacktestEngine(cfg).run(PulseStrategy(), _rebalance_prices())   # AAA doubles -> 26 % overweight
    sells = result.trades[(result.trades["ticker"] == "AAA") & (result.trades["direction"] == -1)]
    assert len(sells) == 1


def test_active_sizing_with_band_reduces_churn():
    rng = np.random.default_rng(0)
    n = 120
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    prices = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0, 0.02, n)) for t in ["AAA", "BBB", "CCC", "DDD"]}, index=idx)

    class Rotating(Strategy):
        name = "rotating"

        def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
            sig = pd.DataFrame(-1, index=data.index, columns=data.columns)
            sig["AAA"] = 1
            sig.loc[sig.index[::3], "BBB"] = 1         # BBB flickers in and out
            return sig

    cfg_no = _cfg0(); cfg_no.sizing = "active"
    cfg_band = _cfg0(); cfg_band.sizing = "active"; cfg_band.rebalance_band = 0.25
    fills_no = len(BacktestEngine(cfg_no).run(Rotating(), prices).trades)
    fills_band = len(BacktestEngine(cfg_band).run(Rotating(), prices).trades)
    assert fills_band < fills_no


def test_negative_band_rejected():
    with pytest.raises(ValueError, match="rebalance_band"):
        BacktestConfig(start="2023-01-01", end="2023-02-01", rebalance_band=-0.1)
