"""Trade-level analytics: pair fills into round trips and summarise them."""
from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd

ROUND_TRIP_COLUMNS = [
    "ticker",
    "entry_date",
    "exit_date",
    "quantity",
    "entry_price",
    "exit_price",
    "pnl",
    "return_pct",
    "holding_days",
    "commission",
]


def round_trips(trades: pd.DataFrame) -> pd.DataFrame:
    """Pair buy fills with later sell fills per ticker using FIFO matching.

    Args:
        trades: Fill log with columns ``date, ticker, direction, quantity,
            fill_price, commission`` (direction 1 = buy, -1 = sell).

    Returns:
        One row per (partial) round trip. Positions still open at the end of the
        log are not included. Commission is split pro rata across partial fills.
    """
    if trades is None or trades.empty:
        return pd.DataFrame(columns=ROUND_TRIP_COLUMNS)

    log = trades.sort_values("date", kind="stable")
    open_lots: dict[str, deque] = {}
    rows: list[dict] = []

    for row in log.itertuples(index=False):
        ticker = row.ticker
        qty = float(row.quantity)
        price = float(row.fill_price)
        commission = float(getattr(row, "commission", 0.0) or 0.0)
        per_share_comm = commission / qty if qty else 0.0
        lots = open_lots.setdefault(ticker, deque())

        if int(row.direction) == 1:
            lots.append({"date": row.date, "qty": qty, "price": price, "comm_ps": per_share_comm})
            continue
        if int(row.direction) != -1:
            continue

        remaining = qty
        while remaining > 1e-12 and lots:
            lot = lots[0]
            matched = min(remaining, lot["qty"])
            entry_value = matched * lot["price"]
            exit_value = matched * price
            comm = matched * (lot["comm_ps"] + per_share_comm)
            pnl = exit_value - entry_value - comm
            rows.append({
                "ticker": ticker,
                "entry_date": lot["date"],
                "exit_date": row.date,
                "quantity": matched,
                "entry_price": lot["price"],
                "exit_price": price,
                "pnl": pnl,
                "return_pct": pnl / entry_value if entry_value else 0.0,
                "holding_days": int((pd.Timestamp(row.date) - pd.Timestamp(lot["date"])).days),
                "commission": comm,
            })
            lot["qty"] -= matched
            remaining -= matched
            if lot["qty"] <= 1e-12:
                lots.popleft()

    if not rows:
        return pd.DataFrame(columns=ROUND_TRIP_COLUMNS)
    return pd.DataFrame(rows, columns=ROUND_TRIP_COLUMNS)


def trade_statistics(rt: pd.DataFrame) -> dict[str, float]:
    """Summary statistics over a round-trip DataFrame from :func:`round_trips`."""
    empty = {
        "n_trades": 0,
        "n_wins": 0,
        "n_losses": 0,
        "win_rate": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "avg_return_pct": 0.0,
        "profit_factor": 0.0,
        "expectancy": 0.0,
        "avg_holding_days": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "total_pnl": 0.0,
        "total_commission": 0.0,
        "max_consecutive_wins": 0,
        "max_consecutive_losses": 0,
    }
    if rt is None or rt.empty:
        return empty

    pnl = rt["pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    return {
        "n_trades": int(len(rt)),
        "n_wins": int(len(wins)),
        "n_losses": int(len(losses)),
        "win_rate": float(len(wins) / len(rt)),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "avg_return_pct": float(rt["return_pct"].mean()),
        "profit_factor": float(profit_factor),
        "expectancy": float(pnl.mean()),
        "avg_holding_days": float(rt["holding_days"].mean()),
        "best_trade": float(pnl.max()),
        "worst_trade": float(pnl.min()),
        "total_pnl": float(pnl.sum()),
        "total_commission": float(rt["commission"].sum()),
        "max_consecutive_wins": _max_streak(pnl.to_numpy() > 0),
        "max_consecutive_losses": _max_streak(pnl.to_numpy() < 0),
    }


def _max_streak(flags: np.ndarray) -> int:
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return int(best)
