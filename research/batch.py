"""Batch runner: backtest many algorithms on one MarketData and assess their edge."""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.trades import round_trips
from data.market import MarketData
from research.edge import EdgeReport, assess
from research.library import AlgoSpec, build_algorithm
from strategies.buy_and_hold import BuyAndHold


@dataclass
class BatchConfig:
    start: str
    end: str
    initial_capital: float = 1_000_000.0
    commission: float = 0.001
    slippage_bps: float = 5.0
    execution_lag: int = 1
    rebalance: bool = True
    max_weight: float | None = None
    risk_free_rate: float = 0.0
    is_fraction: float = 0.6
    n_boot: int = 1000
    seed: int = 0
    pbo_blocks: int = 16
    min_trades: int = 20
    sizing: str = "fixed"          # see BacktestConfig.sizing
    prior_trials: int = 0          # algorithms tried in earlier rounds/configurations, added to N

    def engine_config(self) -> BacktestConfig:
        return BacktestConfig(
            start=self.start, end=self.end, initial_capital=self.initial_capital,
            commission=self.commission, slippage=self.slippage_bps / 10_000,
            execution_lag=self.execution_lag, rebalance=self.rebalance,
            max_weight=self.max_weight, risk_free_rate=self.risk_free_rate, sizing=self.sizing,
        )


@dataclass
class BatchResult:
    specs: list[AlgoSpec]
    config: BatchConfig
    returns: pd.DataFrame          # T x N daily strategy returns
    navs: pd.DataFrame             # T x N NAV
    leaderboard: pd.DataFrame      # edge leaderboard joined with spec info
    summary: dict[str, Any]
    errors: dict[str, str]
    edge: EdgeReport
    market_meta: dict[str, Any] = field(default_factory=dict)
    benchmark: pd.Series | None = None      # daily returns of equal-weight buy-and-hold
    benchmark_nav: pd.Series | None = None


# ── single-algorithm worker ───────────────────────────────────────────────

_WORKER_MARKET: MarketData | None = None
_WORKER_CFG: BacktestConfig | None = None


def _init_worker(market: MarketData, cfg: BacktestConfig) -> None:
    global _WORKER_MARKET, _WORKER_CFG
    _WORKER_MARKET = market
    _WORKER_CFG = cfg


def _run_spec_with(spec: AlgoSpec, market: MarketData, cfg: BacktestConfig) -> dict[str, Any]:
    try:
        strategy = build_algorithm(spec)
        result = BacktestEngine(cfg).run(strategy, market.close, market=market)
        rt = round_trips(result.trades)
        return {
            "name": spec.name,
            "nav": result.nav.to_numpy(dtype=float),
            "index": result.nav.index,
            "n_trades": int(len(rt)),
            "n_fills": int(len(result.trades)),
            "n_stops": int((result.trades["reason"].isin(["stop_loss", "take_profit", "trailing_stop"])).sum()) if len(result.trades) else 0,
            "error": None,
        }
    except Exception as exc:  # keep the batch going; report per algorithm
        return {"name": spec.name, "nav": None, "index": None, "n_trades": 0, "n_fills": 0, "n_stops": 0,
                "error": f"{type(exc).__name__}: {exc}"}


def _run_spec_pooled(spec: AlgoSpec) -> dict[str, Any]:
    assert _WORKER_MARKET is not None and _WORKER_CFG is not None
    return _run_spec_with(spec, _WORKER_MARKET, _WORKER_CFG)


# ── batch ─────────────────────────────────────────────────────────────────

