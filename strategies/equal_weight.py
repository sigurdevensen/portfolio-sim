from __future__ import annotations

import pandas as pd

from .base import Strategy


class EqualWeight(Strategy):
    """Equal-weight rebalancing on a fixed schedule."""

    name = "equal_weight"

    def __init__(self, rebalance_freq: str = "M") -> None:
        self.rebalance_freq = rebalance_freq

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(0, index=data.index, columns=data.columns)
        rebalance_dates = data.resample(self.rebalance_freq).last().index
        signals.loc[signals.index.isin(rebalance_dates)] = 1
        return signals
