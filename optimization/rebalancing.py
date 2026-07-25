"""Portfolio rebalancing utilities."""
from __future__ import annotations

from enum import Enum

import pandas as pd


class RebalanceFrequency(str, Enum):
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"
    QUARTERLY = "Q"
    YEARLY = "Y"


class RebalanceSchedule:
    """Generates rebalance dates for a given date range and frequency."""

    def __init__(self, frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY) -> None:
        self.frequency = frequency

    def get_dates(self, start: str, end: str) -> pd.DatetimeIndex:
        date_range = pd.date_range(start, end, freq=self.frequency.value)
        return date_range

    def is_rebalance_date(self, date: pd.Timestamp, start: str, end: str) -> bool:
        return date in self.get_dates(start, end)
