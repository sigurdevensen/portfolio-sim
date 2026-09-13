"""Tests for backtesting metrics."""
import numpy as np
import pandas as pd
import pytest

from backtesting.metrics import compute_metrics, _sharpe, _drawdown


def _make_nav(values: list[float]) -> pd.Series:
    dates = pd.date_range("2020-01-01", periods=len(values), freq="B", tz="UTC")
    return pd.Series(values, index=dates, name="NAV")


def test_sharpe_positive_drift():
    returns = pd.Series([0.001] * 252)
    assert _sharpe(returns) > 0


def test_sharpe_zero_std():
    returns = pd.Series([0.0] * 252)
    assert _sharpe(returns) == 0.0


def test_drawdown_flat():
    nav = _make_nav([100.0] * 100)
    max_dd, dd = _drawdown(nav)
    assert max_dd == 0.0


def test_drawdown_decline():
    nav = _make_nav([100, 90, 80, 90, 100])
    max_dd, _ = _drawdown(nav)
    assert max_dd == pytest.approx(-0.2)


def test_compute_metrics_keys():
    nav = _make_nav(list(np.cumprod(1 + np.random.normal(0.0005, 0.01, 500)) * 100))
    metrics = compute_metrics(nav)
    assert "cagr" in metrics
    assert "sharpe" in metrics
    assert "max_drawdown" in metrics
    assert "annualised_volatility" in metrics
    assert "total_return" in metrics


# ── Extended metrics ───────────────────────────────────────────────────────

def _drift_nav(n: int = 500, mu: float = 0.0005, sigma: float = 0.01, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return _make_nav(list(np.cumprod(1 + rng.normal(mu, sigma, n)) * 100))


def test_sortino_positive_for_positive_drift():
    m = compute_metrics(_drift_nav())
    assert m["sortino"] > 0


def test_sortino_exceeds_sharpe_for_positive_drift():
    # Downside deviation excludes upside moves, so denominator is smaller.
    m = compute_metrics(_drift_nav())
    assert m["sortino"] > m["sharpe"]


def test_calmar_is_cagr_over_abs_max_drawdown():
    m = compute_metrics(_drift_nav())
    assert m["calmar"] == pytest.approx(m["cagr"] / abs(m["max_drawdown"]))


def test_calmar_zero_when_no_drawdown():
    nav = _make_nav([100, 101, 102, 103, 104])
    assert compute_metrics(nav)["calmar"] == 0.0


def test_positive_days_pct_in_unit_interval():
    m = compute_metrics(_drift_nav())
    assert 0.0 <= m["positive_days_pct"] <= 1.0


def test_n_days_matches_return_count():
    nav = _drift_nav(n=120)
    assert compute_metrics(nav)["n_days"] == 119


def test_best_and_worst_day_bracket_returns():
    nav = _make_nav([100, 110, 99, 105])
    m = compute_metrics(nav)
    assert m["best_day"] == pytest.approx(0.10)
    assert m["worst_day"] == pytest.approx(99 / 110 - 1)


def test_skew_and_kurtosis_present():
    m = compute_metrics(_drift_nav())
    assert "skew" in m and "kurtosis" in m
    assert np.isfinite(m["skew"]) and np.isfinite(m["kurtosis"])


def test_risk_free_rate_lowers_sharpe():
    nav = _drift_nav()
    assert compute_metrics(nav, risk_free_rate=0.05)["sharpe"] < compute_metrics(nav)["sharpe"]
