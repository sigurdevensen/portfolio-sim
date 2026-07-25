"""Tests for strategy signal generation."""
import numpy as np
import pandas as pd
import pytest

from strategies import BuyAndHold, EqualWeight, Momentum, MeanReversion


def _price_df(n: int = 300, tickers: list[str] | None = None) -> pd.DataFrame:
    if tickers is None:
        tickers = ["A", "B", "C"]
    np.random.seed(0)
    dates = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    prices = pd.DataFrame(
        np.cumprod(1 + np.random.normal(0.0003, 0.01, (n, len(tickers))), axis=0) * 100,
        index=dates,
        columns=tickers,
    )
    return prices


def test_buy_and_hold_all_ones():
    prices = _price_df()
    signals = BuyAndHold().generate_signals(prices)
    assert (signals == 1).all().all()
    assert signals.shape == prices.shape


def test_equal_weight_shape():
    prices = _price_df()
    signals = EqualWeight().generate_signals(prices)
    assert signals.shape == prices.shape


def test_momentum_signals_binary():
    prices = _price_df()
    signals = Momentum(lookback=60, top_n=2).generate_signals(prices)
    assert set(signals.values.flatten()).issubset({0, 1})


def test_mean_reversion_signals_ternary():
    prices = _price_df()
    signals = MeanReversion().generate_signals(prices)
    assert set(signals.values.flatten()).issubset({-1, 0, 1})
