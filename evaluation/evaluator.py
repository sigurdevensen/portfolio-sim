"""Evaluator: assembles a BacktestReport from a BacktestResult."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backtesting.metrics import BacktestResult
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


class Evaluator:
    """Computes risk-adjusted metrics from a BacktestResult."""

    def evaluate(
        self,
        result: BacktestResult,
        strategy_name: str = "strategy",
        benchmark: pd.Series | None = None,
        prices: pd.DataFrame | None = None,
    ) -> BacktestReport:
        """Build a BacktestReport with all metrics and risk statistics.

        Args:
            result: Completed backtest result.
            strategy_name: Human-readable strategy label used in the report.
            benchmark: Reserved for future alpha/beta calculation (not yet implemented).
            prices: Optional multi-ticker price DataFrame for correlation matrix.

        Returns:
            BacktestReport with full metrics, VaR, CVaR, drawdown, and correlations.
        """
        returns = result.nav.pct_change().dropna()

        var_95 = value_at_risk(returns, confidence=0.95, method="historical")
        var_99 = value_at_risk(returns, confidence=0.99, method="historical")
        cvar_95 = conditional_var(returns, confidence=0.95)
        dd_series = compute_drawdown_series(result.nav)
        rec_periods = recovery_periods(result.nav)

        corr: pd.DataFrame | None = None
        if prices is not None and len(prices.columns) > 1:
            corr = prices.pct_change().dropna().corr()

        return BacktestReport(
            result=result,
            metrics=result.metrics,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            drawdown_series=dd_series,
            recovery_periods=rec_periods,
            correlation_matrix=corr,
            strategy_name=strategy_name,
        )
