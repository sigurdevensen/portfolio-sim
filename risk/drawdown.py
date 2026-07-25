"""Drawdown analysis utilities."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class RecoveryPeriod:
    peak_date: pd.Timestamp
    trough_date: pd.Timestamp
    recovery_date: pd.Timestamp | None
    drawdown: float
    duration_days: int


def drawdown_series(nav: pd.Series) -> pd.Series:
    """Return the drawdown at each point as a fraction of the rolling peak."""
    rolling_max = nav.cummax()
    return (nav - rolling_max) / rolling_max


def max_drawdown(nav: pd.Series) -> float:
    return float(drawdown_series(nav).min())


def recovery_periods(nav: pd.Series, threshold: float = -0.05) -> list[RecoveryPeriod]:
    """Identify all drawdown episodes deeper than threshold."""
    dd = drawdown_series(nav)
    periods: list[RecoveryPeriod] = []

    in_drawdown = False
    peak_date = trough_date = nav.index[0]
    trough_val = 0.0

    for date, val in dd.items():
        if not in_drawdown and val < threshold:
            in_drawdown = True
            peak_date = nav.index[nav.index.get_loc(date) - 1] if nav.index.get_loc(date) > 0 else date
            trough_date = date
            trough_val = val
        elif in_drawdown:
            if val < trough_val:
                trough_date = date
                trough_val = val
            elif val >= 0.0:
                periods.append(RecoveryPeriod(
                    peak_date=peak_date,
                    trough_date=trough_date,
                    recovery_date=date,
                    drawdown=trough_val,
                    duration_days=(date - peak_date).days,
                ))
                in_drawdown = False

    if in_drawdown:
        periods.append(RecoveryPeriod(
            peak_date=peak_date,
            trough_date=trough_date,
            recovery_date=None,
            drawdown=trough_val,
            duration_days=(nav.index[-1] - peak_date).days,
        ))

    return periods
