"""Order and Fill dataclasses for the simulated execution layer."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Order:
    ticker: str
    direction: int          # must be one of {-1, 0, 1}
    quantity: float         # must be > 0
    timestamp: pd.Timestamp

    def __post_init__(self) -> None:
        if self.direction not in {-1, 0, 1}:
            raise ValueError(f"direction must be -1, 0, or 1; got {self.direction}")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be > 0; got {self.quantity}")


@dataclass(frozen=True)
class Fill:
    """Result of executing an Order.

    commission_rate is a fraction (e.g. 0.001 = 0.1%) applied by the caller
    as quantity * fill_price * commission_rate to compute actual commission cost.
    """
    order: Order
    fill_price: float
    commission_rate: float  # fraction >= 0
