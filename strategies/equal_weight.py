from __future__ import annotations

import numpy as np
import pandas as pd

from ._util import last_trading_day_of_period
from .base import Strategy


class EqualWeight(Strategy):
    """Equal-weight rebalancing on a fixed schedule ('W', 'M', 'Q' or 'Y').

    Emits 1 on the last trading day of each period (the engine rebalances held
    positions to target weight on a fresh 1) and 0 otherwise.
    """

    name = "equal_weight"

    def __init__(self, rebalance_freq: str = "M") -> None:
        self.rebalance_freq = rebalance_freq

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        mask = last_trading_day_of_period(data.index, self.rebalance_freq)
        out = np.where(mask[:, None], 1, 0)
        return pd.DataFrame(np.broadcast_to(out, data.shape).copy(), index=data.index, columns=data.columns).astype(int)
