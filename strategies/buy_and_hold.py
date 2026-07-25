from __future__ import annotations

import pandas as pd

from .base import Strategy


class BuyAndHold(Strategy):
    """Always long every asset — baseline benchmark strategy."""

    name = "buy_and_hold"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(1, index=data.index, columns=data.columns)
