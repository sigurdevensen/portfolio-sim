"""JSON document stores for saved runs (and, via subclassing, batches)."""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_SUMMARY_METRICS = ("total_return", "cagr", "sharpe", "sortino", "max_drawdown", "annualised_volatility")


class JsonStore:
    """One directory per document: ``<root>/<id>/<FILENAME>`` (+ any report files)."""

    FILENAME = "doc.json"
    ID_KEY = "id"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id(label: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_") or "doc"
        return f"{stamp}-{slug}-{secrets.token_hex(3)}"

    def path(self, doc_id: str) -> Path:
        if not _SAFE_ID.match(doc_id or "") or doc_id in {".", ".."}:
            raise KeyError(doc_id)
        return self.root / doc_id

    def save(self, doc: dict[str, Any]) -> str:
        meta = doc.setdefault("meta", {})
        doc_id = meta.get(self.ID_KEY) or self.new_id(self._label(doc))
        meta[self.ID_KEY] = doc_id
        meta.setdefault("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        folder = self.path(doc_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / self.FILENAME).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return doc_id

    def load(self, doc_id: str) -> dict[str, Any]:
        file = self.path(doc_id) / self.FILENAME
        if not file.exists():
            raise KeyError(doc_id)
        return json.loads(file.read_text(encoding="utf-8"))

    def delete(self, doc_id: str) -> None:
        folder = self.path(doc_id)
        if not (folder / self.FILENAME).exists():
            raise KeyError(doc_id)
        for child in folder.iterdir():
            child.unlink()
        folder.rmdir()

    def list(self) -> list[dict[str, Any]]:
        """Summaries sorted newest first."""
        out = []
        for file in self.root.glob(f"*/{self.FILENAME}"):
            try:
                doc = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            meta = dict(doc.get("meta", {}))
            meta.setdefault(self.ID_KEY, file.parent.name)
            meta.update(self._summary(doc))
            out.append(meta)
        out.sort(key=lambda m: (m.get("created_at") or "", m[self.ID_KEY]), reverse=True)
        return out

    # hooks
    def _label(self, doc: dict[str, Any]) -> str:
        return "doc"

    def _summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {}


class RunStore(JsonStore):
    """Single-strategy backtest runs: ``reports/runs/<run_id>/run.json``."""

    FILENAME = "run.json"
    ID_KEY = "run_id"

    def _label(self, doc: dict[str, Any]) -> str:
        return doc.get("meta", {}).get("strategy", "run")

    def _summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        metrics = doc.get("metrics", {}) or {}
        return {
            "metrics": {k: metrics.get(k) for k in _SUMMARY_METRICS if k in metrics},
            "n_trades": (doc.get("trade_stats") or {}).get("n_trades"),
        }
