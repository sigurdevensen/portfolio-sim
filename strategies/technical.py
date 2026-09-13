"""Technical-indicator strategy families (price and OHLC based)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.market import MarketData

from ._util import atr, ema, enter_exit_signals, rsi, sma, state_signals
from .base import Strategy


class SMACross(Strategy):
    """Long while the fast simple moving average is above the slow one."""

    name = "sma_cross"

    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        self.fast, self.slow = fast, slow

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        f, s = sma(data, self.fast), sma(data, self.slow)
        return state_signals(f > s, valid=f.notna() & s.notna())


class EMACross(Strategy):
    """Long while the fast exponential moving average is above the slow one."""

    name = "ema_cross"

    def __init__(self, fast: int = 12, slow: int = 26) -> None:
        self.fast, self.slow = fast, slow

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        f, s = ema(data, self.fast), ema(data, self.slow)
        return state_signals(f > s, valid=f.notna() & s.notna())


class PriceVsSMA(Strategy):
    """Trend filter: long while close is above its moving average."""

    name = "price_vs_sma"

    def __init__(self, window: int = 200) -> None:
        self.window = window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        m = sma(data, self.window)
        return state_signals(data > m, valid=m.notna())


class MACDSignal(Strategy):
    """Long while the MACD line is above its signal line."""

    name = "macd"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self.fast, self.slow, self.signal = fast, slow, signal

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        macd = ema(data, self.fast) - ema(data, self.slow)
        sig = macd.ewm(span=self.signal, adjust=False, min_periods=self.signal).mean()
        return state_signals(macd > sig, valid=macd.notna() & sig.notna())


class RSIReversal(Strategy):
    """Buy when RSI drops below ``lower``; exit when it rises above ``upper``."""

    name = "rsi_reversal"

    def __init__(self, window: int = 14, lower: float = 30.0, upper: float = 70.0) -> None:
        self.window, self.lower, self.upper = window, lower, upper

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        r = rsi(data, self.window)
        return enter_exit_signals(r < self.lower, r > self.upper)


class RSITrend(Strategy):
    """Momentum reading of RSI: long while RSI is above ``threshold``."""

    name = "rsi_trend"

    def __init__(self, window: int = 14, threshold: float = 50.0) -> None:
        self.window, self.threshold = window, threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        r = rsi(data, self.window)
        return state_signals(r > self.threshold, valid=r.notna())


class BollingerReversion(Strategy):
    """Buy below the lower band; exit when price recovers above the middle band."""

    name = "bollinger_reversion"

    def __init__(self, window: int = 20, n_std: float = 2.0) -> None:
        self.window, self.n_std = window, n_std

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        mid = sma(data, self.window)
        sd = data.rolling(self.window, min_periods=self.window).std()
        lower = mid - self.n_std * sd
        return enter_exit_signals(data < lower, data > mid)


class BollingerBreakout(Strategy):
    """Buy above the upper band; exit when price falls back below the middle band."""

    name = "bollinger_breakout"

    def __init__(self, window: int = 20, n_std: float = 2.0) -> None:
        self.window, self.n_std = window, n_std

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        mid = sma(data, self.window)
        sd = data.rolling(self.window, min_periods=self.window).std()
        upper = mid + self.n_std * sd
        return enter_exit_signals(data > upper, data < mid)


class KeltnerBreakout(Strategy):
    """Buy above the upper Keltner channel (EMA + mult*ATR); exit below the EMA."""

    name = "keltner_breakout"
    requires = {"high", "low", "close"}

    def __init__(self, window: int = 20, atr_window: int = 10, mult: float = 2.0) -> None:
        self.window, self.atr_window, self.mult = window, atr_window, mult

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        mid = ema(market.close, self.window)
        band = atr(market.high, market.low, market.close, self.atr_window)
        upper = mid + self.mult * band
        return enter_exit_signals(market.close > upper, market.close < mid)


class Stochastic(Strategy):
    """Buy when %K crosses up through ``lower``; exit when %K exceeds ``upper``."""

    name = "stochastic"
    requires = {"high", "low", "close"}

    def __init__(self, k: int = 14, d: int = 3, lower: float = 20.0, upper: float = 80.0) -> None:
        self.k, self.d, self.lower, self.upper = k, d, lower, upper

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        hh = market.high.rolling(self.k, min_periods=self.k).max()
        ll = market.low.rolling(self.k, min_periods=self.k).min()
        pct_k = 100 * (market.close - ll) / (hh - ll).replace(0, np.nan)
        pct_d = pct_k.rolling(self.d, min_periods=self.d).mean()
        crossed_up = (pct_d > self.lower) & (pct_d.shift(1) <= self.lower)
        return enter_exit_signals(crossed_up, pct_d > self.upper)


class ROCMomentum(Strategy):
    """Long while the rate of change over ``window`` days exceeds ``threshold``."""

    name = "roc_momentum"

    def __init__(self, window: int = 63, threshold: float = 0.0) -> None:
        self.window, self.threshold = window, threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        roc = data.pct_change(self.window)
        return state_signals(roc > self.threshold, valid=roc.notna())


class DonchianBreakout(Strategy):
    """Turtle-style: buy on a close above the prior ``entry``-day high, exit below the ``exit``-day low."""

    name = "donchian_breakout"
    requires = {"high", "low", "close"}

    def __init__(self, entry: int = 55, exit: int = 20) -> None:
        self.entry, self.exit = entry, exit

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        prior_high = market.high.rolling(self.entry, min_periods=self.entry).max().shift(1)
        prior_low = market.low.rolling(self.exit, min_periods=self.exit).min().shift(1)
        return enter_exit_signals(market.close > prior_high, market.close < prior_low)


class ATRBreakout(Strategy):
    """Buy when close exceeds its SMA by ``mult`` ATRs; exit when close drops below the SMA."""

    name = "atr_breakout"
    requires = {"high", "low", "close"}

    def __init__(self, window: int = 20, mult: float = 1.5) -> None:
        self.window, self.mult = window, mult

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        mid = sma(market.close, self.window)
        band = atr(market.high, market.low, market.close, self.window)
        return enter_exit_signals(market.close - mid > self.mult * band, market.close < mid)


TECHNICAL_FAMILIES = [
    SMACross, EMACross, PriceVsSMA, MACDSignal, RSIReversal, RSITrend,
    BollingerReversion, BollingerBreakout, KeltnerBreakout, Stochastic,
    ROCMomentum, DonchianBreakout, ATRBreakout,
]
