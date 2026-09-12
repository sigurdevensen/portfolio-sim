"""FillSimulator: applies slippage and commission to an order."""
from __future__ import annotations

from execution.order import Fill, Order


class FillSimulator:
    """Stateless fill execution with configurable slippage and commission."""

    def __init__(self, slippage: float = 0.0005, commission_rate: float = 0.001) -> None:
        self.slippage = slippage
        self.commission_rate = commission_rate

    def execute(self, order: Order, close_price: float) -> Fill:
        """Apply directional slippage to close_price and return a Fill.

        Args:
            order: The order to fill.
            close_price: End-of-day close price for the ticker.

        Returns:
            Fill with slippage-adjusted fill_price and commission_rate.
        """
        fill_price = close_price * (1 + order.direction * self.slippage)
        return Fill(order=order, fill_price=fill_price, commission_rate=self.commission_rate)
