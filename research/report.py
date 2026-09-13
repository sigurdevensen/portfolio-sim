"""Serialise a BatchResult to the JSON contract used by the web lab, plus its store."""
from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from evaluation.serialize import _clean
from research.batch import BatchResult
from web.store import JsonStore

TOP_NAVS = 10
HIST_BINS = 30


def _hist(values: np.ndarray, bins: int = HIST_BINS) -> dict[str, list[float]]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"counts": [], "edges": []}
    counts, edges = np.histogram(values, bins=bins)
    return {"counts": counts.astype(int).tolist(), "edges": edges.astype(float).tolist()}


def batch_to_dict(result: BatchResult, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """JSON-safe representation of a batch: summary, leaderboard, distributions, top NAVs."""
    lb = result.leaderboard
    rows = []
    for name, row in lb.iterrows():
        rec = {"name": str(name)}
        for k, v in row.items():
            if k == "params":
                rec[k] = dict(v)
            elif isinstance(v, (np.floating, float)):
                rec[k] = None if not math.isfinite(float(v)) else float(v)
            elif isinstance(v, (np.integer, int)) and not isinstance(v, bool):
                rec[k] = int(v)
            else:
                rec[k] = v
        rows.append(rec)

    top = list(lb.index[:TOP_NAVS])
    navs = {str(n): (result.navs[n] / result.navs[n].iloc[0] * 100).tolist() for n in top if n in result.navs}
    sharpes = lb["sharpe_full"].to_numpy(dtype=float)
    excess = lb["excess_sharpe_full"].to_numpy(dtype=float) if "excess_sharpe_full" in lb else sharpes
    bench_nav = None
    if result.benchmark_nav is not None and len(result.benchmark_nav):
        b = result.benchmark_nav
        bench_nav = (b / b.iloc[0] * 100).tolist()

    meta_out: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_algorithms": int(len(lb)),
        "config": asdict(result.config),
        **result.market_meta,
    }
    if meta:
        meta_out.update(meta)

    return _clean({
        "meta": meta_out,
        "summary": result.summary,
        "leaderboard": rows,
        "families": sorted(lb["family"].unique().tolist()),
        "reality_check_hist": _hist(result.edge.reality_check_distribution),
        "reality_check_observed": result.summary.get("reality_check_observed"),
        "pbo_logit_hist": _hist(result.edge.pbo_logits),
        "sharpe_hist": _hist(sharpes),
        "excess_sharpe_hist": _hist(excess),
        "benchmark_nav": bench_nav,
        "dates": [pd.Timestamp(d).isoformat() for d in result.returns.index],
        "navs": navs,
        "errors": dict(result.errors),
    })


class BatchStore(JsonStore):
    """Saved batches: ``reports/batches/<batch_id>/batch.json``."""

    FILENAME = "batch.json"
    ID_KEY = "batch_id"

    def _label(self, doc: dict[str, Any]) -> str:
        return "batch"

    def _summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        s = doc.get("summary", {}) or {}
        keys = ("n_algorithms", "n_strong", "n_candidate", "pbo", "reality_check_p", "expected_max_sharpe",
                "observed_max_sharpe", "best_is_name", "best_is_oos_sharpe")
        return {"summary": {k: s.get(k) for k in keys}}
