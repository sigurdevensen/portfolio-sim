"""Serialise a BacktestReport into one JSON-safe dict.

This dict is the single contract shared by the web API, the JSON run store and the
standalone HTML report. Every number is a plain float/int, NaN and +/-inf become
``null``, and every timestamp is an ISO-8601 string.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from evaluation.evaluator import BacktestReport


def report_to_dict(
    report: BacktestReport,
    prices: pd.DataFrame | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a report (and the prices it was run on) to a JSON-safe dict.

    Args:
        report: Evaluated report.
        prices: Price DataFrame used for the backtest; aligned to the NAV dates.
        meta: Free-form run metadata (run_id, params, config...). ``strategy`` and
            ``created_at`` are filled in when absent.
    """
    nav = report.result.nav
    dates = nav.index
    returns = nav.pct_change()

    meta_out: dict[str, Any] = {
        "strategy": report.strategy_name,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start": _iso(dates[0]) if len(dates) else None,
        "end": _iso(dates[-1]) if len(dates) else None,
    }
    if meta:
        meta_out.update(meta)

    benchmark = report.result.benchmark
    if benchmark is not None:
        benchmark = benchmark.reindex(dates)

    series = {
        "dates": [_iso(d) for d in dates],
        "nav": _floats(nav),
        "benchmark": _floats(benchmark) if benchmark is not None else None,
        "drawdown": _floats(report.drawdown_series.reindex(dates)),
        "returns": _floats(returns),
    }

    prices_out: dict[str, list[float | None]] | None = None
    if prices is not None:
        aligned = prices.reindex(dates)
        prices_out = {str(col): _floats(aligned[col]) for col in aligned.columns}

    return _clean({
        "meta": meta_out,
        "metrics": dict(report.metrics),
        "risk": {"var_95": report.var_95, "var_99": report.var_99, "cvar_95": report.cvar_95},
        "trade_stats": dict(report.trade_stats),
        "significance": report.significance.to_dict() if report.significance is not None else None,
        "series": series,
        "prices": prices_out,
        "trades": _records(report.result.trades),
        "round_trips": _records(report.round_trips),
        "monthly_returns": _monthly_records(report.monthly_returns),
        "recovery_periods": [
            {
                "peak_date": _iso(p.peak_date),
                "trough_date": _iso(p.trough_date),
                "recovery_date": _iso(p.recovery_date) if p.recovery_date is not None else None,
                "drawdown": p.drawdown,
                "duration_days": p.duration_days,
            }
            for p in report.recovery_periods
        ],
        "correlation": (
            {
                "tickers": [str(c) for c in report.correlation_matrix.columns],
                "matrix": report.correlation_matrix.to_numpy().tolist(),
            }
            if report.correlation_matrix is not None
            else None
        ),
    })


# ── helpers ────────────────────────────────────────────────────────────────

def _iso(ts: Any) -> str:
    return pd.Timestamp(ts).isoformat()


def _floats(s: pd.Series) -> list[float | None]:
    return [None if (v is None or (isinstance(v, float) and not math.isfinite(v))) else float(v)
            for v in s.astype(float).tolist()]


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = []
    for rec in df.to_dict(orient="records"):
        out.append({k: (_iso(v) if isinstance(v, (pd.Timestamp, datetime)) else v) for k, v in rec.items()})
    return out


def _monthly_records(table: pd.DataFrame) -> list[dict[str, Any]]:
    if table is None or table.empty:
        return []
    out = []
    for year, row in table.iterrows():
        for month, val in row.items():
            if val is None or (isinstance(val, float) and math.isnan(val)):
                continue
            out.append({"year": int(year), "month": int(month), "ret": float(val)})
    return out


def _clean(obj: Any) -> Any:
    """Recursively convert numpy scalars and non-finite floats to JSON-safe values."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_clean(v) for v in obj.tolist()]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return _iso(obj)
    return obj
