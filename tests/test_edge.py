"""Tests for the multiple-testing / overfitting mathematics."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.edge import (
    EdgeReport,
    assess,
    benjamini_hochberg,
    block_stability,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    holm,
    min_track_record_length,
    pbo_cscv,
    reality_check,
)


def _noise(t: int = 1000, n: int = 50, seed: int = 0, sigma: float = 0.01) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, sigma, (t, n))


def _planted(t: int = 1000, n: int = 50, seed: int = 0, mu: float = 0.002) -> np.ndarray:
    r = _noise(t, n, seed)
    r[:, 0] += mu  # strategy 0 has a real edge (~3 annualised Sharpe)
    return r


# ── p-value adjustments ────────────────────────────────────────────────────

def test_benjamini_hochberg_known_values():
    adj = benjamini_hochberg(np.array([0.01, 0.04, 0.03, 0.2]))
    np.testing.assert_allclose(adj, [0.04, 0.05333333, 0.05333333, 0.2], rtol=1e-6)


def test_holm_known_values():
    adj = holm(np.array([0.01, 0.04, 0.03, 0.2]))
    np.testing.assert_allclose(adj, [0.04, 0.09, 0.09, 0.2], rtol=1e-6)


def test_adjusted_p_never_below_raw_and_capped_at_one():
    p = np.random.default_rng(1).uniform(0, 1, 30)
    for fn in (benjamini_hochberg, holm):
        adj = fn(p)
        assert (adj >= p - 1e-12).all()
        assert (adj <= 1.0).all()


# ── deflated Sharpe ────────────────────────────────────────────────────────

def test_expected_max_sharpe_increases_with_trials():
    v = 0.01
    e1, e10, e100, e1000 = (expected_max_sharpe(n, v) for n in (1, 10, 100, 1000))
    assert e1 == 0.0
    assert e10 < e100 < e1000


def test_dsr_of_best_noise_strategy_is_not_significant():
    r = _noise(n=100)
    dsr = deflated_sharpe_ratio(r)
    assert dsr.shape == (100,)
    assert dsr.max() < 0.95


def test_dsr_of_planted_edge_is_significant():
    dsr = deflated_sharpe_ratio(_planted(n=100))
    assert dsr[0] > 0.95


# ── White's reality check ──────────────────────────────────────────────────

def test_reality_check_noise_not_significant():
    rc = reality_check(_noise(n=30), n_boot=300, seed=1)
    assert rc["p_value"] > 0.05
    assert rc["per_strategy_p"].shape == (30,)
    assert 0 <= rc["best_index"] < 30


def test_reality_check_detects_planted_edge():
    rc = reality_check(_planted(n=30), n_boot=300, seed=1)
    assert rc["p_value"] < 0.05
    assert rc["best_index"] == 0
    assert rc["per_strategy_p"][0] < 0.05


# ── probability of backtest overfitting ────────────────────────────────────

def test_pbo_noise_near_one_half():
    res = pbo_cscv(_noise(t=800, n=20, seed=2), n_blocks=10)
    assert 0.3 < res["pbo"] < 0.7
    assert res["n_combinations"] == 252
    assert len(res["logits"]) == 252


def test_pbo_low_when_one_strategy_dominates():
    res = pbo_cscv(_planted(t=800, n=20, seed=2, mu=0.003), n_blocks=10)
    assert res["pbo"] < 0.2


def test_pbo_requires_even_blocks():
    with pytest.raises(ValueError):
        pbo_cscv(_noise(t=200, n=5), n_blocks=7)


# ── stability & MinTRL ─────────────────────────────────────────────────────

def test_block_stability_constant_positive_returns():
    r = np.full((500, 3), 0.001)
    r[:, 2] = -0.001
    st = block_stability(r, k=5)
    assert list(st.columns) == ["stability", "worst_block_sharpe", "best_block_sharpe"]
    assert st["stability"].iloc[0] == 1.0
    assert st["stability"].iloc[2] == 0.0


def test_min_track_record_length_sanity():
    strong = np.random.default_rng(0).normal(0.003, 0.01, 2000)
    weak = np.random.default_rng(0).normal(0.0002, 0.01, 2000)
    assert min_track_record_length(strong) < min_track_record_length(weak)
    assert min_track_record_length(np.random.default_rng(0).normal(-0.001, 0.01, 500)) == np.inf


# ── full assessment ────────────────────────────────────────────────────────

def _frame(r: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=r.shape[0], freq="B", tz="UTC")
    return pd.DataFrame(r, index=idx, columns=[f"algo_{i}" for i in range(r.shape[1])])


def test_assess_returns_leaderboard_with_expected_columns():
    rep = assess(_frame(_planted(n=20)), n_boot=200, seed=0)
    assert isinstance(rep, EdgeReport)
    lb = rep.leaderboard
    for col in ("sharpe_full", "sharpe_is", "sharpe_oos", "cagr_full", "max_drawdown_full", "t_stat",
                "p_value", "p_fdr", "p_holm", "p_rc", "psr", "dsr", "stability", "worst_block_sharpe",
                "min_trl", "n_trades", "edge"):
        assert col in lb.columns, col
    assert len(lb) == 20
    assert set(lb["edge"]) <= {"strong", "candidate", "none"}


def test_assess_ranks_planted_edge_first_and_flags_it_strong():
    n_trades = pd.Series(50, index=[f"algo_{i}" for i in range(20)])
    rep = assess(_frame(_planted(n=20)), n_trades=n_trades, n_boot=200, seed=0)
    assert rep.leaderboard.index[0] == "algo_0"
    assert rep.leaderboard.loc["algo_0", "edge"] == "strong"
    assert (rep.leaderboard["edge"].iloc[1:] != "strong").all()


def test_assess_noise_yields_no_strong_edges_and_flags_batch():
    n_trades = pd.Series(50, index=[f"algo_{i}" for i in range(40)])
    rep = assess(_frame(_noise(n=40, seed=5)), n_trades=n_trades, n_boot=200, seed=0)
    assert (rep.leaderboard["edge"] != "strong").all()
    assert rep.summary["reality_check_p"] > 0.05
    assert rep.summary["best_is_consistent_with_luck"] is True


def test_assess_summary_fields():
    rep = assess(_frame(_planted(n=10)), n_boot=100, seed=0)
    s = rep.summary
    for key in ("n_algorithms", "n_days", "is_days", "oos_days", "expected_max_sharpe", "reality_check_p",
                "pbo", "n_strong", "n_candidate", "is_oos_rank_corr", "best_is_name", "best_is_oos_sharpe"):
        assert key in s, key
    assert s["n_algorithms"] == 10
    assert s["is_days"] + s["oos_days"] == s["n_days"]


def test_assess_requires_minimum_length():
    with pytest.raises(ValueError):
        assess(_frame(_noise(t=40, n=3)))


def test_low_trade_count_blocks_strong_verdict():
    n_trades = pd.Series(5, index=[f"algo_{i}" for i in range(20)])
    rep = assess(_frame(_planted(n=20)), n_trades=n_trades, n_boot=100, seed=0)
    assert rep.leaderboard.loc["algo_0", "edge"] == "none"


# ── benchmark-relative edge (beta is not skill) ────────────────────────────

def _bull_market(t: int = 1000, n: int = 30, seed: int = 11, mu_m: float = 0.001):
    """All strategies share a strongly positive market factor plus zero-mean noise."""
    rng = np.random.default_rng(seed)
    market = rng.normal(mu_m, 0.01, t)
    r = market[:, None] + rng.normal(0.0, 0.003, (t, n))
    return r, market


def _bench_series(market: np.ndarray) -> pd.Series:
    idx = pd.date_range("2020-01-01", periods=len(market), freq="B", tz="UTC")
    return pd.Series(market, index=idx, name="benchmark")


def test_zero_benchmark_matches_no_benchmark():
    r = _planted(n=10)
    a = assess(_frame(r), n_boot=100, seed=0)
    b = assess(_frame(r), benchmark=_bench_series(np.zeros(r.shape[0])), n_boot=100, seed=0)
    pd.testing.assert_series_equal(a.leaderboard["p_fdr"], b.leaderboard["p_fdr"])
    assert a.summary["reality_check_p"] == b.summary["reality_check_p"]


def test_bull_market_beta_is_not_edge_when_benchmarked():
    r, market = _bull_market()
    n_trades = pd.Series(50, index=[f"algo_{i}" for i in range(r.shape[1])])
    naive = assess(_frame(r), n_trades=n_trades, n_boot=200, seed=0)
    benched = assess(_frame(r), benchmark=_bench_series(market), n_trades=n_trades, n_boot=200, seed=0)
    assert naive.summary["n_fdr_5pct"] > 20            # against zero, almost everything "works"
    assert benched.summary["n_strong"] == 0            # against the market, nothing does
    assert benched.summary["reality_check_p"] > 0.05
    assert benched.summary["best_is_consistent_with_luck"] is True


def test_planted_alpha_over_market_is_detected():
    r, market = _bull_market()
    r[:, 0] += 0.002
    n_trades = pd.Series(50, index=[f"algo_{i}" for i in range(r.shape[1])])
    rep = assess(_frame(r), benchmark=_bench_series(market), n_trades=n_trades, n_boot=200, seed=0)
    assert rep.leaderboard.index[0] == "algo_0"
    assert rep.leaderboard.loc["algo_0", "edge"] == "strong"
    assert rep.summary["reality_check_p"] < 0.05


def test_benchmark_columns_and_summary_fields():
    r, market = _bull_market(n=8)
    rep = assess(_frame(r), benchmark=_bench_series(market), n_boot=100, seed=0)
    for col in ("excess_sharpe_full", "excess_sharpe_is", "excess_sharpe_oos", "sharpe_full", "sharpe_oos"):
        assert col in rep.leaderboard.columns, col
    assert "benchmark_sharpe" in rep.summary
    assert rep.summary["benchmark_sharpe"] > 1.0
    # absolute Sharpe stays high while excess Sharpe is near zero
    assert rep.leaderboard["sharpe_full"].mean() > 1.0
    assert abs(rep.leaderboard["excess_sharpe_full"].mean()) < 0.5


def test_pbo_ignores_constant_excess_columns():
    # A column identical to the benchmark has zero excess return everywhere. It must
    # not be allowed to "win" every in-sample split and drive PBO to zero.
    r, market = _bull_market(n=12)
    r[:, 0] = market                      # exact benchmark clone
    rep = assess(_frame(r), benchmark=_bench_series(market), n_boot=100, seed=0)
    assert 0.3 < rep.summary["pbo"] < 0.8
    assert rep.summary["pbo_excluded_constant"] == 1
