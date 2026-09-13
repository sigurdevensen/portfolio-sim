"""Evaluator: assembles a BacktestReport from a BacktestResult."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backtesting.metrics import BacktestResult, compute_metrics
from backtesting.trades import round_trips, trade_statistics
from evaluation.significance import MIN_OBSERVATIONS, SignificanceResult, analyse
from risk.drawdown import RecoveryPeriod
from risk.drawdown import drawdown_series as compute_drawdown_series
from risk.drawdown import recovery_periods
from risk.var import conditional_var, value_at_risk


@dataclass
class BacktestReport:
    result: BacktestResult
    metrics: dict[str, float]
    var_95: float
    var_99: float
    cvar_95: float
    drawdown_series: pd.Series
    recovery_periods: list[RecoveryPeriod]
    correlation_matrix: pd.DataFrame | None
    strategy_name: str = "strategy"
    round_trips: pd.DataFrame = field(default_factory=pd.DataFrame)
    trade_stats: dict[str, float] = field(default_factory=dict)
    significance: SignificanceResult | None = None
    monthly_returns: pd.DataFrame = field(default_factory=pd.DataFrame)


class Evaluator:
    """Computes risk-adjusted metrics, trade statistics and significance."""

    def evaluate(
        self,
        result: BacktestResult,
        strategy_name: str = "strategy",
        benchmark: pd.Series | None = None,
        prices: pd.DataFrame | None = None,
        significance: bool = True,
        n_samples: int = 1000,
        seed: int = 0,
    ) -> BacktestReport:
        """Build a BacktestReport with all metrics and risk statistics.

        Args:
            result: Completed backtest result.
            strategy_name: Human-readable strategy label used in the report.
            benchmark: Benchmark value series; overrides ``result.benchmark`` if given.
            prices: Optional multi-ticker price DataFrame for the correlation matrix.
            significance: Run bootstrap / randomisation analysis (skipped when the
                return series is shorter than 30 observations).
            n_samples: Bootstrap sample count.
            seed: RNG seed for the significance analysis.
        """
        nav = result.nav
        returns = nav.pct_change().dropna()

        metrics = result.metrics
        if benchmark is not None:
            metrics = compute_metrics(nav, benchmark, result.risk_free_rate)
            result.benchmark = benchmark
            result.metrics = metrics

        rt = round_trips(result.trades)

        sig: SignificanceResult | None = None
        if significance and len(returns) >= MIN_OBSERVATIONS:
            sig = analyse(returns, n_samples=n_samples, seed=seed)

        corr: pd.DataFrame | None = None
        if prices is not None and len(prices.columns) > 1:
            corr = prices.pct_change(fill_method=None).dropna().corr()

        return BacktestReport(
            result=result,
            metrics=metrics,
            var_95=value_at_risk(returns, confidence=0.95, method="historical") if len(returns) else 0.0,
            var_99=value_at_risk(returns, confidence=0.99, method="historical") if len(returns) else 0.0,
            cvar_95=conditional_var(returns, confidence=0.95) if len(returns) else 0.0,
            drawdown_series=compute_drawdown_series(nav),
            recovery_periods=recovery_periods(nav),
            correlation_matrix=corr,
            strategy_name=strategy_name,
            round_trips=rt,
            trade_stats=trade_statistics(rt),
            significance=sig,
            monthly_returns=monthly_returns_table(nav),
        )


def monthly_returns_table(nav: pd.Series) -> pd.DataFrame:
    """Year x month table of compounded monthly returns (months 1..12 as columns)."""
    if nav.empty:
        return pd.DataFrame(columns=list(range(1, 13)))
    try:
        month_end = nav.resample("ME").last()
    except ValueError:  # pandas < 2.2 uses "M" for month-end
        month_end = nav.resample("M").last()
    # Prepend the starting value so the first month's return is measured from inception.
    prev = month_end.shift(1)
    prev.iloc[0] = nav.iloc[0]
    monthly = month_end / prev - 1
    table = pd.DataFrame({
        "year": monthly.index.year,
        "month": monthly.index.month,
        "ret": monthly.values,
    }).pivot(index="year", columns="month", values="ret")
    return table.reindex(columns=list(range(1, 13)))
