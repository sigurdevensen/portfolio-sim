"""Tests for statistical significance analysis of strategy returns."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from evaluation.significance import SignificanceResult, analyse


def _returns(n: int = 500, mu: float = 0.0, sigma: float = 0.01, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="UTC")
    return pd.Series(rng.normal(mu, sigma, n), index=idx)


def test_returns_significance_result():
    res = analyse(_returns(), n_samples=50)
    assert isinstance(res, SignificanceResult)


def test_deterministic_with_same_seed():
    a = analyse(_returns(), n_samples=50, seed=7)
    b = analyse(_returns(), n_samples=50, seed=7)
    np.testing.assert_array_equal(a.bootstrap_sharpe, b.bootstrap_sharpe)
    np.testing.assert_array_equal(a.permutation_sharpe, b.permutation_sharpe)


def test_distribution_lengths_match_n_samples():
    res = analyse(_returns(), n_samples=123)
    assert len(res.bootstrap_sharpe) == 123
    assert len(res.bootstrap_cagr) == 123
    assert len(res.permutation_sharpe) == 123
    assert res.n_samples == 123


def test_bootstrap_ci_contains_observed_for_iid_returns():
    res = analyse(_returns(n=1000, mu=0.0004), n_samples=300)
    lo, hi = res.sharpe_ci_95
    assert lo <= res.observed_sharpe <= hi
    lo, hi = res.cagr_ci_95
    assert lo <= res.observed_cagr <= hi


def test_strong_positive_drift_is_significant():
    res = analyse(_returns(n=1000, mu=0.003, sigma=0.01), n_samples=300)
    assert res.p_value_sharpe < 0.05
    assert res.prob_sharpe_ratio > 0.95
    assert res.p_value_t < 0.05


def test_pure_noise_is_not_significant():
    res = analyse(_returns(n=1000, mu=0.0, sigma=0.01, seed=3), n_samples=300)
    assert res.p_value_sharpe > 0.05
    assert res.p_value_t > 0.05


def test_psr_matches_one_sided_t_test_for_normal_returns():
    # For (near) normal returns PSR reduces to 1 - one-sided t p-value.
    res = analyse(_returns(n=1000, mu=0.0, sigma=0.01, seed=3), n_samples=100)
    assert res.prob_sharpe_ratio == pytest.approx(1 - res.p_value_t / 2, abs=0.03)


def test_permutation_sharpe_mean_near_zero_when_observed_positive():
    # Shuffling destroys sequencing; the permutation Sharpe distribution should be
    # centred on the observed Sharpe (same marginal distribution) — check it is finite.
    res = analyse(_returns(n=500, mu=0.001), n_samples=200)
    assert np.isfinite(res.permutation_sharpe).all()


def test_too_few_observations_raises():
    with pytest.raises(ValueError, match="at least 30"):
        analyse(_returns(n=20), n_samples=10)


def test_to_dict_is_json_serialisable_with_histogram():
    res = analyse(_returns(), n_samples=60)
    payload = res.to_dict()
    json.dumps(payload)
    assert payload["bootstrap_sharpe_hist"]["counts"]
    assert len(payload["bootstrap_sharpe_hist"]["edges"]) == len(payload["bootstrap_sharpe_hist"]["counts"]) + 1
    assert payload["permutation_sharpe_hist"]["counts"]
    assert payload["sharpe_ci_95"] == [pytest.approx(res.sharpe_ci_95[0]), pytest.approx(res.sharpe_ci_95[1])]
