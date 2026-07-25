"""NAV and return visualizations."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_nav(
    nav: pd.Series,
    benchmark: pd.Series | None = None,
    title: str = "Portfolio NAV",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(12, 5))
    nav_normalised = nav / nav.iloc[0] * 100
    ax.plot(nav_normalised.index, nav_normalised.values, label="Strategy", linewidth=1.5)
    if benchmark is not None:
        bm_normalised = benchmark / benchmark.iloc[0] * 100
        ax.plot(bm_normalised.index, bm_normalised.values, label="Benchmark", linewidth=1, linestyle="--", alpha=0.7)
    ax.set_title(title)
    ax.set_ylabel("Indexed Value (base=100)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig


def plot_returns_distribution(returns: pd.Series, title: str = "Daily Returns Distribution") -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(returns.dropna(), bins=60, edgecolor="none", alpha=0.75)
    ax.axvline(returns.mean(), color="red", linestyle="--", label=f"Mean: {returns.mean():.4f}")
    ax.set_title(title)
    ax.set_xlabel("Daily Return")
    ax.set_ylabel("Frequency")
    ax.legend()
    return fig
