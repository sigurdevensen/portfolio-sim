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


# ── external series and dividends ──────────────────────────────────────────

from data.market import fetch_dividends, fetch_external


def test_from_close_has_empty_extra_and_no_dividends():
    m = MarketData.from_close(_close())
    assert m.extra == {}
    assert m.dividends is None


def test_extra_series_are_aligned_and_ffilled_on_attach():
    close = _close(n=10)
    raw = pd.Series([1.0, 2.0, 3.0], index=pd.DatetimeIndex([close.index[0], close.index[2], close.index[5]]))
    m = MarketData.from_close(close)
    m.attach_extra("brent", raw)
    s = m.extra["brent"]
    assert s.index.equals(close.index)
    assert s.iloc[1] == 1.0          # forward-filled
    assert s.iloc[-1] == 3.0
    assert not s.isna().any()


def test_attach_extra_accepts_dataframe():
    close = _close(n=6)
    df = pd.DataFrame({"a": range(6), "b": range(6)}, index=close.index)
    m = MarketData.from_close(close)
    m.attach_extra("macro", df)
    assert m.extra["macro"].shape == (6, 2)


def test_slice_keeps_extra_and_dividends():
    close = _close(n=30)
    m = MarketData.from_close(close)
    m.attach_extra("vix", pd.Series(20.0, index=close.index))
    m.dividends = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    m.dividends.iloc[20, 0] = 1.5
    s = m.slice("2024-01-15", "2024-02-09")
    assert s.extra["vix"].index.equals(s.close.index)
    assert s.dividends.shape == s.close.shape
    assert s.dividends.to_numpy().sum() == 1.5


def test_require_extra_raises_helpful_error():
    m = MarketData.from_close(_close())
    with pytest.raises(KeyError, match="brent"):
        m.require_extra("brent")


def _fake_macro(tickers, start, end, auto_adjust=True, progress=False):
    idx = pd.date_range(start, periods=12, freq="D")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], tickers])
    df = pd.DataFrame(1.0, index=idx, columns=cols)
    for i, t in enumerate(tickers):
        df[("Close", t)] = np.arange(12, dtype=float) + 10 * i
    return df


@patch("data.market.yf.download", side_effect=_fake_macro)
def test_fetch_external_returns_named_close_frame(mock_dl, tmp_path):
    ext = fetch_external({"brent": "BZ=F", "vix": "^VIX"}, "2024-01-01", "2024-01-31", cache_dir=tmp_path)
    assert list(ext.columns) == ["brent", "vix"]
    assert ext.index.tz is not None
    assert ext["vix"].iloc[0] == 10.0
    fetch_external({"brent": "BZ=F", "vix": "^VIX"}, "2024-01-01", "2024-01-31", cache_dir=tmp_path)
    assert mock_dl.call_count == 1  # cached


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    @property
    def dividends(self):
        idx = pd.DatetimeIndex(["2024-01-03", "2024-01-10"], tz="Europe/Oslo")
        return pd.Series([1.0, 2.0], index=idx, name="Dividends")


@patch("data.market.yf.Ticker", side_effect=_FakeTicker)
def test_fetch_dividends_aligned_to_index(mock_tk, tmp_path):
    close = _close(n=10)  # 2024-01-01 .. business days
    div = fetch_dividends(["AAA", "BBB"], close.index, cache_dir=tmp_path)
    assert div.shape == close.shape
    assert div.loc["2024-01-03", "AAA"] == 1.0
    assert div.loc["2024-01-10", "BBB"] == 2.0
    assert div.to_numpy().sum() == 6.0


from data.market import cache_key


def test_cache_key_short_is_readable_and_long_is_hashed():
    short = cache_key("ohlcv", "AAA_BBB", "2020-01-01", "2020-12-31")
    assert short == "ohlcv_AAA_BBB_2020-01-01_2020-12-31"
    long = cache_key("ohlcv", "_".join(f"T{i}.OL" for i in range(40)), "2010-01-01", "2024-12-31")
    assert len(long) < 120
    assert long != cache_key("ohlcv", "_".join(f"T{i}.OL" for i in range(41)), "2010-01-01", "2024-12-31")
    assert "^" not in cache_key("external", "^VIX", "a", "b")
