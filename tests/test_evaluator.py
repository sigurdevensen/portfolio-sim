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


# ── Reporter tests ─────────────────────────────────────────────────────────

from evaluation.reporter import MarkdownReporter


def test_reporter_writes_report_md(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result, strategy_name="momentum")
    reporter = MarkdownReporter()
    md_path = reporter.write(report, output_dir=tmp_path)
    assert md_path.exists()
    assert md_path.name == "report.md"


def test_report_contains_strategy_name(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result, strategy_name="momentum")
    reporter = MarkdownReporter()
    md_path = reporter.write(report, output_dir=tmp_path)
    content = md_path.read_text()
    assert "momentum" in content


def test_report_contains_sharpe_section(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result)
    reporter = MarkdownReporter()
    md_path = reporter.write(report, output_dir=tmp_path)
    content = md_path.read_text()
    assert "Sharpe" in content
    assert "VaR" in content


def test_report_saves_charts(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result)
    reporter = MarkdownReporter()
    reporter.write(report, output_dir=tmp_path)
    assert (tmp_path / "nav_curve.png").exists()
    assert (tmp_path / "drawdown.png").exists()
    assert (tmp_path / "returns_dist.png").exists()


# ── Extended report fields ─────────────────────────────────────────────────

def _make_result_with_trades() -> BacktestResult:
    result = _make_result()
    idx = result.nav.index
    trades = pd.DataFrame([
        {"date": idx[0], "ticker": "AAA", "direction": 1, "quantity": 10.0, "fill_price": 100.0,
         "commission": 1.0, "value": 1000.0, "cash_after": 99_000.0},
        {"date": idx[20], "ticker": "AAA", "direction": -1, "quantity": 10.0, "fill_price": 110.0,
         "commission": 1.1, "value": 1100.0, "cash_after": 100_098.9},
    ])
    return BacktestResult(nav=result.nav, trades=trades)


def test_report_contains_round_trips_and_trade_stats():
    report = Evaluator().evaluate(_make_result_with_trades(), significance=False)
    assert len(report.round_trips) == 1
    assert report.trade_stats["n_trades"] == 1
    assert report.trade_stats["win_rate"] == 1.0


def test_report_significance_present_by_default():
    report = Evaluator().evaluate(_make_result(), n_samples=20)
    assert report.significance is not None
    assert report.significance.n_samples == 20


def test_report_significance_disabled():
    report = Evaluator().evaluate(_make_result(), significance=False)
    assert report.significance is None


def test_report_significance_skipped_for_short_series():
    report = Evaluator().evaluate(_make_result(n=20), n_samples=20)
    assert report.significance is None


def test_monthly_returns_table_shape():
    report = Evaluator().evaluate(_make_result(), significance=False)
    mr = report.monthly_returns
    assert list(mr.columns) == list(range(1, 13))
    assert 2023 in mr.index
    # January 2023 return should equal compounded daily returns in January
    nav = report.result.nav
    jan = nav[nav.index.month == 1]
    expected = jan.iloc[-1] / nav.iloc[0] - 1
    assert mr.loc[2023, 1] == pytest.approx(expected)


def test_benchmark_passed_to_evaluate_adds_beta():
    result = _make_result()
    bench = result.nav * 1.01
    report = Evaluator().evaluate(result, benchmark=bench, significance=False)
    assert "beta" in report.metrics
    assert report.metrics["beta"] == pytest.approx(1.0, abs=1e-6)


def test_report_md_has_trade_statistics_section(tmp_path):
    report = Evaluator().evaluate(_make_result_with_trades(), significance=False)
    content = MarkdownReporter().write(report, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "## Trade Statistics" in content
    assert "Win Rate" in content
    assert "Profit Factor" in content


def test_report_md_has_significance_section(tmp_path):
    report = Evaluator().evaluate(_make_result(), n_samples=20)
    content = MarkdownReporter().write(report, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "## Statistical Significance" in content
    assert "Probabilistic Sharpe Ratio" in content
    assert "95% CI" in content


def test_report_md_omits_significance_when_disabled(tmp_path):
    report = Evaluator().evaluate(_make_result(), significance=False)
    content = MarkdownReporter().write(report, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "## Statistical Significance" not in content


def test_report_md_extended_metrics(tmp_path):
    report = Evaluator().evaluate(_make_result(), significance=False)
    content = MarkdownReporter().write(report, output_dir=tmp_path).read_text(encoding="utf-8")
    assert "Sortino" in content
    assert "Calmar" in content
