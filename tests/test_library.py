"""Tests for the fixed-parameter algorithm library."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine import BacktestConfig, BacktestEngine
from data.market import MarketData
from research.library import ALGORITHMS, AlgoSpec, build_algorithm, families, filter_algorithms
from strategies.base import Strategy


def _market(n: int = 320, tickers=("AAA", "BBB", "CCC"), seed: int = 3) -> MarketData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n)) for t in tickers}, index=idx)
    m = MarketData.from_close(close)
    m.volume.loc[:, :] = rng.integers(500, 1500, size=close.shape).astype(float)
    return m


def test_library_has_at_least_100_algorithms():
    assert len(ALGORITHMS) >= 100


def test_names_unique_and_deterministic():
    names = [a.name for a in ALGORITHMS]
    assert len(names) == len(set(names))
    assert names == sorted(names, key=names.index)  # stable order


def test_specs_are_frozen_dataclasses_with_family_and_params():
    spec = ALGORITHMS[0]
    assert isinstance(spec, AlgoSpec)
    assert spec.family
    assert isinstance(spec.params, dict)


def test_every_spec_builds_a_strategy():
    for spec in ALGORITHMS:
        strat = build_algorithm(spec)
        assert isinstance(strat, Strategy), spec.name
        assert strat.name == spec.family


def test_stop_variants_set_engine_attributes():
    with_sl = [a for a in ALGORITHMS if a.stop_loss is not None]
    with_ts = [a for a in ALGORITHMS if a.trailing_stop is not None]
    assert len(with_sl) >= 10
    assert len(with_ts) >= 5
    strat = build_algorithm(with_sl[0])
    assert strat.stop_loss == with_sl[0].stop_loss


def test_library_contains_random_controls_and_baselines():
    fams = families()
    assert "random" in fams
    assert "buy_and_hold" in fams
    assert sum(1 for a in ALGORITHMS if a.family == "random") >= 5


def test_library_spans_multiple_data_types():
    data_types = {a.data_type for a in ALGORITHMS}
    assert {"price", "ohlc", "volume", "calendar", "cross_sectional"} <= data_types


def test_filter_by_family_and_limit():
    subset = filter_algorithms(families=["sma_cross", "random"], limit=3)
    assert len(subset) == 3
    assert {a.family for a in subset} <= {"sma_cross", "random"}


@pytest.mark.parametrize("spec", ALGORITHMS, ids=lambda s: s.name)
def test_every_algorithm_runs_on_synthetic_market(spec):
    market = _market()
    cfg = BacktestConfig(start="2022-01-03", end="2023-12-31", initial_capital=100_000.0)
    result = BacktestEngine(cfg).run(build_algorithm(spec), market.close, market=market)
    assert len(result.nav) == len(market.index)
    assert np.isfinite(result.nav.to_numpy()).all()


# ── universe-specific additions (Oslo / macro / events) ────────────────────

from research.library import OSLO_ALGORITHMS, library_for


def test_oslo_additions_are_substantial_and_unique():
    assert len(OSLO_ALGORITHMS) >= 45
    names = [a.name for a in OSLO_ALGORITHMS]
    assert len(names) == len(set(names))
    assert not (set(names) & {a.name for a in ALGORITHMS})


def test_oslo_additions_use_macro_and_event_data():
    data_types = {a.data_type for a in OSLO_ALGORITHMS}
    assert {"macro", "events"} <= data_types
    series_used = {a.params.get("series") for a in OSLO_ALGORITHMS if "series" in a.params}
    assert {"brent", "usdnok", "vix", "spx", "obx"} <= series_used


def test_library_for_oslo_is_base_plus_additions():
    lib = library_for("oslo")
    assert len(lib) == len(ALGORITHMS) + len(OSLO_ALGORITHMS)
    assert library_for(None) == ALGORITHMS
    assert library_for("us10") == ALGORITHMS + OSLO_ALGORITHMS  # macro ideas apply to any universe with extras
    assert library_for("oslo_holdout") == ALGORITHMS + OSLO_ALGORITHMS
    assert any(a.family == "illiquidity_rank" for a in filter_algorithms(families=["illiquidity_rank"], universe="oslo_holdout"))


def _market_with_extras(n: int = 320, tickers=("AAA", "BBB", "CCC", "DDD"), seed: int = 8) -> MarketData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.012, n)) for t in tickers}, index=idx)
    m = MarketData.from_close(close)
    m.volume.loc[:, :] = rng.integers(500, 1500, size=close.shape).astype(float)
    for name in ("brent", "wti", "usdnok", "eurnok", "vix", "spx", "us10y", "gold", "copper", "natgas", "obx", "stoxx50"):
        m.attach_extra(name, pd.Series(50 * np.cumprod(1 + rng.normal(0, 0.01, n)), index=idx))
    m.dividends = pd.DataFrame(0.0, index=idx, columns=close.columns)
    m.dividends.iloc[80, 0] = 1.0
    m.dividends.iloc[200, 2] = 2.0
    m.meta["sectors"] = {t: ("a" if i % 2 == 0 else "b") for i, t in enumerate(tickers)}
    return m


@pytest.mark.parametrize("spec", OSLO_ALGORITHMS, ids=lambda s: s.name)
def test_every_oslo_algorithm_runs_with_extras(spec):
    market = _market_with_extras()
    cfg = BacktestConfig(start="2022-01-03", end="2023-12-31", initial_capital=100_000.0)
    result = BacktestEngine(cfg).run(build_algorithm(spec), market.close, market=market)
    assert len(result.nav) == len(market.index)
    assert np.isfinite(result.nav.to_numpy()).all()
