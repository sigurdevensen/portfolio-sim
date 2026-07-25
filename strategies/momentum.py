from __future__ import annotations

import pandas as pd

from .base import Strategy


class Momentum(Strategy):
    """Cross-sectional momentum: long top-N assets by trailing return."""

    name = "momentum"

    def __init__(self, lookback: int = 252, top_n: int = 3) -> None:
        self.lookback = lookback
        self.top_n = top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        trailing_returns = data.pct_change(self.lookback)
        signals = pd.DataFrame(0, index=data.index, columns=data.columns)
        for date in data.index[self.lookback:]:
            row = trailing_returns.loc[date].dropna()
            top = row.nlargest(self.top_n).index
            signals.loc[date, top] = 1
        return signals
