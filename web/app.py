"""FastAPI application for the portfolio-sim platform.

Routes
------
GET  /                        platform page (Backtest and Algorithm lab tabs)
GET  /static/*                report.js, batch.js, app.js, style.css
GET  /runs/{id}/report.html   standalone report for a saved run
GET  /batches/{id}/report.html standalone report for a saved batch
GET  /api/strategies          registered strategies and their parameters
GET  /api/runs, /api/runs/{id}, DELETE /api/runs/{id}
POST /api/backtest            run + evaluate + save one strategy
GET  /api/algorithms          the fixed-parameter algorithm library
GET  /api/batches, /api/batches/{id}, DELETE /api/batches/{id}
POST /api/batch               test many algorithms at once with overfitting controls
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from data.market import MarketData, fetch_market_data
from evaluation.html_reporter import BatchHTMLReporter, HTMLReporter
from pipeline.pipeline import Pipeline
from research.batch import BatchConfig, run_batch
from research.library import ALGORITHMS, families, filter_algorithms, library_for
from research.report import BatchStore, batch_to_dict
from research.universes import UNIVERSES, load_universe
from web.registry import build, strategy_specs
from web.store import RunStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
DEFAULT_RUNS_DIR = REPORTS_DIR / "runs"
DEFAULT_BATCHES_DIR = REPORTS_DIR / "batches"


class BacktestRequest(BaseModel):
    strategy: str
    params: dict[str, Any] = Field(default_factory=dict)
    tickers: list[str] = Field(min_length=1)
    start: str
    end: str
    initial_capital: float = 1_000_000.0
    commission: float = 0.001
    slippage_bps: float = 5.0
    data_source: str = "yfinance"
    benchmark: str | None = None
    execution_lag: int = 1
    rebalance: bool = True
    max_weight: float | None = None
    risk_free_rate: float = 0.0
    significance: bool = True
    n_samples: int = Field(default=1000, ge=10, le=20_000)


class BatchRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    universe: str | None = None
    start: str
    end: str
    families: list[str] | None = None
    data_types: list[str] | None = None
    names: list[str] | None = None
    limit: int | None = Field(default=None, ge=1)
    initial_capital: float = 1_000_000.0
    commission: float = 0.001
    slippage_bps: float = 5.0
    execution_lag: int = 1
    rebalance: bool = True
    is_fraction: float = Field(default=0.6, gt=0.2, lt=0.9)
    n_boot: int = Field(default=1000, ge=50, le=20_000)
    pbo_blocks: int = Field(default=16, ge=2, le=20)
    min_trades: int = Field(default=20, ge=0)
    n_jobs: int = Field(default=1, ge=0, le=64)
    data_source: str = "yfinance"


def _load_market(tickers: list[str], start: str, end: str, data_source: str) -> MarketData:
    if data_source == "lseg":
        from data.lseg import LSEGDataFeed
        return MarketData.from_close(LSEGDataFeed().fetch_prices(tickers, start, end))
    return fetch_market_data(tickers, start, end)


def create_app(store: RunStore | None = None, batch_store: BatchStore | None = None) -> FastAPI:
    store = store or RunStore(DEFAULT_RUNS_DIR)
    batch_store = batch_store or BatchStore(DEFAULT_BATCHES_DIR)
    app = FastAPI(title="portfolio-sim", version="0.3.0")
    app.state.store = store
    app.state.batch_store = batch_store
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    # ── single runs ───────────────────────────────────────────────────────

    @app.get("/runs/{run_id}/report.html", response_class=HTMLResponse)
    def run_report(run_id: str) -> Any:
        return _report_file(store, run_id, HTMLReporter())

    @app.get("/api/strategies")
    def strategies() -> list[dict[str, Any]]:
        return strategy_specs()

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, Any]]:
        return store.list()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return store.load(run_id)
        except KeyError:
            raise HTTPException(404, f"Run '{run_id}' not found")

    @app.delete("/api/runs/{run_id}", status_code=204)
    def delete_run(run_id: str) -> Response:
        try:
            store.delete(run_id)
        except KeyError:
            raise HTTPException(404, f"Run '{run_id}' not found")
        return Response(status_code=204)

    @app.post("/api/backtest")
    def backtest(req: BacktestRequest) -> dict[str, Any]:
        try:
            strategy = build(req.strategy, req.params)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        run_id = store.new_id(req.strategy)
        pipeline = Pipeline(
            strategy=strategy,
            tickers=[t.strip() for t in req.tickers if t.strip()],
            start=req.start, end=req.end, data_source=req.data_source,
            initial_capital=req.initial_capital, commission=req.commission, slippage_bps=req.slippage_bps,
            benchmark=req.benchmark or None, execution_lag=req.execution_lag, rebalance=req.rebalance,
            max_weight=req.max_weight, risk_free_rate=req.risk_free_rate,
            significance=req.significance, n_samples=req.n_samples, run_id=run_id, params=req.params,
        )
        try:
            pipeline.run().evaluate()
        except RuntimeError as exc:  # data feed problems
            raise HTTPException(502, str(exc))
        except (ValueError, KeyError) as exc:  # bad dates, empty data, bad tickers
            raise HTTPException(400, str(exc))

        run = pipeline.to_dict()
        store.save(run)
        HTMLReporter().write(run, store.path(run_id))
        return run

    # ── algorithm lab ─────────────────────────────────────────────────────

    @app.get("/api/algorithms")
    def algorithms(universe: str | None = None) -> dict[str, Any]:
        lib = library_for(universe) if universe in UNIVERSES else list(ALGORITHMS)
        return {
            "count": len(lib),
            "families": sorted({a.family for a in lib}),
            "data_types": sorted({a.data_type for a in lib}),
            "algorithms": [a.to_dict() for a in lib],
            "universes": {k: {"description": v["description"], "tickers": v["tickers"],
                              "default_start": v["default_start"]} for k, v in UNIVERSES.items()},
        }

    @app.get("/api/batches")
    def list_batches() -> list[dict[str, Any]]:
        return batch_store.list()

    @app.get("/api/batches/{batch_id}")
    def get_batch(batch_id: str) -> dict[str, Any]:
        try:
            return batch_store.load(batch_id)
        except KeyError:
            raise HTTPException(404, f"Batch '{batch_id}' not found")

    @app.delete("/api/batches/{batch_id}", status_code=204)
    def delete_batch(batch_id: str) -> Response:
        try:
            batch_store.delete(batch_id)
        except KeyError:
            raise HTTPException(404, f"Batch '{batch_id}' not found")
        return Response(status_code=204)

    @app.get("/batches/{batch_id}/report.html", response_class=HTMLResponse)
    def batch_report(batch_id: str) -> Any:
        return _report_file(batch_store, batch_id, BatchHTMLReporter())

    @app.post("/api/batch")
    def batch(req: BatchRequest) -> dict[str, Any]:
        universe = req.universe or None
        if universe is not None and universe not in UNIVERSES:
            raise HTTPException(400, f"Unknown universe '{universe}'. Available: {sorted(UNIVERSES)}")
        known = {a.family for a in library_for(universe)}
        if req.families:
            unknown = sorted(set(req.families) - known)
            if unknown:
                raise HTTPException(400, f"Unknown families: {unknown}. Available: {sorted(known)}")
        specs = filter_algorithms(families=req.families, data_types=req.data_types, names=req.names,
                                  limit=req.limit, universe=universe)
        if not specs:
            raise HTTPException(400, "No algorithms match the requested filter")
        if req.pbo_blocks % 2:
            raise HTTPException(400, "pbo_blocks must be even")

        tickers = [t.strip() for t in req.tickers if t.strip()]
        if not tickers and universe is None:
            raise HTTPException(400, "Provide tickers or a universe")
        try:
            if universe is not None:
                market = load_universe(universe, start=req.start, end=req.end)
                tickers = market.tickers
            else:
                market = _load_market(tickers, req.start, req.end, req.data_source)
        except RuntimeError as exc:
            raise HTTPException(502, str(exc))
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc))

        cfg = BatchConfig(
            start=req.start, end=req.end, initial_capital=req.initial_capital, commission=req.commission,
            slippage_bps=req.slippage_bps, execution_lag=req.execution_lag, rebalance=req.rebalance,
            is_fraction=req.is_fraction, n_boot=req.n_boot, pbo_blocks=req.pbo_blocks, min_trades=req.min_trades,
        )
        try:
            result = run_batch(specs, market, cfg, n_jobs=req.n_jobs)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(400, str(exc))

        batch_id = batch_store.new_id("batch")
        doc = batch_to_dict(result, meta={"batch_id": batch_id, "tickers": tickers, "data_source": req.data_source,
                                          "universe": universe})
        batch_store.save(doc)
        BatchHTMLReporter().write(doc, batch_store.path(batch_id))
        return doc

    return app


def _report_file(store, doc_id: str, reporter) -> FileResponse:
    try:
        folder = store.path(doc_id)
        file = folder / "report.html"
        if not file.exists():
            reporter.write(store.load(doc_id), folder)
    except KeyError:
        raise HTTPException(404, f"'{doc_id}' not found")
    return FileResponse(file, media_type="text/html")


app = create_app()
