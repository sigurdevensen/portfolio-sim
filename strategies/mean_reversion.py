from __future__ import annotations

import pandas as pd

from .base import Strategy


class MeanReversion(Strategy):
    """Buy assets that have fallen most vs their moving average."""

    name = "mean_reversion"

    def __init__(self, window: int = 20, z_threshold: float = 1.5) -> None:
        self.window = window
        self.z_threshold = z_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ma = data.rolling(self.window).mean()
        std = data.rolling(self.window).std()
        z_score = (data - ma) / std
        signals = pd.DataFrame(0, index=data.index, columns=data.columns)
        signals[z_score < -self.z_threshold] = 1   # buy when price far below MA
        signals[z_score > self.z_threshold] = -1    # sell when price far above MA
        return signals
