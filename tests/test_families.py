"""Tests for the strategy family library (technical, volume, cross-sectional, calendar, regime)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.market import MarketData
from strategies import ALL_FAMILIES, Momentum
from strategies.calendar import DayOfWeek, SellInMay, TurnOfMonth
from strategies.cross_sectional import LowVolatility
from strategies.equal_weight import EqualWeight
from strategies.random_control import RandomSignal
from strategies.regime import StreakReversal
from strategies.technical import DonchianBreakout, PriceVsSMA, RSIReversal, SMACross
from strategies.volume import VolumeBreakout


def _market(n: int = 320, tickers=("AAA", "BBB", "CCC", "DDD"), seed: int = 0) -> MarketData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n)) for t in tickers}, index=idx)
    m = MarketData.from_close(close)
    m.volume.loc[:, :] = rng.integers(500, 1500, size=close.shape).astype(float)
    m.synthetic = False
    return m


def _trend(n: int = 300, slope: float = 0.5, ticker: str = "AAA") -> pd.DataFrame:
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    return pd.DataFrame({ticker: 100 + slope * np.arange(n)}, index=idx)


@pytest.mark.parametrize("cls", ALL_FAMILIES, ids=lambda c: c.name)
def test_every_family_emits_valid_aligned_signals(cls):
    market = _market()
    sig = cls().generate_signals_market(market)
    assert sig.shape == market.close.shape
    assert sig.index.equals(market.close.index)
    assert list(sig.columns) == list(market.close.columns)
    assert set(np.unique(sig.to_numpy())).issubset({-1, 0, 1})
    assert not sig.isna().any().any()


@pytest.mark.parametrize("cls", ALL_FAMILIES, ids=lambda c: c.name)
def test_every_family_has_unique_name_and_typed_params(cls):
    import inspect
    assert cls.name and cls.name != "base"
    for pname, p in inspect.signature(cls.__init__).parameters.items():
        if pname == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        assert p.default is not inspect.Parameter.empty, f"{cls.name}.{pname} needs a default"


def test_family_names_are_unique():
    names = [c.name for c in ALL_FAMILIES]
    assert len(names) == len(set(names))


def test_at_least_25_families():
    assert len(ALL_FAMILIES) >= 25


# ── behavioural checks ─────────────────────────────────────────────────────

def test_sma_cross_long_in_steady_uptrend():
    sig = SMACross(fast=10, slow=30).generate_signals(_trend())
    assert (sig["AAA"].iloc[40:] == 1).all()
    assert (sig["AAA"].iloc[:29] == 0).all()   # warm-up


def test_price_vs_sma_exits_in_downtrend():
    sig = PriceVsSMA(window=50).generate_signals(_trend(slope=-0.5))
    assert (sig["AAA"].iloc[60:] == -1).all()


def test_rsi_reversal_enters_after_sharp_selloff():
    idx = pd.date_range("2022-01-03", periods=60, freq="B", tz="UTC")
    path = np.concatenate([np.full(30, 100.0), 100 * np.cumprod(np.full(30, 0.97))])
    sig = RSIReversal(window=14, lower=30, upper=70).generate_signals(pd.DataFrame({"AAA": path}, index=idx))
    assert (sig["AAA"].iloc[31:] == 1).any()


def test_donchian_breakout_fires_on_new_high():
    m = _market(n=120, tickers=("AAA",))
    m.close.iloc[:, :] = 100.0
    m.high.iloc[:, :] = 101.0
    m.low.iloc[:, :] = 99.0
    m.close.iloc[80, 0] = 110.0
    m.high.iloc[80, 0] = 111.0
    sig = DonchianBreakout(entry=20, exit=10).generate_signals_market(m)
    assert sig["AAA"].iloc[80] == 1
    assert sig["AAA"].iloc[79] != 1


def test_volume_breakout_requires_volume_spike():
    m = _market(n=120, tickers=("AAA",))
    m.close.iloc[:, :] = 100.0
    m.close.iloc[80, 0] = 110.0
    m.close.iloc[100, 0] = 115.0
    m.volume.iloc[:, :] = 1000.0
    m.volume.iloc[100, 0] = 5000.0  # only the second breakout has volume
    sig = VolumeBreakout(price_window=20, vol_window=20, vol_mult=1.5).generate_signals_market(m)
    assert sig["AAA"].iloc[80] != 1
    assert sig["AAA"].iloc[100] == 1


def test_turn_of_month_long_on_last_and_first_days():
    m = _market(n=120, tickers=("AAA",))
    sig = TurnOfMonth(days_before=1, days_after=3).generate_signals(m.close)
    idx = m.close.index
    month = idx.month
    last_of_month = np.where(month[:-1] != month[1:])[0]
    i = last_of_month[1]
    assert sig["AAA"].iloc[i] == 1          # last trading day of month
    assert sig["AAA"].iloc[i + 1] == 1      # first of next month
    assert sig["AAA"].iloc[i + 3] == 1      # third
    assert sig["AAA"].iloc[i + 4] == -1     # fourth -> out
    assert sig["AAA"].iloc[i - 8] == -1     # mid-month -> out


def test_day_of_week_parses_days():
    m = _market(n=30, tickers=("AAA",))
    sig = DayOfWeek(long_days="0,1").generate_signals(m.close)
    dow = m.close.index.dayofweek
    assert (sig["AAA"][dow <= 1] == 1).all()
    assert (sig["AAA"][dow > 1] == -1).all()


def test_sell_in_may_out_in_summer():
    m = _market(n=300, tickers=("AAA",))
    sig = SellInMay().generate_signals(m.close)
    months = m.close.index.month
    assert (sig["AAA"][months == 7] == -1).all()
    assert (sig["AAA"][months == 12] == 1).all()


def test_low_volatility_always_holds_constant_ticker():
    m = _market(n=200, tickers=("AAA", "BBB", "CCC"))
    m.close["AAA"] = 100.0
    sig = LowVolatility(window=20, top_n=1).generate_signals(m.close)
    assert (sig["AAA"].iloc[25:] == 1).all()
    assert (sig["BBB"].iloc[25:] == -1).all()


def test_momentum_vectorised_semantics():
    idx = pd.date_range("2022-01-03", periods=40, freq="B", tz="UTC")
    close = pd.DataFrame({
        "UP": 100 + np.arange(40) * 1.0,
        "FLAT": np.full(40, 100.0),
        "DOWN": 100 - np.arange(40) * 0.5,
    }, index=idx)
    sig = Momentum(lookback=10, top_n=2).generate_signals(close)
    assert (sig.iloc[:10] == 0).all().all()
    assert (sig["UP"].iloc[10:] == 1).all()
    assert (sig["FLAT"].iloc[10:] == -1).all()   # zero return is not positive
    assert (sig["DOWN"].iloc[10:] == -1).all()


def test_streak_reversal_enters_after_n_down_days():
    idx = pd.date_range("2022-01-03", periods=12, freq="B", tz="UTC")
    path = [100, 101, 100, 99, 98, 97, 99, 100, 99, 98, 97, 96]
    sig = StreakReversal(down_days=3).generate_signals(pd.DataFrame({"AAA": path}, index=idx))
    assert sig["AAA"].iloc[5] == 1     # third consecutive down day (97)
    assert sig["AAA"].iloc[6] == -1    # first up day exits


def test_random_signal_deterministic_and_seed_dependent():
    m = _market(n=100, tickers=("AAA", "BBB"))
    a = RandomSignal(seed=1).generate_signals(m.close)
    b = RandomSignal(seed=1).generate_signals(m.close)
    c = RandomSignal(seed=2).generate_signals(m.close)
    assert a.equals(b)
    assert not a.equals(c)
    assert set(np.unique(a.to_numpy())) <= {-1, 1}


def test_equal_weight_rebalances_on_last_trading_day_of_period():
    m = _market(n=90, tickers=("AAA",))
    sig = EqualWeight(rebalance_freq="M").generate_signals(m.close)
    month = m.close.index.month
    last = np.where(month[:-1] != month[1:])[0]
    assert (sig["AAA"].iloc[last] == 1).all()
    assert sig["AAA"].iloc[last[0] - 5] == 0