def run_batch(
    specs: list[AlgoSpec],
    market: MarketData,
    config: BatchConfig,
    n_jobs: int = 1,
    progress: Callable[[int, int, str], None] | None = None,
) -> BatchResult:
    """Backtest every spec on ``market`` and assess the set for edge.

    Args:
        specs: Algorithms to test (see ``research.library``).
        market: OHLCV data shared by all algorithms.
        config: Costs, execution and statistics settings.
        n_jobs: Worker processes (1 = run inline). ``0``/``None`` = CPU count.
        progress: Optional callback ``(done, total, name)``.
    """
    engine_cfg = config.engine_config()
    market = market.slice(config.start, config.end)
    outputs: list[dict[str, Any]] = []

    if not n_jobs or n_jobs < 1:
        n_jobs = os.cpu_count() or 1
    if n_jobs == 1 or len(specs) <= 1:
        for i, spec in enumerate(specs):
            outputs.append(_run_spec_with(spec, market, engine_cfg))
            if progress:
                progress(i + 1, len(specs), spec.name)
    else:
        with ProcessPoolExecutor(max_workers=min(n_jobs, len(specs)), initializer=_init_worker,
                                 initargs=(market, engine_cfg)) as pool:
            for i, out in enumerate(pool.map(_run_spec_pooled, specs, chunksize=2)):
                outputs.append(out)
                if progress:
                    progress(i + 1, len(specs), out["name"])

    errors = {o["name"]: o["error"] for o in outputs if o["error"]}
    good = [o for o in outputs if not o["error"]]
    if not good:
        raise RuntimeError("No algorithm completed successfully: " + "; ".join(f"{k}: {v}" for k, v in errors.items()))

    index = good[0]["index"]
    navs = pd.DataFrame({o["name"]: pd.Series(o["nav"], index=o["index"]).reindex(index) for o in good}, index=index)
    returns = navs.pct_change().fillna(0.0)
    n_trades = pd.Series({o["name"]: o["n_trades"] for o in good})

    # The passive alternative: equal-weight buy-and-hold of the same universe, same
    # costs and execution. Edge is measured in excess of it so beta is not "skill".
    bench_result = BacktestEngine(engine_cfg).run(BuyAndHold(), market.close, market=market)
    benchmark_nav = bench_result.nav.reindex(index)
    benchmark = benchmark_nav.pct_change().fillna(0.0)

    edge = assess(
        returns, n_trades=n_trades, benchmark=benchmark, is_fraction=config.is_fraction,
        n_boot=config.n_boot, seed=config.seed, pbo_blocks=config.pbo_blocks, min_trades=config.min_trades,
        prior_trials=config.prior_trials,
    )

    by_name = {s.name: s for s in specs}
    info = pd.DataFrame({
        "family": [by_name[n].family for n in edge.leaderboard.index],
        "data_type": [by_name[n].data_type for n in edge.leaderboard.index],
        "params": [dict(by_name[n].params) for n in edge.leaderboard.index],
        "stop_loss": [by_name[n].stop_loss for n in edge.leaderboard.index],
        "take_profit": [by_name[n].take_profit for n in edge.leaderboard.index],
        "trailing_stop": [by_name[n].trailing_stop for n in edge.leaderboard.index],
        "n_fills": [next(o["n_fills"] for o in good if o["name"] == n) for n in edge.leaderboard.index],
        "n_stops": [next(o["n_stops"] for o in good if o["name"] == n) for n in edge.leaderboard.index],
    }, index=edge.leaderboard.index)
    leaderboard = pd.concat([info, edge.leaderboard], axis=1)

    summary = dict(edge.summary)
    summary["n_requested"] = len(specs)
    summary["n_failed"] = len(errors)
    summary["n_random_controls_strong"] = int(((leaderboard["family"] == "random") & (leaderboard["edge"] == "strong")).sum())
    summary["n_random_controls_alpha_strong"] = int(((leaderboard["family"] == "random") & (leaderboard["alpha_edge"] == "strong")).sum())
    summary["families"] = sorted(leaderboard["family"].unique().tolist())
    summary["benchmark_name"] = "buy_and_hold_equal_weight"

    return BatchResult(
        specs=specs, config=config, returns=returns, navs=navs, leaderboard=leaderboard,
        summary=summary, errors=errors, edge=edge, benchmark=benchmark, benchmark_nav=benchmark_nav,
        market_meta={"tickers": market.tickers, "start": str(market.index[0].date()),
                     "end": str(market.index[-1].date()), "synthetic": market.synthetic, "n_days": len(market.index)},
    )
