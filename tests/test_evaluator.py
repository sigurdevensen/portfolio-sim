"""Tests for Evaluator — uses synthetic BacktestResult."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.metrics import BacktestResult
from evaluation.evaluator import BacktestReport, Evaluator


def _make_result(n: int = 252, seed: int = 42) -> BacktestResult:
    """Build a synthetic BacktestResult with a plausible NAV series."""
    rng = np.random.default_rng(seed)
    daily_rets = rng.normal(0.0003, 0.01, n)
    nav_values = 100_000.0 * np.cumprod(1 + daily_rets)
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    nav = pd.Series(nav_values, index=idx, name="NAV")
    trades = pd.DataFrame(columns=["date", "ticker", "direction", "quantity", "fill_price", "commission"])
    return BacktestResult(nav=nav, trades=trades)


def test_evaluate_returns_backtest_report():
    result = _make_result()
    report = Evaluator().evaluate(result, strategy_name="test")
    assert isinstance(report, BacktestReport)


def test_report_has_expected_metrics():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert "sharpe" in report.metrics
    assert "cagr" in report.metrics
    assert "max_drawdown" in report.metrics
    assert "total_return" in report.metrics


def test_var_95_is_positive():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.var_95 > 0


def test_var_99_greater_than_var_95():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.var_99 > report.var_95


def test_cvar_greater_than_var():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.cvar_95 >= report.var_95


def test_drawdown_series_nonpositive():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert (report.drawdown_series <= 0).all()


def test_strategy_name_default():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.strategy_name == "strategy"


def test_correlation_matrix_with_prices():
    result = _make_result()
    rng = np.random.default_rng(1)
    idx = result.nav.index
    prices = pd.DataFrame(
        {"EQNR.OL": rng.uniform(80, 120, len(idx)), "DNB.OL": rng.uniform(50, 80, len(idx))},
        index=idx,
    )
    report = Evaluator().evaluate(result, prices=prices)
    assert report.correlation_matrix is not None
    assert report.correlation_matrix.shape == (2, 2)
