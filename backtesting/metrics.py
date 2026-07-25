"""Performance metrics computed from a NAV series."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    nav: pd.Series
    trades: pd.DataFrame
    benchmark: pd.Series | None = None
    metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metrics = compute_metrics(self.nav, self.benchmark)


def compute_metrics(nav: pd.Series, benchmark: pd.Series | None = None) -> dict[str, float]:
    returns = nav.pct_change().dropna()
    n_years = len(returns) / 252

    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / n_years) - 1 if n_years > 0 else 0.0
    sharpe = _sharpe(returns)
    max_dd, dd_series = _drawdown(nav)
    volatility = returns.std() * np.sqrt(252)

    result: dict[str, float] = {
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "annualised_volatility": volatility,
        "total_return": (nav.iloc[-1] / nav.iloc[0]) - 1,
    }

    if benchmark is not None:
        bm_returns = benchmark.pct_change().dropna()
        aligned = returns.align(bm_returns, join="inner")
        result["alpha"], result["beta"] = _alpha_beta(*aligned)
        result["information_ratio"] = _information_ratio(*aligned)

    return result


def _sharpe(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = returns - risk_free_rate / 252
    std = excess.std()
    return float((excess.mean() / std) * np.sqrt(252)) if std > 0 else 0.0


def _drawdown(nav: pd.Series) -> tuple[float, pd.Series]:
    rolling_max = nav.cummax()
    dd = (nav - rolling_max) / rolling_max
    return float(dd.min()), dd


def _alpha_beta(returns: pd.Series, benchmark: pd.Series) -> tuple[float, float]:
    cov = np.cov(returns, benchmark)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0.0
    alpha = returns.mean() - beta * benchmark.mean()
    return float(alpha * 252), float(beta)


def _information_ratio(returns: pd.Series, benchmark: pd.Series) -> float:
    active = returns - benchmark
    std = active.std()
    return float((active.mean() / std) * np.sqrt(252)) if std > 0 else 0.0
