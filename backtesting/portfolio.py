"""Portfolio state: tracks positions, cash, and NAV over time."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Position:
    ticker: str
    shares: float
    avg_cost: float


class Portfolio:
    """Mutable portfolio state used during the backtest loop."""

    def __init__(self, initial_capital: float) -> None:
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self._nav_history: list[tuple[pd.Timestamp, float]] = []

    @property
    def nav_series(self) -> pd.Series:
        if not self._nav_history:
            return pd.Series(dtype=float)
        timestamps, values = zip(*self._nav_history)
        return pd.Series(values, index=pd.DatetimeIndex(timestamps), name="NAV")

    def market_value(self, prices: dict[str, float]) -> float:
        equity = sum(
            pos.shares * prices.get(ticker, 0.0)
            for ticker, pos in self.positions.items()
        )
        return self.cash + equity

    def record_nav(self, timestamp: pd.Timestamp, prices: dict[str, float]) -> None:
        self._nav_history.append((timestamp, self.market_value(prices)))

    def buy(self, ticker: str, shares: float, price: float, commission: float) -> None:
        cost = shares * price * (1 + commission)
        if cost > self.cash:
            raise ValueError(f"Insufficient cash to buy {shares} shares of {ticker}")
        self.cash -= cost
        if ticker in self.positions:
            pos = self.positions[ticker]
            total_shares = pos.shares + shares
            pos.avg_cost = (pos.shares * pos.avg_cost + shares * price) / total_shares
            pos.shares = total_shares
        else:
            self.positions[ticker] = Position(ticker, shares, price)

    def sell(self, ticker: str, shares: float, price: float, commission: float) -> None:
        if ticker not in self.positions or self.positions[ticker].shares < shares:
            raise ValueError(f"Cannot sell {shares} shares of {ticker}: insufficient position")
        proceeds = shares * price * (1 - commission)
        self.cash += proceeds
        self.positions[ticker].shares -= shares
        if self.positions[ticker].shares == 0:
            del self.positions[ticker]
