"""Pipeline: the public API wiring data feed, backtest engine, and evaluation together."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.metrics import BacktestResult
from data.loader import fetch_prices
from evaluation.evaluator import BacktestReport, Evaluator
from evaluation.html_reporter import HTMLReporter
from evaluation.reporter import MarkdownReporter
from evaluation.serialize import report_to_dict
from strategies.base import Strategy


@dataclass
class _PipelineConfig:
    tickers: list[str]
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
    n_samples: int = 1000


class Pipeline:
    """Composable pipeline for strategy backtesting and evaluation.

    Usage::

        pipeline = (
            Pipeline(
                strategy=Momentum(lookback=60, top_n=5),
                tickers=["EQNR.OL", "DNB.OL"],
                start="2018-01-01",
                end="2024-12-31",
                benchmark="^OSEBX",
                initial_capital=1_000_000,
            )
            .run()
            .evaluate()
            .report(output="reports/momentum")
        )
        run_dict = pipeline.to_dict()   # JSON-safe, feeds the web UI
    """

    def __init__(
        self,
        strategy: Strategy,
        tickers: list[str],
        start: str,
        end: str,
        data_source: str = "yfinance",
        initial_capital: float = 1_000_000.0,
        commission: float = 0.001,
        slippage_bps: float = 5.0,
        benchmark: str | None = None,
        execution_lag: int = 1,
        rebalance: bool = True,
        max_weight: float | None = None,
        risk_free_rate: float = 0.0,
        significance: bool = True,
        n_samples: int = 1000,
        run_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.strategy = strategy
        self.run_id = run_id
        self.params = params if params is not None else _strategy_params(strategy)
        self._cfg = _PipelineConfig(
            tickers=list(tickers),
            start=start,
            end=end,
            initial_capital=initial_capital,
            commission=commission,
            slippage_bps=slippage_bps,
            data_source=data_source,
            benchmark=benchmark,
            execution_lag=execution_lag,
            rebalance=rebalance,
            max_weight=max_weight,
            risk_free_rate=risk_free_rate,
            significance=significance,
            n_samples=n_samples,
        )
        self.engine_config = BacktestConfig(
            start=start,
            end=end,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage_bps / 10_000,
            execution_lag=execution_lag,
            rebalance=rebalance,
            max_weight=max_weight,
            risk_free_rate=risk_free_rate,
        )
        self._result: BacktestResult | None = None
        self._report: BacktestReport | None = None
        self._prices: pd.DataFrame | None = None
        self._benchmark: pd.Series | None = None

    # ── stages ─────────────────────────────────────────────────────────────

    def run(self) -> "Pipeline":
        """Fetch data and run the backtest simulation. Returns self for chaining."""
        self._prices = self._fetch(self._cfg.tickers)
        if self._cfg.benchmark:
            bench_df = self._fetch([self._cfg.benchmark])
            self._benchmark = bench_df.iloc[:, 0].rename(self._cfg.benchmark)
        engine = BacktestEngine(self.engine_config)
        self._result = engine.run(self.strategy, self._prices, benchmark=self._benchmark)
        return self

    def evaluate(self, benchmark: pd.Series | None = None) -> "Pipeline":
        """Compute metrics, trade stats and significance. Call after run(). Returns self."""
        if self._result is None:
            raise RuntimeError("Call run() before evaluate()")
        self._report = Evaluator().evaluate(
            self._result,
            strategy_name=self.strategy.name,
            benchmark=benchmark,
            prices=self._prices,
            significance=self._cfg.significance,
            n_samples=self._cfg.n_samples,
        )
        return self

    def report(self, output: str | Path = "reports/") -> "Pipeline":
        """Write report.md (+ PNGs), report.html and run.json to ``output``. Returns self."""
        if self._report is None:
            raise RuntimeError("Call evaluate() before report()")
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        MarkdownReporter().write(self._report, output_dir=output)
        run = self.to_dict()
        HTMLReporter().write(run, output_dir=output)
        (output / "run.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
        return self

    # ── accessors ──────────────────────────────────────────────────────────

    def get_result(self) -> BacktestResult:
        if self._result is None:
            raise RuntimeError("Call run() first")
        return self._result

    def get_report(self) -> BacktestReport:
        if self._report is None:
            raise RuntimeError("Call evaluate() first")
        return self._report

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict of the evaluated run (see evaluation.serialize)."""
        report = self.get_report()
        if self.run_id is None:
            from web.store import RunStore
            self.run_id = RunStore.new_id(self.strategy.name)
        cfg = asdict(self._cfg)
        meta = {
            "run_id": self.run_id,
            "strategy": self.strategy.name,
            "params": self.params,
            "tickers": self._cfg.tickers,
            "benchmark": self._cfg.benchmark,
            "data_source": self._cfg.data_source,
            "requested_start": self._cfg.start,
            "requested_end": self._cfg.end,
            "config": {
                k: cfg[k]
                for k in ("initial_capital", "commission", "slippage_bps", "execution_lag",
                          "rebalance", "max_weight", "risk_free_rate", "significance", "n_samples")
            },
        }
        return report_to_dict(report, prices=self._prices, meta=meta)

    # ── internals ──────────────────────────────────────────────────────────

    def _fetch(self, tickers: list[str]) -> pd.DataFrame:
        if self._cfg.data_source == "lseg":
            from data.lseg import LSEGDataFeed
            return LSEGDataFeed().fetch_prices(tickers, self._cfg.start, self._cfg.end)
        return fetch_prices(tickers, self._cfg.start, self._cfg.end)


def _strategy_params(strategy: Strategy) -> dict[str, Any]:
    """Best-effort snapshot of a strategy's constructor parameters from its attributes."""
    import inspect
    out: dict[str, Any] = {}
    try:
        for name in inspect.signature(type(strategy).__init__).parameters:
            if name != "self" and hasattr(strategy, name):
                out[name] = getattr(strategy, name)
    except (TypeError, ValueError):
        pass
    return out
