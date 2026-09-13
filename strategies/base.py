"""Abstract base class for all portfolio strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from data.market import MarketData


class Strategy(ABC):
    """All strategies must implement generate_signals().

    Signals convention:
        1  = go long / increase weight
        0  = hold / no change
       -1  = exit / reduce weight

    Optional risk controls (fractions of entry / peak price; ``None`` = off). The
    engine checks them on every bar close before processing signals:
        stop_loss      exit when close <= entry * (1 - stop_loss)
        take_profit    exit when close >= entry * (1 + take_profit)
        trailing_stop  exit when close <= peak_since_entry * (1 - trailing_stop)

    ``requires`` lists the MarketData fields the strategy reads. Strategies that
    need more than closes override ``generate_signals_market``; the default
    delegates to ``generate_signals(market.close)``.
    """

    name: str = "base"
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    requires: set[str] = {"close"}

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame of signals aligned with data's index and columns.

        Args:
            data: Adjusted-close prices, DatetimeIndex, one column per ticker.

        Returns:
            DataFrame of the same shape with signal values {-1, 0, 1}.
        """

    def generate_signals_market(self, market: "MarketData") -> pd.DataFrame:
        """Signals from full OHLCV data. Default: close-only strategies."""
        return self.generate_signals(market.close)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
