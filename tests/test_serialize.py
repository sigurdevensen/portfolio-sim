"""Tests for the JSON serialisation of a BacktestReport."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from backtesting.metrics import BacktestResult
from evaluation.evaluator import Evaluator
from evaluation.serialize import report_to_dict


def _report(n: int = 120, with_trades: bool = True, nan_price: bool = False):
    rng = np.random.default_rng(5)
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    nav = pd.Series(100_000 * np.cumprod(1 + rng.normal(0.0003, 0.01, n)), index=idx, name="NAV")
    trades = pd.DataFrame(columns=["date", "ticker", "direction", "quantity", "fill_price", "commission", "value", "cash_after"])
    if with_trades:
        trades = pd.DataFrame([
            {"date": idx[1], "ticker": "AAA", "direction": 1, "quantity": 5.0, "fill_price": 50.0,
             "commission": 0.25, "value": 250.0, "cash_after": 99_749.75},
            {"date": idx[30], "ticker": "AAA", "direction": -1, "quantity": 5.0, "fill_price": 55.0,
             "commission": 0.275, "value": 275.0, "cash_after": 100_024.475},
        ])
    prices = pd.DataFrame({"AAA": rng.uniform(40, 60, n), "BBB": rng.uniform(10, 20, n)}, index=idx)
    if nan_price:
        prices.iloc[3, 0] = np.nan
    bench = nav * 0.99
    result = BacktestResult(nav=nav, trades=trades, benchmark=bench)
    report = Evaluator().evaluate(result, strategy_name="unit", prices=prices, n_samples=20)
    return report, prices


def test_output_is_json_serialisable():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices, meta={"run_id": "r1", "strategy": "unit"})
    json.dumps(payload)


def test_top_level_keys():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices)
    for key in ("meta", "metrics", "risk", "trade_stats", "significance", "series",
                "prices", "trades", "round_trips", "monthly_returns", "recovery_periods"):
        assert key in payload, key


def test_meta_passthrough_and_defaults():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices, meta={"run_id": "abc", "extra": 1})
    assert payload["meta"]["run_id"] == "abc"
    assert payload["meta"]["extra"] == 1
    assert payload["meta"]["strategy"] == "unit"
    assert "created_at" in payload["meta"]


def test_series_aligned_and_iso_dates():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices)
    s = payload["series"]
    n = len(report.result.nav)
    assert len(s["dates"]) == n
    assert len(s["nav"]) == n
    assert len(s["drawdown"]) == n
    assert len(s["benchmark"]) == n
    assert len(s["returns"]) == n  # first element null
    assert s["returns"][0] is None
    assert s["dates"][0].startswith("2023-01-02")


def test_prices_aligned_to_dates_with_nan_as_null():
    report, prices = _report(nan_price=True)
    payload = report_to_dict(report, prices=prices)
    assert set(payload["prices"]) == {"AAA", "BBB"}
    assert len(payload["prices"]["AAA"]) == len(payload["series"]["dates"])
    assert payload["prices"]["AAA"][3] is None


def test_trades_and_round_trips_as_records():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices)
    assert len(payload["trades"]) == 2
    assert payload["trades"][0]["direction"] == 1
    assert isinstance(payload["trades"][0]["date"], str)
    assert len(payload["round_trips"]) == 1
    assert isinstance(payload["round_trips"][0]["entry_date"], str)


def test_monthly_returns_as_records():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices)
    rec = payload["monthly_returns"][0]
    assert set(rec) == {"year", "month", "ret"}


def test_significance_included_and_null_when_absent():
    report, prices = _report()
    payload = report_to_dict(report, prices=prices)
    assert payload["significance"]["n_samples"] == 20
    report.significance = None
    assert report_to_dict(report, prices=prices)["significance"] is None


def test_no_nan_anywhere():
    report, prices = _report(nan_price=True)
    payload = report_to_dict(report, prices=prices)

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, float):
            assert not math.isnan(x)
            assert not math.isinf(x)

    walk(payload)
