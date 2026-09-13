"""Tests for macro- and event-driven strategy families (use MarketData.extra / dividends)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.market import MarketData
from strategies import ALL_FAMILIES
from strategies.events import DividendCapture, PostDividendReversal, WeeklyReversal
from strategies.macro import (
    MACRO_FAMILIES,
    CrossAssetAgreement,
    IndexDipBuy,
    MacroBetaRotation,
    MacroLevelRegime,
    MacroTrendFilter,
    RelativeToIndex,
    USLeadLag,
    VIXSpikeReversal,
)


def _market(n: int = 300, tickers=("AAA", "BBB", "CCC"), seed: int = 5) -> MarketData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n)) for t in tickers}, index=idx)
    m = MarketData.from_close(close)
    m.attach_extra("brent", pd.Series(80 * np.cumprod(1 + rng.normal(0, 0.02, n)), index=idx))
    m.attach_extra("spx", pd.Series(4000 * np.cumprod(1 + rng.normal(0.0003, 0.01, n)), index=idx))
    m.attach_extra("vix", pd.Series(np.clip(20 + np.cumsum(rng.normal(0, 1, n)), 10, 60), index=idx))
    m.attach_extra("obx", pd.Series(1000 * np.cumprod(1 + rng.normal(0.0003, 0.01, n)), index=idx))
    m.attach_extra("usdnok", pd.Series(9 + np.cumsum(rng.normal(0, 0.02, n)), index=idx))
    m.dividends = pd.DataFrame(0.0, index=idx, columns=close.columns)
    m.dividends.iloc[100, 0] = 2.0
    m.dividends.iloc[200, 1] = 1.0
    return m


ALL_NEW = MACRO_FAMILIES + [DividendCapture, PostDividendReversal, WeeklyReversal]


@pytest.mark.parametrize("cls", ALL_NEW, ids=lambda c: c.name)
def test_new_families_emit_valid_signals(cls):
    m = _market()
    sig = cls().generate_signals_market(m)
    assert sig.shape == m.close.shape
    assert set(np.unique(sig.to_numpy())).issubset({-1, 0, 1})
    assert not sig.isna().any().any()


@pytest.mark.parametrize("cls", ALL_NEW, ids=lambda c: c.name)
def test_new_families_registered_in_all_families(cls):
    assert cls in ALL_FAMILIES


def test_missing_extra_raises_key_error_naming_series():
    m = MarketData.from_close(_market().close)
    with pytest.raises(KeyError, match="brent"):
        MacroTrendFilter(series="brent").generate_signals_market(m)


def test_macro_trend_filter_follows_series_direction():
    m = _market()
    idx = m.index
    m.attach_extra("brent", pd.Series(np.linspace(50, 150, len(idx)), index=idx))   # steadily rising
    sig = MacroTrendFilter(series="brent", window=20, direction=1).generate_signals_market(m)
    assert (sig.iloc[25:] == 1).all().all()
    sig_inv = MacroTrendFilter(series="brent", window=20, direction=-1).generate_signals_market(m)
    assert (sig_inv.iloc[25:] == -1).all().all()


def test_macro_level_regime_thresholds():
    m = _market()
    m.attach_extra("vix", pd.Series(np.where(np.arange(len(m.index)) < 150, 15.0, 35.0), index=m.index))
    sig = MacroLevelRegime(series="vix", threshold=25.0, below=True).generate_signals_market(m)
    assert (sig.iloc[:150] == 1).all().all()
    assert (sig.iloc[150:] == -1).all().all()


def test_macro_beta_rotation_picks_high_beta_when_series_rising():
    rng = np.random.default_rng(1)
    n = 400
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    oil_ret = rng.normal(0.002, 0.02, n)
    oil = pd.Series(50 * np.cumprod(1 + oil_ret), index=idx)
    high = 100 * np.cumprod(1 + 1.5 * oil_ret + rng.normal(0, 0.002, n))   # beta ~1.5
    low = 100 * np.cumprod(1 + rng.normal(0.0002, 0.01, n))                # beta ~0
    m = MarketData.from_close(pd.DataFrame({"HIGH": high, "LOW": low}, index=idx))
    m.attach_extra("brent", oil)
    sig = MacroBetaRotation(series="brent", beta_window=120, mom_window=60, top_n=1).generate_signals_market(m)
    rising = (oil.pct_change(60) > 0).iloc[200:]
    tail = sig.iloc[200:]
    # oil rising -> hold the high-beta name; oil falling -> hold the low-beta name
    assert (tail["HIGH"][rising] == 1).mean() > 0.9
    assert (tail["LOW"][rising] == -1).mean() > 0.9
    assert (tail["LOW"][~rising] == 1).mean() > 0.9
    assert (tail["HIGH"][~rising] == -1).mean() > 0.9


def test_relative_to_index_long_outperformers():
    m = _market(tickers=("UP", "DOWN"))
    idx = m.index
    m.close["UP"] = np.linspace(100, 200, len(idx))
    m.close["DOWN"] = np.linspace(100, 50, len(idx))
    m.attach_extra("obx", pd.Series(np.linspace(100, 120, len(idx)), index=idx))
    sig = RelativeToIndex(window=20).generate_signals_market(m)
    assert (sig["UP"].iloc[25:] == 1).all()
    assert (sig["DOWN"].iloc[25:] == -1).all()


def test_index_dip_buy_enters_in_drawdown():
    m = _market()
    idx = m.index
    path = np.concatenate([np.linspace(100, 120, 150), np.linspace(120, 100, 50), np.linspace(100, 125, 100)])
    m.attach_extra("obx", pd.Series(path, index=idx))
    sig = IndexDipBuy(drawdown=0.10, window=100, exit_dd=0.01).generate_signals_market(m)
    assert (sig.iloc[180:200] == 1).any().any()      # in the dip
    assert (sig.iloc[260:] == -1).any().any()        # recovered -> exit signal fired


def test_vix_spike_reversal_fires_after_spike():
    m = _market()
    idx = m.index
    vix = np.full(len(idx), 15.0)
    vix[150:156] = [18, 22, 26, 28, 27, 25]   # spike
    m.attach_extra("vix", pd.Series(vix, index=idx))
    sig = VIXSpikeReversal(spike=0.30, window=20).generate_signals_market(m)
    assert (sig.iloc[151:156] == 1).any().any()
    assert (sig.iloc[170:] == -1).any().any()


def test_us_lead_lag_uses_spx_return():
    m = _market()
    idx = m.index
    m.attach_extra("spx", pd.Series(np.where(np.arange(len(idx)) % 2 == 0, 100.0, 101.0), index=idx))
    sig = USLeadLag(lookback=1).generate_signals_market(m)
    # spx up on odd days (100 -> 101), down on even days
    assert (sig.iloc[1::2] == 1).all().all()
    assert (sig.iloc[2::2] == -1).all().all()


def test_cross_asset_agreement_requires_all_positive():
    m = _market()
    idx = m.index
    m.close.loc[:, :] = np.linspace(100, 200, len(idx))[:, None]
    m.attach_extra("brent", pd.Series(np.linspace(100, 200, len(idx)), index=idx))
    m.attach_extra("spx", pd.Series(np.linspace(200, 100, len(idx)), index=idx))   # falling
    sig = CrossAssetAgreement(mom_window=20).generate_signals_market(m)
    assert (sig.iloc[25:] == -1).all().all()


def test_dividend_capture_window_around_ex_date():
    m = _market()
    sig = DividendCapture(days_before=3, days_after=1).generate_signals_market(m)
    assert sig["AAA"].iloc[97] == 1        # enter 3 days before ex-date at 100
    assert sig["AAA"].iloc[101] == -1      # exit 1 day after
    assert sig["AAA"].iloc[50] == 0
    assert (sig["CCC"] == 0).all()         # never pays


def test_post_dividend_reversal_holds_n_days():
    m = _market()
    sig = PostDividendReversal(hold=5).generate_signals_market(m)
    assert sig["AAA"].iloc[100] == 1
    assert sig["AAA"].iloc[105] == -1
    assert sig["BBB"].iloc[200] == 1


def test_weekly_reversal_longs_biggest_losers():
    idx = pd.date_range("2022-01-03", periods=30, freq="B", tz="UTC")
    close = pd.DataFrame({
        "LOSER": np.linspace(100, 70, 30), "FLAT": np.full(30, 100.0), "WINNER": np.linspace(100, 130, 30),
    }, index=idx)
    sig = WeeklyReversal(lookback=5, top_n=1).generate_signals(close)
    assert (sig["LOSER"].iloc[6:] == 1).all()
    assert (sig["WINNER"].iloc[6:] == -1).all()
