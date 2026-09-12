"""Tests for LSEGDataFeed — mocks the lseg.data library to avoid requiring a Workspace session."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import pytest

from data.lseg import LSEGDataFeed


def _fake_history(tickers: list[str], n: int = 10) -> pd.DataFrame:
    """Simulate what ld.get_history() returns: DatetimeIndex, one column per ticker."""
    idx = pd.date_range("2024-01-02", periods=n, freq="B", tz="UTC")
    data = {t: np.random.uniform(80, 120, n) for t in tickers}
    df = pd.DataFrame(data, index=idx)
    df.columns.name = None
    return df


@patch("data.lseg.ld")
def test_fetch_prices_returns_dataframe(mock_ld):
    mock_ld.get_history.return_value = _fake_history(["EQNR.OL"])
    feed = LSEGDataFeed(use_cache=False)
    df = feed.fetch_prices(["EQNR.OL"], "2024-01-01", "2024-03-01")
    assert isinstance(df, pd.DataFrame)
    assert "EQNR.OL" in df.columns
    assert df.index.tz is not None  # UTC-aware


@patch("data.lseg.ld")
def test_fetch_prices_multiple_tickers(mock_ld):
    mock_ld.get_history.return_value = _fake_history(["EQNR.OL", "DNB.OL"])
    feed = LSEGDataFeed(use_cache=False)
    df = feed.fetch_prices(["EQNR.OL", "DNB.OL"], "2024-01-01", "2024-03-01")
    assert set(df.columns) == {"EQNR.OL", "DNB.OL"}


@patch("data.lseg.ld")
def test_fetch_prices_caches_result(mock_ld, tmp_path):
    mock_ld.get_history.return_value = _fake_history(["DNB.OL"])
    feed = LSEGDataFeed(use_cache=True, cache_dir=tmp_path)
    feed.fetch_prices(["DNB.OL"], "2024-01-01", "2024-03-01")
    feed.fetch_prices(["DNB.OL"], "2024-01-01", "2024-03-01")
    # second call should hit cache — ld.get_history called only once
    assert mock_ld.get_history.call_count == 1


@patch("data.lseg.ld")
def test_fetch_fundamentals_returns_dict(mock_ld):
    mock_ld.get_data.return_value = pd.DataFrame(
        {"P/E": [12.5], "EPS": [3.1]},
        index=["EQNR.OL"],
    )
    feed = LSEGDataFeed(use_cache=False)
    result = feed.fetch_fundamentals(["EQNR.OL"])
    assert isinstance(result, dict)
    assert "EQNR.OL" in result
    assert "P/E" in result["EQNR.OL"]


@patch("data.lseg.ld")
def test_fetch_index_constituents_returns_list(mock_ld):
    mock_ld.get_data.return_value = pd.DataFrame(
        {"TR.IndexConstituentRIC": ["EQNR.OL", "DNB.OL", "TEL.OL"]}
    )
    feed = LSEGDataFeed(use_cache=False)
    result = feed.fetch_index_constituents(".OSEBX")
    assert isinstance(result, list)
    assert "EQNR.OL" in result


@patch("data.lseg.ld")
def test_fetch_prices_raises_on_session_failure(mock_ld):
    mock_ld.get_history.side_effect = Exception("Workspace not running")
    feed = LSEGDataFeed(use_cache=False)
    with pytest.raises(RuntimeError, match="LSEG"):
        feed.fetch_prices(["EQNR.OL"], "2024-01-01", "2024-03-01")
