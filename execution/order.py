"""Order and Fill dataclasses for the simulated execution layer."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Order:
    ticker: str
    direction: int          # {-1, 0, 1}
    quantity: float
    timestamp: pd.Timestamp


@dataclass
class Fill:
    order: Order
    fill_price: float
    commission_rate: float  # fraction, e.g. 0.001 for 0.1%
