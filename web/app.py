"""FastAPI application for the portfolio-sim platform.

Routes
------
GET  /                      platform page (run form, run list, report viewer)
GET  /static/*              report.js, style.css, app.js
GET  /runs/{id}/report.html standalone report for a saved run
GET  /api/strategies        registered strategies and their parameters
GET  /api/runs              run summaries, newest first
GET  /api/runs/{id}         full run dict
DELETE /api/runs/{id}
POST /api/backtest          run + evaluate + save; returns the full run dict
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from evaluation.html_reporter import HTMLReporter
from pipeline.pipeline import Pipeline
from web.registry import build, strategy_specs
from web.store import RunStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "reports" / "runs"


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


def create_app(store: RunStore | None = None) -> FastAPI:
    store = store or RunStore(DEFAULT_RUNS_DIR)
    app = FastAPI(title="portfolio-sim", version="0.2.0")
    app.state.store = store
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/runs/{run_id}/report.html", response_class=HTMLResponse)
    def run_report(run_id: str) -> Any:
        try:
            folder = store.path(run_id)
        except KeyError:
            raise HTTPException(404, f"Run '{run_id}' not found")
        file = folder / "report.html"
        if not file.exists():
            try:
                HTMLReporter().write(store.load(run_id), folder)
            except KeyError:
                raise HTTPException(404, f"Run '{run_id}' not found")
        return FileResponse(file, media_type="text/html")

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
            start=req.start,
            end=req.end,
            data_source=req.data_source,
            initial_capital=req.initial_capital,
            commission=req.commission,
            slippage_bps=req.slippage_bps,
            benchmark=req.benchmark or None,
            execution_lag=req.execution_lag,
            rebalance=req.rebalance,
            max_weight=req.max_weight,
            risk_free_rate=req.risk_free_rate,
            significance=req.significance,
            n_samples=req.n_samples,
            run_id=run_id,
            params=req.params,
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

    return app


app = create_app()
