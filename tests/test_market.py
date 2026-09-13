"""Tests for the OHLCV MarketData container and its loader."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from data.market import FIELDS, MarketData, fetch_market_data


def _close(n: int = 30, tickers=("AAA", "BBB")) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0, 0.01, n)) for t in tickers}, index=idx)


def test_fields_constant():
    assert FIELDS == ("open", "high", "low", "close", "volume")


def test_from_close_builds_all_fields_aligned():
    close = _close()
    m = MarketData.from_close(close)
    for f in FIELDS:
        df = getattr(m, f)
        assert df.shape == close.shape
        assert list(df.columns) == list(close.columns)
        assert df.index.equals(close.index)
    assert m.synthetic is True
    assert (m.high >= m.close).all().all()
    assert (m.low <= m.close).all().all()
    assert not m.volume.isna().any().any()


def test_tickers_and_index():
    m = MarketData.from_close(_close())
    assert m.tickers == ["AAA", "BBB"]
    assert len(m.index) == 30


def test_slice_by_date():
    m = MarketData.from_close(_close())
    s = m.slice("2024-01-15", "2024-01-31")
    assert s.close.index[0] >= pd.Timestamp("2024-01-15", tz="UTC")
    assert s.close.index[-1] <= pd.Timestamp("2024-01-31", tz="UTC")
    assert s.volume.shape == s.close.shape


def test_validate_rejects_misaligned_fields():
    close = _close()
    with pytest.raises(ValueError, match="aligned"):
        MarketData(open=close.iloc[:-1], high=close, low=close, close=close, volume=close)


def _fake_yf(tickers, start, end, auto_adjust=True, progress=False):
    idx = pd.date_range(start, periods=10, freq="B")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], tickers])
    data = np.tile(np.arange(1, 11, dtype=float)[:, None], (1, len(cols)))
    df = pd.DataFrame(data, index=idx, columns=cols)
    df.loc[:, ("High", slice(None))] = df.loc[:, ("High", slice(None))] + 1
    df.loc[:, ("Low", slice(None))] = df.loc[:, ("Low", slice(None))] - 1
    return df


@patch("data.market.yf.download", side_effect=_fake_yf)
def test_fetch_market_data_parses_multiindex(mock_dl, tmp_path):
    m = fetch_market_data(["AAA", "BBB"], "2024-01-01", "2024-01-20", cache_dir=tmp_path)
    assert m.tickers == ["AAA", "BBB"]
    assert m.close.index.tz is not None
    assert m.high["AAA"].iloc[0] == 2.0
    assert m.low["BBB"].iloc[0] == 0.0
    assert m.synthetic is False


@patch("data.market.yf.download", side_effect=_fake_yf)
def test_fetch_market_data_uses_cache_second_time(mock_dl, tmp_path):
    fetch_market_data(["AAA"], "2024-01-01", "2024-01-20", cache_dir=tmp_path)
    m2 = fetch_market_data(["AAA"], "2024-01-01", "2024-01-20", cache_dir=tmp_path)
    assert mock_dl.call_count == 1
    assert m2.close["AAA"].iloc[-1] == 10.0
    assert m2.volume.shape == m2.close.shape
