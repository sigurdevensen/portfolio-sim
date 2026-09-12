import math
import pytest
from execution.order import Order, Fill
from execution.fill import FillSimulator
import pandas as pd


def _order(direction: int, qty: float = 100.0) -> Order:
    return Order(
        ticker="EQNR.OL",
        direction=direction,
        quantity=qty,
        timestamp=pd.Timestamp("2024-01-02", tz="UTC"),
    )


def test_fill_buy_applies_slippage():
    sim = FillSimulator(slippage=0.001, commission_rate=0.001)
    fill = sim.execute(_order(1), close_price=100.0)
    assert fill.fill_price == pytest.approx(100.1)   # 100 * (1 + 1 * 0.001)


def test_fill_sell_applies_slippage():
    sim = FillSimulator(slippage=0.001, commission_rate=0.001)
    fill = sim.execute(_order(-1), close_price=100.0)
    assert fill.fill_price == pytest.approx(99.9)    # 100 * (1 + -1 * 0.001)


def test_fill_hold_no_slippage():
    sim = FillSimulator(slippage=0.001, commission_rate=0.001)
    fill = sim.execute(_order(0), close_price=100.0)
    assert fill.fill_price == pytest.approx(100.0)


def test_fill_commission_rate_passed_through():
    sim = FillSimulator(slippage=0.0, commission_rate=0.002)
    fill = sim.execute(_order(1), close_price=50.0)
    assert fill.commission_rate == 0.002


def test_fill_preserves_order():
    order = _order(1, qty=200.0)
    sim = FillSimulator(slippage=0.0, commission_rate=0.001)
    fill = sim.execute(order, close_price=50.0)
    assert fill.order is order
    assert fill.order.quantity == 200.0
