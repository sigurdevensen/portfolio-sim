"""Tests for the RunStore and the FastAPI platform app."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from web.app import create_app
from web.store import RunStore


def _run(run_id: str = "20260913-120000-momentum-abc123", strategy: str = "momentum", ret: float = 0.1) -> dict:
    return {
        "meta": {"run_id": run_id, "strategy": strategy, "created_at": "2026-09-13T12:00:00+00:00",
                 "tickers": ["AAA"], "start": "2023-01-02", "end": "2023-03-01"},
        "metrics": {"total_return": ret, "sharpe": 1.0, "max_drawdown": -0.1, "cagr": 0.2},
        "series": {"dates": ["2023-01-02T00:00:00+00:00"], "nav": [1.0]},
    }


# ── RunStore ───────────────────────────────────────────────────────────────

def test_store_save_returns_id_and_load_round_trips(tmp_path):
    store = RunStore(tmp_path)
    rid = store.save(_run())
    assert rid == "20260913-120000-momentum-abc123"
    assert store.load(rid)["metrics"]["total_return"] == 0.1
    assert (tmp_path / rid / "run.json").exists()


def test_store_generates_id_when_missing(tmp_path):
    store = RunStore(tmp_path)
    run = _run()
    del run["meta"]["run_id"]
    rid = store.save(run)
    assert "momentum" in rid
    assert store.load(rid)["meta"]["run_id"] == rid


def test_store_list_newest_first_with_summary(tmp_path):
    store = RunStore(tmp_path)
    a = _run("20260101-000000-a-000001", "a")
    b = _run("20260102-000000-b-000002", "b")
    b["meta"]["created_at"] = "2026-01-02T00:00:00+00:00"
    a["meta"]["created_at"] = "2026-01-01T00:00:00+00:00"
    store.save(a)
    store.save(b)
    listed = store.list()
    assert [r["run_id"] for r in listed] == [b["meta"]["run_id"], a["meta"]["run_id"]]
    assert listed[0]["metrics"]["total_return"] == 0.1
    assert "series" not in listed[0]


def test_store_delete_and_missing_raise(tmp_path):
    store = RunStore(tmp_path)
    rid = store.save(_run())
    store.delete(rid)
    with pytest.raises(KeyError):
        store.load(rid)
    with pytest.raises(KeyError):
        store.delete(rid)


def test_store_rejects_path_traversal(tmp_path):
    store = RunStore(tmp_path)
    with pytest.raises(KeyError):
        store.load("../etc/passwd")


# ── FastAPI app ────────────────────────────────────────────────────────────

def _fake_prices(tickers, start, end, use_cache=True):
    rng = np.random.default_rng(0)
    idx = pd.date_range("2023-01-02", periods=80, freq="B", tz="UTC")
    return pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 80)) for t in tickers}, index=idx)


@pytest.fixture
def client(tmp_path):
    app = create_app(RunStore(tmp_path))
    with patch("pipeline.pipeline.fetch_prices", side_effect=_fake_prices):
        with TestClient(app) as c:
            yield c


def _request(**overrides):
    body = {
        "strategy": "buy_and_hold", "params": {}, "tickers": ["AAA", "BBB"],
        "start": "2023-01-02", "end": "2023-04-30", "initial_capital": 10_000.0,
        "commission": 0.001, "slippage_bps": 5.0, "data_source": "yfinance",
        "benchmark": None, "execution_lag": 1, "significance": True, "n_samples": 20,
    }
    body.update(overrides)
    return body


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "report.js" in r.text


def test_static_report_js_served(client):
    r = client.get("/static/report.js")
    assert r.status_code == 200
    assert "renderReport" in r.text


def test_list_strategies(client):
    r = client.get("/api/strategies")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert "momentum" in names


def test_backtest_creates_run(client):
    r = client.post("/api/backtest", json=_request())
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["meta"]["run_id"]
    assert run["meta"]["strategy"] == "buy_and_hold"
    assert run["meta"]["tickers"] == ["AAA", "BBB"]
    assert run["meta"]["config"]["execution_lag"] == 1
    assert len(run["series"]["nav"]) == 80
    assert run["significance"]["n_samples"] == 20
    assert len(run["trades"]) == 2


def test_backtest_with_benchmark_adds_beta(client):
    r = client.post("/api/backtest", json=_request(benchmark="SPY"))
    assert r.status_code == 200, r.text
    assert "beta" in r.json()["metrics"]
    assert r.json()["series"]["benchmark"] is not None


def test_backtest_with_params(client):
    r = client.post("/api/backtest", json=_request(strategy="momentum", params={"lookback": 10, "top_n": 1}))
    assert r.status_code == 200, r.text
    assert r.json()["meta"]["params"] == {"lookback": 10, "top_n": 1}


def test_runs_listed_and_fetched(client):
    rid = client.post("/api/backtest", json=_request()).json()["meta"]["run_id"]
    listed = client.get("/api/runs").json()
    assert listed[0]["run_id"] == rid
    full = client.get(f"/api/runs/{rid}")
    assert full.status_code == 200
    assert full.json()["meta"]["run_id"] == rid


def test_missing_run_404(client):
    assert client.get("/api/runs/does-not-exist").status_code == 404


def test_delete_run(client):
    rid = client.post("/api/backtest", json=_request()).json()["meta"]["run_id"]
    assert client.delete(f"/api/runs/{rid}").status_code == 204
    assert client.get(f"/api/runs/{rid}").status_code == 404


def test_unknown_strategy_400(client):
    r = client.post("/api/backtest", json=_request(strategy="nope"))
    assert r.status_code == 400
    assert "Unknown strategy" in r.json()["detail"]


def test_bad_param_400(client):
    r = client.post("/api/backtest", json=_request(strategy="momentum", params={"lookback": "abc"}))
    assert r.status_code == 400


def test_data_error_502(tmp_path):
    app = create_app(RunStore(tmp_path))

    def boom(*a, **k):
        raise RuntimeError("LSEG session error: offline")

    with patch("pipeline.pipeline.fetch_prices", side_effect=boom):
        with TestClient(app) as c:
            r = c.post("/api/backtest", json=_request())
    assert r.status_code == 502
    assert "offline" in r.json()["detail"]


def test_run_report_html_written_alongside(client, tmp_path):
    rid = client.post("/api/backtest", json=_request()).json()["meta"]["run_id"]
    assert (tmp_path / rid / "report.html").exists()
    r = client.get(f"/runs/{rid}/report.html")
    assert r.status_code == 200
    assert "renderReport" in r.text


# ── Algorithm lab API ──────────────────────────────────────────────────────

from data.market import MarketData
from research.report import BatchStore


def _fake_market(tickers, start, end, use_cache=True, cache_dir=None):
    rng = np.random.default_rng(7)
    idx = pd.date_range("2021-01-04", periods=400, freq="B", tz="UTC")
    close = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, 400)) for t in tickers}, index=idx)
    m = MarketData.from_close(close)
    m.volume.loc[:, :] = rng.integers(500, 1500, size=close.shape).astype(float)
    return m


@pytest.fixture
def lab_client(tmp_path):
    app = create_app(RunStore(tmp_path / "runs"), BatchStore(tmp_path / "batches"))
    with patch("web.app.fetch_market_data", side_effect=_fake_market):
        with TestClient(app) as c:
            yield c


def _batch_request(**overrides):
    body = {"tickers": ["AAA", "BBB", "CCC"], "start": "2021-01-04", "end": "2022-12-31",
            "families": ["buy_and_hold", "sma_cross", "random"], "limit": 8, "n_boot": 100,
            "pbo_blocks": 8, "n_jobs": 1}
    body.update(overrides)
    return body


def test_list_algorithms(lab_client):
    r = lab_client.get("/api/algorithms")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 100
    assert "sma_cross" in body["families"]
    assert body["algorithms"][0]["name"]


def test_batch_endpoint_runs_and_saves(lab_client, tmp_path):
    r = lab_client.post("/api/batch", json=_batch_request())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["meta"]["batch_id"]
    assert d["meta"]["n_algorithms"] == 8
    assert len(d["leaderboard"]) == 8
    assert "pbo" in d["summary"]
    assert (tmp_path / "batches" / d["meta"]["batch_id"] / "batch.json").exists()
    assert (tmp_path / "batches" / d["meta"]["batch_id"] / "batch.html").exists()


def test_batches_listed_fetched_deleted(lab_client):
    bid = lab_client.post("/api/batch", json=_batch_request(limit=4)).json()["meta"]["batch_id"]
    listed = lab_client.get("/api/batches").json()
    assert listed[0]["batch_id"] == bid
    assert lab_client.get(f"/api/batches/{bid}").status_code == 200
    assert lab_client.get(f"/batches/{bid}/report.html").status_code == 200
    assert lab_client.delete(f"/api/batches/{bid}").status_code == 204
    assert lab_client.get(f"/api/batches/{bid}").status_code == 404


def test_batch_unknown_family_400(lab_client):
    r = lab_client.post("/api/batch", json=_batch_request(families=["nope"]))
    assert r.status_code == 400


def test_index_has_lab_tab(lab_client):
    assert "Algorithm lab" in lab_client.get("/").text
    assert lab_client.get("/static/batch.js").status_code == 200
