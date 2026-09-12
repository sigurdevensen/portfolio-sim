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
