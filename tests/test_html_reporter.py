"""Tests for the self-contained interactive HTML report."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from backtesting.metrics import BacktestResult
from evaluation.evaluator import Evaluator
from evaluation.html_reporter import HTMLReporter
from evaluation.serialize import report_to_dict


def _run_dict():
    rng = np.random.default_rng(2)
    idx = pd.date_range("2023-01-02", periods=80, freq="B", tz="UTC")
    nav = pd.Series(100_000 * np.cumprod(1 + rng.normal(0.0003, 0.01, 80)), index=idx)
    trades = pd.DataFrame(columns=["date", "ticker", "direction", "quantity", "fill_price", "commission", "value", "cash_after"])
    report = Evaluator().evaluate(BacktestResult(nav=nav, trades=trades), strategy_name="html_unit", n_samples=10)
    prices = pd.DataFrame({"AAA": rng.uniform(90, 110, 80)}, index=idx)
    return report_to_dict(report, prices=prices, meta={"run_id": "r-html"})


def test_write_returns_existing_report_html(tmp_path):
    path = HTMLReporter().write(_run_dict(), tmp_path)
    assert path.exists()
    assert path.name == "report.html"


def test_report_html_embeds_payload_and_renderer(tmp_path):
    run = _run_dict()
    html = HTMLReporter().write(run, tmp_path).read_text(encoding="utf-8")
    assert 'id="run-data"' in html
    assert "renderReport" in html
    assert "plotly" in html.lower()
    assert "html_unit" in html


def test_embedded_payload_round_trips(tmp_path):
    run = _run_dict()
    html = HTMLReporter().write(run, tmp_path).read_text(encoding="utf-8")
    start = html.index('id="run-data"')
    start = html.index(">", start) + 1
    end = html.index("</script>", start)
    payload = json.loads(html[start:end])
    assert payload["meta"]["run_id"] == "r-html"
    assert len(payload["series"]["nav"]) == 80


def test_payload_with_script_tag_in_strategy_name_is_escaped(tmp_path):
    run = _run_dict()
    run["meta"]["strategy"] = "</script><script>alert(1)</script>"
    html = HTMLReporter().write(run, tmp_path).read_text(encoding="utf-8")
    assert "</script><script>alert(1)" not in html


def test_render_to_string_without_writing():
    html = HTMLReporter().render(_run_dict())
    assert html.startswith("<!doctype html>")
