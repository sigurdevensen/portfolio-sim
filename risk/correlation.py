"""Return correlation utilities."""
from __future__ import annotations

import pandas as pd


def rolling_correlation(
    returns: pd.DataFrame,
    window: int = 60,
    pair: tuple[str, str] | None = None,
) -> pd.DataFrame | pd.Series:
    """Rolling pairwise correlations.

    Args:
        returns: Daily return DataFrame, one column per asset.
        window: Rolling window in trading days.
        pair: If given, return a Series for that specific pair only.

    Returns:
        DataFrame of rolling correlations or a Series if pair is specified.
    """
    if pair is not None:
        a, b = pair
        return returns[a].rolling(window).corr(returns[b])
    return returns.rolling(window).corr()


def correlation_heatmap_data(returns: pd.DataFrame) -> pd.DataFrame:
    """Full-period correlation matrix, ready for plotting."""
    return returns.corr()
