from __future__ import annotations

import pandas as pd

from ._util import state_signals
from .base import Strategy


class Momentum(Strategy):
    """Cross-sectional momentum: long the top-N assets by trailing return, if positive.

    Emits 1 for the top-N assets with positive trailing return, -1 for every other
    asset with a defined trailing return (so the engine exits positions that drop
    out or turn negative), and 0 during the warm-up window. With a single ticker
    this degenerates to time-series momentum.
    """

    name = "momentum"

    def __init__(self, lookback: int = 252, top_n: int = 3) -> None:
        self.lookback = lookback
        self.top_n = top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        trailing = data.pct_change(self.lookback)
        positive = trailing.where(trailing > 0)
        rank = positive.rank(axis=1, ascending=False, method="first")
        return state_signals(rank <= self.top_n, valid=trailing.notna())
