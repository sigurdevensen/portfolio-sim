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
    m.meta["sectors"] = {t: ("a" if i % 2 == 0 else "b") for i, t in enumerate(tickers)}
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


# ── round 2: documented anomalies ──────────────────────────────────────────

from strategies.anomalies import ANOMALY_FAMILIES, DividendYieldRank, LongTermReversal, LowBetaRank, RelativeVolRegime


@pytest.mark.parametrize("cls", ANOMALY_FAMILIES, ids=lambda c: c.name)
def test_anomaly_families_emit_valid_signals_and_are_registered(cls):
    m = _market(n=600)
    sig = cls().generate_signals_market(m)
    assert sig.shape == m.close.shape
    assert set(np.unique(sig.to_numpy())).issubset({-1, 0, 1})
    assert cls in ALL_FAMILIES


def test_dividend_yield_rank_prefers_highest_yielder():
    m = _market(n=400)
    m.close.loc[:, :] = 100.0
    m.dividends.loc[:, :] = 0.0
    m.dividends.iloc[50, 0] = 8.0     # AAA yields 8 %
    m.dividends.iloc[50, 1] = 2.0     # BBB yields 2 %
    sig = DividendYieldRank(window=252, top_n=1).generate_signals_market(m)
    assert (sig["AAA"].iloc[260:300] == 1).all()
    assert (sig["BBB"].iloc[260:300] == -1).all()
    assert (sig["CCC"].iloc[260:300] == -1).all()   # non-payer never selected


def test_low_beta_rank_selects_low_beta_name():
    rng = np.random.default_rng(4)
    n = 500
    idx = pd.date_range("2021-01-04", periods=n, freq="B", tz="UTC")
    mkt = rng.normal(0.0003, 0.01, n)
    m = MarketData.from_close(pd.DataFrame({
        "HIGHB": 100 * np.cumprod(1 + 1.6 * mkt + rng.normal(0, 0.003, n)),
        "LOWB": 100 * np.cumprod(1 + 0.2 * mkt + rng.normal(0, 0.003, n)),
    }, index=idx))
    m.attach_extra("obx", pd.Series(1000 * np.cumprod(1 + mkt), index=idx))
    sig = LowBetaRank(window=252, top_n=1).generate_signals_market(m)
    assert (sig["LOWB"].iloc[260:] == 1).all()
    inv = LowBetaRank(window=252, top_n=1, direction=-1).generate_signals_market(m)
    assert (inv["HIGHB"].iloc[260:] == 1).all()


def test_long_term_reversal_longs_multi_year_loser():
    n = 900
    idx = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({"LOSER": np.linspace(100, 40, n), "WINNER": np.linspace(100, 300, n), "FLAT": 100.0}, index=idx)
    sig = LongTermReversal(lookback=756, skip=21, top_n=1).generate_signals(close)
    assert (sig["LOSER"].iloc[760:] == 1).all()
    assert (sig["WINNER"].iloc[760:] == -1).all()


def test_relative_vol_regime_out_when_vol_elevated():
    rng = np.random.default_rng(9)
    n = 700
    idx = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    vol = np.where(np.arange(n) < 600, 0.005, 0.05)
    close = pd.DataFrame({"AAA": 100 * np.cumprod(1 + rng.normal(0, 1, n) * vol)}, index=idx)
    sig = RelativeVolRegime(window=20, ref_window=252).generate_signals(close)
    assert (sig["AAA"].iloc[640:] == -1).all()


# ── round 3: sector and liquidity data ─────────────────────────────────────

from strategies.anomalies import IlliquidityRank, SectorMomentum


def test_sector_momentum_holds_top_sector_members():
    n = 300
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({
        "E1": np.linspace(100, 200, n), "E2": np.linspace(100, 190, n),      # energy: strong
        "F1": np.linspace(100, 90, n), "F2": np.linspace(100, 95, n),        # financials: weak
        "S1": np.linspace(100, 120, n),                                      # seafood: middling
    }, index=idx)
    m = MarketData.from_close(close)
    m.meta["sectors"] = {"E1": "energy", "E2": "energy", "F1": "financials", "F2": "financials", "S1": "seafood"}
    sig = SectorMomentum(lookback=60, top_k=1, skip=5).generate_signals_market(m)
    assert (sig[["E1", "E2"]].iloc[70:] == 1).all().all()
    assert (sig[["F1", "F2", "S1"]].iloc[70:] == -1).all().all()


def test_sector_momentum_requires_sector_map():
    m = _market()
    m.meta.pop("sectors", None)
    with pytest.raises(KeyError, match="sectors"):
        SectorMomentum().generate_signals_market(m)


def test_illiquidity_rank_prefers_thinly_traded_name():
    m = _market(n=400)
    m.volume.loc[:, :] = 1_000_000.0
    m.volume["CCC"] = 1_000.0          # thinly traded
    sig = IlliquidityRank(window=60, top_n=1).generate_signals_market(m)
    assert (sig["CCC"].iloc[70:] == 1).all()
    assert (sig["AAA"].iloc[70:] == -1).all()
