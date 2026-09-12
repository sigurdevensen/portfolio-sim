"""Pipeline: the public API wiring data feed, backtest engine, and evaluation together."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.metrics import BacktestResult
from evaluation.evaluator import BacktestReport, Evaluator
from evaluation.reporter import MarkdownReporter
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


class Pipeline:
    """Composable pipeline for strategy backtesting and evaluation.

    Usage::

        result = (
            Pipeline(
                strategy=MomentumStrategy(lookback=60, top_n=5),
                tickers=["EQNR.OL", "DNB.OL"],
                start="2018-01-01",
                end="2024-12-31",
                data_source="lseg",
                initial_capital=1_000_000,
            )
            .run()
            .evaluate()
            .report(output="reports/")
        )
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
    ) -> None:
        self.strategy = strategy
        self._cfg = _PipelineConfig(
            tickers=tickers,
            start=start,
            end=end,
            initial_capital=initial_capital,
            commission=commission,
            slippage_bps=slippage_bps,
            data_source=data_source,
        )
        self._result: BacktestResult | None = None
        self._report: BacktestReport | None = None
        self._prices: pd.DataFrame | None = None

    def run(self) -> "Pipeline":
        """Fetch data and run the backtest simulation. Returns self for chaining."""
        self._prices = self._fetch_prices()
        engine_cfg = BacktestConfig(
            start=self._cfg.start,
            end=self._cfg.end,
            initial_capital=self._cfg.initial_capital,
            commission=self._cfg.commission,
            slippage=self._cfg.slippage_bps / 10_000,
        )
        engine = BacktestEngine(engine_cfg)
        self._result = engine.run(self.strategy, self._prices)
        return self

    def evaluate(self, benchmark: pd.Series | None = None) -> "Pipeline":
        """Compute metrics and risk statistics. Call after run(). Returns self."""
        if self._result is None:
            raise RuntimeError("Call run() before evaluate()")
        evaluator = Evaluator()
        self._report = evaluator.evaluate(
            self._result,
            strategy_name=self.strategy.name,
            benchmark=benchmark,
            prices=self._prices,
        )
        return self

    def report(self, output: str | Path = "reports/") -> "Pipeline":
        """Write markdown report and chart images to output directory. Returns self."""
        if self._report is None:
            raise RuntimeError("Call evaluate() before report()")
        MarkdownReporter().write(self._report, output_dir=output)
        return self

    def get_result(self) -> BacktestResult:
        """Return the BacktestResult (available after run())."""
        if self._result is None:
            raise RuntimeError("Call run() first")
        return self._result

    def get_report(self) -> BacktestReport:
        """Return the BacktestReport (available after evaluate())."""
        if self._report is None:
            raise RuntimeError("Call evaluate() first")
        return self._report

    def _fetch_prices(self) -> pd.DataFrame:
        if self._cfg.data_source == "lseg":
            from data.lseg import LSEGDataFeed
            return LSEGDataFeed().fetch_prices(self._cfg.tickers, self._cfg.start, self._cfg.end)
        from data.loader import fetch_prices
        return fetch_prices(self._cfg.tickers, self._cfg.start, self._cfg.end)
