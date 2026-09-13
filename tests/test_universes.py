"""Tests for named universes (Oslo)."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from data.market import MarketData
from research.universes import MACRO_SYMBOLS, UNIVERSES, load_universe, universe_tickers


def test_oslo_universe_defined():
    tickers = universe_tickers("oslo")
    assert len(tickers) >= 25
    assert all(t.endswith(".OL") for t in tickers)
    assert "EQNR.OL" in tickers and "DNB.OL" in tickers


def test_macro_symbols_cover_required_data_types():
    assert {"brent", "usdnok", "vix", "spx", "us10y", "obx"} <= set(MACRO_SYMBOLS)


def test_unknown_universe_raises():
    with pytest.raises(KeyError):
        universe_tickers("mars")


def _fake_market(tickers, start, end, use_cache=True, cache_dir=None):
    idx = pd.date_range("2020-01-01", periods=50, freq="B", tz="UTC")
    return MarketData.from_close(pd.DataFrame({t: 100.0 for t in tickers}, index=idx))


def _fake_external(symbols, start, end, use_cache=True, cache_dir=None):
    idx = pd.date_range("2020-01-01", periods=50, freq="B", tz="UTC")
    return pd.DataFrame({k: 1.0 for k in symbols}, index=idx)


def _fake_dividends(tickers, index, use_cache=True, cache_dir=None):
    return pd.DataFrame(0.0, index=index, columns=tickers)


@patch("research.universes.fetch_dividends", side_effect=_fake_dividends)
@patch("research.universes.fetch_external", side_effect=_fake_external)
@patch("research.universes.fetch_market_data", side_effect=_fake_market)
def test_load_universe_attaches_extras_and_dividends(m1, m2, m3):
    m = load_universe("oslo", "2020-01-01", "2020-03-31")
    assert set(MACRO_SYMBOLS) <= set(m.extra)
    assert m.dividends is not None and m.dividends.shape == m.close.shape
    assert m.meta["universe"] == "oslo"
    assert UNIVERSES["oslo"]["description"]
