"""Abstract base class for all portfolio strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """All strategies must implement generate_signals().

    Signals convention:
        1  = go long / increase weight
        0  = hold / no change
       -1  = exit / reduce weight
    """

    name: str = "base"

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame of signals aligned with data's index and columns.

        Args:
            data: Adjusted-close prices, DatetimeIndex, one column per ticker.

        Returns:
            DataFrame of the same shape with signal values {-1, 0, 1}.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
