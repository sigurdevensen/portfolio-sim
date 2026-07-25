"""Core backtesting engine — drives the simulation loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from strategies.base import Strategy


@dataclass
class BacktestConfig:
    start: str
    end: str
    initial_capital: float = 100_000.0
    commission: float = 0.001  # 0.1% per trade
    slippage: float = 0.0005


class BacktestEngine:
    """Runs a strategy against historical price data."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def run(self, strategy: "Strategy", prices: pd.DataFrame) -> "BacktestResult":  # noqa: F821
        """Execute backtest and return a result object.

        Args:
            strategy: A Strategy instance with generate_signals().
            prices: DataFrame with DatetimeIndex and one column per ticker (adjusted close).

        Returns:
            BacktestResult with NAV series, trades, and metrics.
        """
        raise NotImplementedError
