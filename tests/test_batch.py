"""Tests for the batch runner, its serialisation and the batch store."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from data.market import MarketData
from research.batch import BatchConfig, BatchResult, run_batch
from research.library import ALGORITHMS, AlgoSpec, filter_algorithms
from research.report import BatchStore, batch_to_dict


def _market(n: int = 400, tickers=("AAA", "BBB", "CCC"), seed: int = 4) -> MarketData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-04", periods=n, freq="B", tz="UTC")
    close = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n)) for t in tickers}, index=idx)
    m = MarketData.from_close(close)
    m.volume.loc[:, :] = rng.integers(500, 1500, size=close.shape).astype(float)
    return m


SPECS = filter_algorithms(names=[
    "buy_and_hold", "sma_cross_20_50", "rsi_reversal_14_30p0_70p0", "donchian_breakout_55_20_sl10",
    "turn_of_month_1_3", "random_0_0p5_5",
])


def _cfg(**kw) -> BatchConfig:
    base = dict(start="2021-01-04", end="2022-12-31", initial_capital=100_000.0, n_boot=100, pbo_blocks=8)
    base.update(kw)
    return BatchConfig(**base)


def test_selected_specs_exist():
    assert len(SPECS) == 6


def test_run_batch_shapes_and_columns():
    market = _market()
    res = run_batch(SPECS, market, _cfg(), n_jobs=1)
    assert isinstance(res, BatchResult)
    assert res.returns.shape == (len(market.index), 6)
    assert list(res.returns.columns) == [s.name for s in SPECS]
    assert len(res.leaderboard) == 6
    for col in ("family", "data_type", "stop_loss", "params", "n_fills", "sharpe_is", "sharpe_oos", "p_fdr", "dsr", "edge"):
        assert col in res.leaderboard.columns, col
    assert res.summary["n_algorithms"] == 6
    assert res.errors == {}


def test_random_control_and_buy_and_hold_present_in_leaderboard():
    res = run_batch(SPECS, _market(), _cfg(), n_jobs=1)
    assert "random_0_0p5_5" in res.leaderboard.index
    assert res.leaderboard.loc["buy_and_hold", "n_fills"] == 3  # one fill per ticker


def test_failing_spec_is_recorded_not_raised():
    bad = AlgoSpec(name="broken", family="does_not_exist", params={})
    res = run_batch(SPECS[:2] + [bad], _market(), _cfg(), n_jobs=1)
    assert "broken" in res.errors
    assert "Unknown strategy" in res.errors["broken"]
    assert "broken" not in res.leaderboard.index
    assert res.returns.shape[1] == 2


def test_too_few_successful_algorithms_raises():
    bad = AlgoSpec(name="broken", family="does_not_exist", params={})
    with pytest.raises(RuntimeError, match="No algorithm"):
        run_batch([bad], _market(), _cfg(), n_jobs=1)


def test_parallel_matches_serial():
    market = _market()
    a = run_batch(SPECS, market, _cfg(), n_jobs=1)
    b = run_batch(SPECS, market, _cfg(), n_jobs=2)
    pd.testing.assert_frame_equal(a.returns, b.returns)
    assert a.summary["reality_check_p"] == b.summary["reality_check_p"]


def test_batch_to_dict_is_json_safe_with_expected_keys():
    res = run_batch(SPECS, _market(), _cfg(), n_jobs=1)
    d = batch_to_dict(res, meta={"batch_id": "b1", "tickers": ["AAA", "BBB", "CCC"]})
    json.dumps(d)
    for key in ("meta", "summary", "leaderboard", "reality_check_hist", "pbo_logit_hist", "sharpe_hist",
                "navs", "dates", "errors", "families"):
        assert key in d, key
    assert d["meta"]["batch_id"] == "b1"
    assert d["meta"]["n_algorithms"] == 6
    assert len(d["leaderboard"]) == 6
    assert d["leaderboard"][0]["name"]
    assert set(d["navs"]) <= set(res.returns.columns)
    assert len(d["dates"]) == len(res.returns)


def test_batch_store_round_trip(tmp_path):
    store = BatchStore(tmp_path)
    d = {"meta": {"batch_id": "20260913-000000-batch-abc123", "n_algorithms": 3, "created_at": "2026-09-13T00:00:00+00:00"},
         "summary": {"n_strong": 1, "pbo": 0.4, "reality_check_p": 0.03}, "leaderboard": []}
    bid = store.save(d)
    assert (tmp_path / bid / "batch.json").exists()
    assert store.load(bid)["summary"]["pbo"] == 0.4
    listed = store.list()
    assert listed[0]["batch_id"] == bid
    assert listed[0]["summary"]["n_strong"] == 1
    store.delete(bid)
    with pytest.raises(KeyError):
        store.load(bid)
