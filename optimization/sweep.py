"""Parameter grid search: run one backtest per parameter combination and rank them."""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.trades import round_trips, trade_statistics
from web.registry import build

OBJECTIVES = ("sharpe", "sortino", "calmar", "cagr", "total_return", "max_drawdown")
_METRIC_COLUMNS = ("total_return", "cagr", "sharpe", "sortino", "calmar", "max_drawdown", "annualised_volatility")


@dataclass
class SweepResult:
    strategy: str
    objective: str
    param_names: list[str]
    table: pd.DataFrame
    best: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        rows = []
        for rec in self.table.to_dict(orient="records"):
            rows.append({k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in rec.items()})
        return {
            "strategy": self.strategy,
            "objective": self.objective,
            "param_names": list(self.param_names),
            "rows": rows,
            "best": {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in self.best.items()},
        }


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Cartesian product of a ``{param: [values]}`` grid as a list of kwargs dicts."""
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(grid[k] for k in keys))]


def grid_search(
    strategy: str,
    grid: dict[str, list[Any]],
    prices: pd.DataFrame,
    objective: str = "sharpe",
    benchmark: pd.Series | None = None,
    initial_capital: float = 1_000_000.0,
    commission: float = 0.001,
    slippage_bps: float = 5.0,
    execution_lag: int = 1,
    rebalance: bool = True,
    risk_free_rate: float = 0.0,
) -> SweepResult:
    """Backtest every parameter combination and rank by ``objective`` (descending).

    ``max_drawdown`` is negative, so sorting descending puts the shallowest
    drawdown first, which is the desired ranking. Failing combinations are kept
    as rows with ``error`` set rather than aborting the sweep.
    """
    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {OBJECTIVES}, got '{objective}'")

    config = BacktestConfig(
        start=str(prices.index[0].date()),
        end=str(prices.index[-1].date()),
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage_bps / 10_000,
        execution_lag=execution_lag,
        rebalance=rebalance,
        risk_free_rate=risk_free_rate,
    )
    engine = BacktestEngine(config)
    combos = expand_grid(grid)
    rows: list[dict[str, Any]] = []

    for params in combos:
        row: dict[str, Any] = dict(params)
        try:
            result = engine.run(build(strategy, params), prices, benchmark=benchmark)
            row.update({k: result.metrics.get(k) for k in _METRIC_COLUMNS})
            stats = trade_statistics(round_trips(result.trades))
            row["n_trades"] = stats["n_trades"]
            row["win_rate"] = stats["win_rate"]
            row["profit_factor"] = stats["profit_factor"]
            row["error"] = None
        except Exception as exc:  # keep sweeping; surface the failure in the table
            row.update({k: None for k in _METRIC_COLUMNS})
            row.update({"n_trades": 0, "win_rate": None, "profit_factor": None, "error": str(exc)})
        rows.append(row)

    table = pd.DataFrame(rows)
    table = table.sort_values(objective, ascending=False, na_position="last", kind="stable").reset_index(drop=True)
    best = table.iloc[0].to_dict() if len(table) else {}
    return SweepResult(strategy=strategy, objective=objective, param_names=list(grid), table=table, best=best)
