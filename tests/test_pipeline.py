"""End-to-end Pipeline tests using yfinance data source (mocked)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from pipeline.pipeline import Pipeline
from strategies.buy_and_hold import BuyAndHold


def _fake_prices(tickers: list[str], n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n)) for t in tickers},
        index=idx,
    )


@patch("data.loader.yf.download")
def test_pipeline_run_returns_pipeline(mock_dl):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    result = p.run()
    assert result is p  # chainable


@patch("data.loader.yf.download")
def test_pipeline_get_result(mock_dl):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    p.run()
    from backtesting.metrics import BacktestResult
    assert isinstance(p.get_result(), BacktestResult)


@patch("data.loader.yf.download")
def test_pipeline_evaluate_returns_pipeline(mock_dl):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    result = p.run().evaluate()
    assert result is p


@patch("data.loader.yf.download")
def test_pipeline_report_writes_files(mock_dl, tmp_path):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    p.run().evaluate().report(output=tmp_path)
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "nav_curve.png").exists()


def test_pipeline_run_before_evaluate_raises():
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
    )
    with pytest.raises(RuntimeError, match="run\\(\\)"):
        p.evaluate()


def test_pipeline_evaluate_before_report_raises():
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
    )
    with pytest.raises(RuntimeError, match="evaluate\\(\\)"):
        p.report()


# ── Platform upgrades ──────────────────────────────────────────────────────

def _fake_fetch(tickers, start, end, use_cache=True):
    rng = np.random.default_rng(len(tickers))
    idx = pd.date_range("2023-01-02", periods=60, freq="B", tz="UTC")
    return pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 60)) for t in tickers}, index=idx)


def _pipeline(**kw):
    args = dict(strategy=BuyAndHold(), tickers=["AAPL"], start="2023-01-02", end="2023-04-01",
                data_source="yfinance", initial_capital=10_000.0, n_samples=10)
    args.update(kw)
    return Pipeline(**args)


@patch("pipeline.pipeline.fetch_prices", side_effect=_fake_fetch)
def test_benchmark_ticker_is_fetched_and_beta_computed(mock_fetch):
    p = _pipeline(benchmark="SPY").run().evaluate()
    fetched = [call.args[0] for call in mock_fetch.call_args_list]
    assert ["SPY"] in fetched
    assert "beta" in p.get_report().metrics
    assert p.get_result().benchmark is not None


@patch("pipeline.pipeline.fetch_prices", side_effect=_fake_fetch)
def test_execution_lag_and_rebalance_forwarded(mock_fetch):
    p = _pipeline(execution_lag=0, rebalance=False).run()
    assert p.get_result().trades["date"].iloc[0] == p._prices.index[0]
    assert p.engine_config.execution_lag == 0
    assert p.engine_config.rebalance is False


@patch("pipeline.pipeline.fetch_prices", side_effect=_fake_fetch)
def test_to_dict_is_json_serialisable_with_meta(mock_fetch):
    import json
    p = _pipeline().run().evaluate()
    d = p.to_dict()
    json.dumps(d)
    assert d["meta"]["strategy"] == "buy_and_hold"
    assert d["meta"]["tickers"] == ["AAPL"]
    assert d["meta"]["config"]["initial_capital"] == 10_000.0
    assert d["meta"]["run_id"]


@patch("pipeline.pipeline.fetch_prices", side_effect=_fake_fetch)
def test_report_writes_html_and_json(mock_fetch, tmp_path):
    _pipeline().run().evaluate().report(output=tmp_path)
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "run.json").exists()


@patch("pipeline.pipeline.fetch_prices", side_effect=_fake_fetch)
def test_significance_can_be_disabled(mock_fetch):
    p = _pipeline(significance=False).run().evaluate()
    assert p.get_report().significance is None
