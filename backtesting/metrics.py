"""Performance metrics computed from a NAV series."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    nav: pd.Series
    trades: pd.DataFrame
    benchmark: pd.Series | None = None
    risk_free_rate: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metrics = compute_metrics(self.nav, self.benchmark, self.risk_free_rate)


def compute_metrics(
    nav: pd.Series,
    benchmark: pd.Series | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """Compute performance and distribution statistics from a NAV series.

    Args:
        nav: Portfolio value series with a DatetimeIndex.
        benchmark: Optional benchmark value series (aligned on inner join).
        risk_free_rate: Annualised risk-free rate used for Sharpe/Sortino.

    Returns:
        Dict of plain floats. Keys are stable and consumed by the reporters.
    """
    returns = nav.pct_change().dropna()
    n_years = len(returns) / TRADING_DAYS

    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / n_years) - 1 if n_years > 0 else 0.0
    max_dd, _ = _drawdown(nav)
    volatility = float(returns.std() * np.sqrt(TRADING_DAYS)) if len(returns) > 1 else 0.0

    result: dict[str, float] = {
        "total_return": float(nav.iloc[-1] / nav.iloc[0] - 1),
        "cagr": float(cagr),
        "sharpe": _sharpe(returns, risk_free_rate),
        "sortino": _sortino(returns, risk_free_rate),
        "calmar": float(cagr / abs(max_dd)) if max_dd < 0 else 0.0,
        "max_drawdown": max_dd,
        "annualised_volatility": volatility,
        "skew": float(stats.skew(returns)) if len(returns) > 2 else 0.0,
        "kurtosis": float(stats.kurtosis(returns)) if len(returns) > 3 else 0.0,
        "best_day": float(returns.max()) if len(returns) else 0.0,
        "worst_day": float(returns.min()) if len(returns) else 0.0,
        "positive_days_pct": float((returns > 0).mean()) if len(returns) else 0.0,
        "n_days": int(len(returns)),
    }

    if benchmark is not None:
        bm_returns = benchmark.pct_change().dropna()
        aligned = returns.align(bm_returns, join="inner")
        if len(aligned[0]) > 1:
            result["alpha"], result["beta"] = _alpha_beta(*aligned)
            result["information_ratio"] = _information_ratio(*aligned)
            bm_nav = benchmark.loc[aligned[1].index]
            result["benchmark_total_return"] = float(bm_nav.iloc[-1] / benchmark.iloc[0] - 1)

    return result


def _sharpe(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = returns - risk_free_rate / TRADING_DAYS
    std = excess.std()
    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS)) if std > 0 else 0.0


def _sortino(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = returns - risk_free_rate / TRADING_DAYS
    downside = excess[excess < 0]
    if len(downside) == 0:
        return 0.0
    downside_dev = np.sqrt((downside ** 2).sum() / len(excess))
    return float((excess.mean() / downside_dev) * np.sqrt(TRADING_DAYS)) if downside_dev > 0 else 0.0


def _drawdown(nav: pd.Series) -> tuple[float, pd.Series]:
    rolling_max = nav.cummax()
    dd = (nav - rolling_max) / rolling_max
    return float(dd.min()), dd


def _alpha_beta(returns: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    cov = np.cov(returns, benchmark)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0.0
    alpha = returns.mean() - beta * benchmark.mean()
    return float(alpha * TRADING_DAYS), float(beta)


def _information_ratio(returns: pd.Series, benchmark: pd.Series) -> float:
    active = returns - benchmark
    std = active.std()
    return float((active.mean() / std) * np.sqrt(TRADING_DAYS)) if std > 0 else 0.0
