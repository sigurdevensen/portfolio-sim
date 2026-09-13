"""Volume-based strategy families (require MarketData.volume)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.market import MarketData

from ._util import enter_exit_signals, sma, state_signals, zscore
from .base import Strategy


class VolumeBreakout(Strategy):
    """Buy a new ``price_window`` high only when volume is ``vol_mult`` x its average; exit below the SMA."""

    name = "volume_breakout"
    requires = {"close", "volume"}

    def __init__(self, price_window: int = 20, vol_window: int = 20, vol_mult: float = 1.5) -> None:
        self.price_window, self.vol_window, self.vol_mult = price_window, vol_window, vol_mult

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        close, vol = market.close, market.volume
        prior_high = close.rolling(self.price_window, min_periods=self.price_window).max().shift(1)
        avg_vol = vol.rolling(self.vol_window, min_periods=self.vol_window).mean().shift(1)
        enter = (close > prior_high) & (vol > self.vol_mult * avg_vol)
        return enter_exit_signals(enter, close < sma(close, self.price_window))


class OBVTrend(Strategy):
    """Long while on-balance volume is above its own moving average."""

    name = "obv_trend"
    requires = {"close", "volume"}

    def __init__(self, window: int = 20) -> None:
        self.window = window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        direction = np.sign(market.close.diff()).fillna(0)
        obv = (direction * market.volume).cumsum()
        m = sma(obv, self.window)
        return state_signals(obv > m, valid=m.notna())


class VolumeZReversal(Strategy):
    """Capitulation buy: volume z-score above ``z`` on a down day; exit above the ``exit_window`` SMA."""

    name = "volume_z_reversal"
    requires = {"close", "volume"}

    def __init__(self, window: int = 20, z: float = 2.0, exit_window: int = 10) -> None:
        self.window, self.z, self.exit_window = window, z, exit_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        vz = zscore(market.volume, self.window)
        down = market.close.pct_change() < 0
        enter = (vz > self.z) & down
        return enter_exit_signals(enter, market.close > sma(market.close, self.exit_window))


VOLUME_FAMILIES = [VolumeBreakout, OBVTrend, VolumeZReversal]
