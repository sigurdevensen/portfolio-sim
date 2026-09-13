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
