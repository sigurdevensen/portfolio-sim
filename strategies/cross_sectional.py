"""Cross-sectional (universe-relative) strategy families."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ._util import rolling_vol, state_signals
from .base import Strategy


def _top_n_signals(score: pd.DataFrame, top_n: int, require_positive: bool = False) -> pd.DataFrame:
    """1 for the top-N tickers by score each day, -1 for the rest, 0 where score is NaN."""
    eligible = score.where(score > 0) if require_positive else score
    rank = eligible.rank(axis=1, ascending=False, method="first")
    long = rank <= top_n
    return state_signals(long, valid=score.notna())


class LowVolatility(Strategy):
    """Hold the ``top_n`` tickers with the lowest realised volatility."""

    name = "low_volatility"

    def __init__(self, window: int = 60, top_n: int = 3) -> None:
        self.window, self.top_n = window, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        vol = rolling_vol(data, self.window)
        return _top_n_signals(-vol, self.top_n)


class DualMomentum(Strategy):
    """Relative momentum (top-N) gated by absolute momentum (trailing return > 0)."""

    name = "dual_momentum"

    def __init__(self, lookback: int = 126, top_n: int = 2) -> None:
        self.lookback, self.top_n = lookback, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change(self.lookback)
        return _top_n_signals(ret, self.top_n, require_positive=True)


class RelativeStrength(Strategy):
    """Long tickers whose trailing return beats the universe median."""

    name = "relative_strength"

    def __init__(self, window: int = 63) -> None:
        self.window = window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change(self.window)
        median = ret.median(axis=1)
        long = ret.gt(median, axis=0)
        return state_signals(long, valid=ret.notna())


class High52Week(Strategy):
    """Buy near the rolling high (>= ``threshold`` x max); exit when falling below ``exit_threshold`` x max."""

    name = "high_52w"

    def __init__(self, window: int = 252, threshold: float = 0.95, exit_threshold: float = 0.85) -> None:
        self.window, self.threshold, self.exit_threshold = window, threshold, exit_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        from ._util import enter_exit_signals
        hi = data.rolling(self.window, min_periods=self.window // 2).max()
        return enter_exit_signals(data >= self.threshold * hi, data < self.exit_threshold * hi)


class TimeSeriesMomentum(Strategy):
    """Long while the return from t-lookback to t-skip is positive (skips the most recent month)."""

    name = "ts_momentum"

    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        self.lookback, self.skip = lookback, skip

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.shift(self.skip) / data.shift(self.lookback) - 1
        return state_signals(ret > 0, valid=ret.notna())


CROSS_SECTIONAL_FAMILIES = [LowVolatility, DualMomentum, RelativeStrength, High52Week, TimeSeriesMomentum]
