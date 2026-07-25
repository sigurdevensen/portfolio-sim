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
