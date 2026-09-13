"""RunStore: persists serialised backtest runs as JSON under a root directory."""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_SUMMARY_METRICS = ("total_return", "cagr", "sharpe", "sortino", "max_drawdown", "annualised_volatility")


class RunStore:
    """One directory per run: ``<root>/<run_id>/run.json`` (+ any report files)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id(strategy: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^A-Za-z0-9]+", "_", strategy).strip("_") or "run"
        return f"{stamp}-{slug}-{secrets.token_hex(3)}"

    def path(self, run_id: str) -> Path:
        if not _SAFE_ID.match(run_id or "") or run_id in {".", ".."}:
            raise KeyError(run_id)
        return self.root / run_id

    def save(self, run: dict[str, Any]) -> str:
        meta = run.setdefault("meta", {})
        run_id = meta.get("run_id") or self.new_id(meta.get("strategy", "run"))
        meta["run_id"] = run_id
        folder = self.path(run_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "run.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
        return run_id

    def load(self, run_id: str) -> dict[str, Any]:
        file = self.path(run_id) / "run.json"
        if not file.exists():
            raise KeyError(run_id)
        return json.loads(file.read_text(encoding="utf-8"))

    def delete(self, run_id: str) -> None:
        folder = self.path(run_id)
        if not (folder / "run.json").exists():
            raise KeyError(run_id)
        for child in folder.iterdir():
            child.unlink()
        folder.rmdir()

    def list(self) -> list[dict[str, Any]]:
        """Summaries (meta + headline metrics) sorted newest first."""
        out = []
        for file in self.root.glob("*/run.json"):
            try:
                run = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            meta = dict(run.get("meta", {}))
            meta.setdefault("run_id", file.parent.name)
            metrics = run.get("metrics", {}) or {}
            meta["metrics"] = {k: metrics.get(k) for k in _SUMMARY_METRICS if k in metrics}
            meta["n_trades"] = (run.get("trade_stats") or {}).get("n_trades")
            out.append(meta)
        out.sort(key=lambda m: (m.get("created_at") or "", m["run_id"]), reverse=True)
        return out
