"""Regime, dip-buying and short-term reversal families."""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.market import MarketData

from ._util import enter_exit_signals, rolling_vol, state_signals
from .base import Strategy


class VolatilityRegime(Strategy):
    """Long only while realised annualised volatility is below ``threshold``."""

    name = "vol_regime"

    def __init__(self, window: int = 20, threshold: float = 0.25) -> None:
        self.window, self.threshold = window, threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        vol = rolling_vol(data, self.window)
        return state_signals(vol < self.threshold, valid=vol.notna())


class BuyTheDip(Strategy):
    """Buy when price is ``drawdown`` below its rolling ``window`` high; exit once back within ``exit_dd`` of it."""

    name = "buy_the_dip"

    def __init__(self, drawdown: float = 0.10, window: int = 126, exit_dd: float = 0.02) -> None:
        self.drawdown, self.window, self.exit_dd = drawdown, window, exit_dd

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        hi = data.rolling(self.window, min_periods=self.window // 2).max()
        dd = data / hi - 1
        return enter_exit_signals(dd <= -self.drawdown, dd >= -self.exit_dd)


class StreakReversal(Strategy):
    """Buy after ``down_days`` consecutive down closes; exit on the first up close."""

    name = "streak_reversal"

    def __init__(self, down_days: int = 3) -> None:
        self.down_days = down_days

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change()
        down = (ret < 0).astype(int)
        # consecutive-down counter, reset on up days
        streak = down.copy()
        arr = down.to_numpy().copy()
        for i in range(1, len(arr)):
            arr[i] = np.where(arr[i] > 0, arr[i - 1] + 1, 0)
        streak.loc[:, :] = arr
        return enter_exit_signals(streak >= self.down_days, ret > 0)


class GapReversal(Strategy):
    """Buy a gap-down open (open < prev close * (1 - gap)); exit the following bar."""

    name = "gap_reversal"
    requires = {"open", "close"}

    def __init__(self, gap: float = 0.02) -> None:
        self.gap = gap

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        gap_down = market.open < market.close.shift(1) * (1 - self.gap)
        exit_next = gap_down.shift(1).fillna(False).astype(bool) & ~gap_down
        return enter_exit_signals(gap_down, exit_next)


REGIME_FAMILIES = [VolatilityRegime, BuyTheDip, StreakReversal, GapReversal]
