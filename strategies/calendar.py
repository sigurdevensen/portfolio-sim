"""Calendar / seasonality strategy families (use only the date index)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


def _broadcast(mask: np.ndarray, data: pd.DataFrame) -> pd.DataFrame:
    out = np.where(mask[:, None], 1, -1)
    return pd.DataFrame(np.broadcast_to(out, data.shape).copy(), index=data.index, columns=data.columns).astype(int)


def _parse_ints(spec: str) -> set[int]:
    return {int(s) for s in str(spec).replace(";", ",").split(",") if s.strip() != ""}


class TurnOfMonth(Strategy):
    """Long on the last ``days_before`` trading days of a month and first ``days_after`` of the next."""

    name = "turn_of_month"

    def __init__(self, days_before: int = 1, days_after: int = 3) -> None:
        self.days_before, self.days_after = days_before, days_after

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        idx = data.index
        month = idx.month.to_numpy()
        n = len(idx)
        # position within month (1-based) and days remaining to month end (0 = last day)
        pos = np.zeros(n, dtype=int)
        remaining = np.zeros(n, dtype=int)
        start = 0
        for i in range(1, n + 1):
            if i == n or month[i] != month[i - 1]:
                length = i - start
                pos[start:i] = np.arange(1, length + 1)
                remaining[start:i] = np.arange(length - 1, -1, -1)
                start = i
        mask = (pos <= self.days_after) | (remaining < self.days_before)
        return _broadcast(mask, data)


class DayOfWeek(Strategy):
    """Long only on the listed weekdays (0 = Monday ... 4 = Friday), e.g. "1,2,3,4"."""

    name = "day_of_week"

    def __init__(self, long_days: str = "1,2,3,4") -> None:
        self.long_days = long_days

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        days = _parse_ints(self.long_days)
        mask = np.isin(data.index.dayofweek.to_numpy(), list(days))
        return _broadcast(mask, data)


class SellInMay(Strategy):
    """Long only during the listed months (default November through April)."""

    name = "sell_in_may"

    def __init__(self, long_months: str = "11,12,1,2,3,4") -> None:
        self.long_months = long_months

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        months = _parse_ints(self.long_months)
        mask = np.isin(data.index.month.to_numpy(), list(months))
        return _broadcast(mask, data)


CALENDAR_FAMILIES = [TurnOfMonth, DayOfWeek, SellInMay]
