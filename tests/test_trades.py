"""Tests for round-trip trade pairing and trade statistics."""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.trades import round_trips, trade_statistics

TRADE_COLS = ["date", "ticker", "direction", "quantity", "fill_price", "commission"]


def _ts(day: str) -> pd.Timestamp:
    return pd.Timestamp(day, tz="UTC")


def _log(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=TRADE_COLS)


def test_single_round_trip_pnl_and_return():
    log = _log([
        (_ts("2024-01-02"), "AAA", 1, 10.0, 100.0, 1.0),
        (_ts("2024-01-12"), "AAA", -1, 10.0, 110.0, 1.1),
    ])
    rt = round_trips(log)
    assert len(rt) == 1
    row = rt.iloc[0]
    assert row["ticker"] == "AAA"
    assert row["entry_price"] == 100.0
    assert row["exit_price"] == 110.0
    assert row["quantity"] == 10.0
    assert row["pnl"] == pytest.approx(10 * 10 - 1.0 - 1.1)
    assert row["return_pct"] == pytest.approx((100 - 2.1) / 1000)  # net of commission
    assert row["holding_days"] == 10
    assert row["commission"] == pytest.approx(2.1)


def test_partial_exit_splits_fifo():
    log = _log([
        (_ts("2024-01-02"), "AAA", 1, 10.0, 100.0, 0.0),
        (_ts("2024-01-03"), "AAA", 1, 10.0, 120.0, 0.0),
        (_ts("2024-01-10"), "AAA", -1, 15.0, 130.0, 0.0),
    ])
    rt = round_trips(log)
    assert len(rt) == 2
    first, second = rt.iloc[0], rt.iloc[1]
    assert first["quantity"] == 10.0 and first["entry_price"] == 100.0
    assert second["quantity"] == 5.0 and second["entry_price"] == 120.0
    assert first["pnl"] == pytest.approx(300.0)
    assert second["pnl"] == pytest.approx(50.0)


def test_open_position_excluded():
    log = _log([
        (_ts("2024-01-02"), "AAA", 1, 10.0, 100.0, 0.0),
        (_ts("2024-01-02"), "BBB", 1, 5.0, 50.0, 0.0),
        (_ts("2024-01-05"), "AAA", -1, 10.0, 90.0, 0.0),
    ])
    rt = round_trips(log)
    assert list(rt["ticker"]) == ["AAA"]


def test_empty_log_gives_empty_frame_and_zero_stats():
    rt = round_trips(pd.DataFrame(columns=TRADE_COLS))
    assert rt.empty
    stats = trade_statistics(rt)
    assert stats["n_trades"] == 0
    assert stats["win_rate"] == 0.0
    assert stats["profit_factor"] == 0.0


def test_statistics_on_known_trades():
    log = _log([
        (_ts("2024-01-02"), "AAA", 1, 10.0, 100.0, 0.0),
        (_ts("2024-01-04"), "AAA", -1, 10.0, 110.0, 0.0),   # +100
        (_ts("2024-01-05"), "AAA", 1, 10.0, 100.0, 0.0),
        (_ts("2024-01-09"), "AAA", -1, 10.0, 120.0, 0.0),   # +200
        (_ts("2024-01-10"), "AAA", 1, 10.0, 100.0, 0.0),
        (_ts("2024-01-11"), "AAA", -1, 10.0, 95.0, 0.0),    # -50
    ])
    stats = trade_statistics(round_trips(log))
    assert stats["n_trades"] == 3
    assert stats["n_wins"] == 2
    assert stats["n_losses"] == 1
    assert stats["win_rate"] == pytest.approx(2 / 3)
    assert stats["avg_win"] == pytest.approx(150.0)
    assert stats["avg_loss"] == pytest.approx(-50.0)
    assert stats["profit_factor"] == pytest.approx(300 / 50)
    assert stats["expectancy"] == pytest.approx(250 / 3)
    assert stats["total_pnl"] == pytest.approx(250.0)
    assert stats["best_trade"] == pytest.approx(200.0)
    assert stats["worst_trade"] == pytest.approx(-50.0)
    assert stats["max_consecutive_wins"] == 2
    assert stats["max_consecutive_losses"] == 1
    assert stats["avg_holding_days"] == pytest.approx((2 + 4 + 1) / 3)


def test_profit_factor_infinite_when_no_losses_is_capped():
    log = _log([
        (_ts("2024-01-02"), "AAA", 1, 1.0, 100.0, 0.0),
        (_ts("2024-01-03"), "AAA", -1, 1.0, 101.0, 0.0),
    ])
    stats = trade_statistics(round_trips(log))
    assert stats["profit_factor"] == float("inf") or stats["profit_factor"] > 1e6
