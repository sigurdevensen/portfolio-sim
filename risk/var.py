"""Value at Risk and Conditional VaR calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def value_at_risk(
    returns: pd.Series,
    confidence: float = 0.95,
    method: str = "historical",
    horizon: int = 1,
) -> float:
    """Compute VaR at a given confidence level.

    Args:
        returns: Daily return series.
        confidence: Confidence level (e.g. 0.95 = 95%).
        method: 'historical', 'parametric', or 'montecarlo'.
        horizon: Holding period in days (scales by sqrt(horizon)).

    Returns:
        VaR as a positive number (loss magnitude).
    """
    if method == "historical":
        var = -np.percentile(returns.dropna(), (1 - confidence) * 100)
    elif method == "parametric":
        mu, sigma = returns.mean(), returns.std()
        var = -(mu + stats.norm.ppf(1 - confidence) * sigma)
    elif method == "montecarlo":
        mu, sigma = returns.mean(), returns.std()
        simulated = np.random.normal(mu, sigma, 100_000)
        var = -np.percentile(simulated, (1 - confidence) * 100)
    else:
        raise ValueError(f"Unknown VaR method: {method}")
    return float(var * np.sqrt(horizon))


def conditional_var(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """Expected Shortfall (CVaR): mean loss beyond the VaR threshold."""
    threshold = np.percentile(returns.dropna(), (1 - confidence) * 100)
    tail = returns[returns <= threshold]
    return float(-tail.mean())
