"""FillSimulator: applies slippage and commission to an order."""
from __future__ import annotations

from execution.order import Fill, Order


class FillSimulator:
    """Stateless fill execution with configurable slippage and commission."""

    def __init__(self, slippage: float = 0.0005, commission_rate: float = 0.001) -> None:
        if slippage < 0:
            raise ValueError(f"slippage must be >= 0; got {slippage}")
        if commission_rate < 0:
            raise ValueError(f"commission_rate must be >= 0; got {commission_rate}")
        self.slippage = slippage
        self.commission_rate = commission_rate

    def execute(self, order: Order, close_price: float) -> Fill:
        """Apply directional slippage to close_price and return a Fill.

        Args:
            order: The order to fill.
            close_price: End-of-day close price for the ticker (must be > 0).

        Returns:
            Fill with slippage-adjusted fill_price and commission_rate.

        Raises:
            ValueError: If close_price is not positive.
        """
        if close_price <= 0:
            raise ValueError(f"close_price must be > 0; got {close_price}")
        fill_price = close_price * (1 + order.direction * self.slippage)
        return Fill(order=order, fill_price=fill_price, commission_rate=self.commission_rate)
