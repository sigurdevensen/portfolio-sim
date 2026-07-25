"""Risk-focused visualizations."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from risk.drawdown import drawdown_series


def plot_drawdown(nav: pd.Series, title: str = "Drawdown") -> plt.Figure:
    dd = drawdown_series(nav)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(dd.index, dd.values, 0, alpha=0.5, color="red")
    ax.plot(dd.index, dd.values, color="red", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.grid(True, alpha=0.3)
    return fig


def plot_var_cone(
    returns: pd.Series,
    horizon: int = 252,
    confidence_levels: list[float] | None = None,
    title: str = "VaR Projection Cone",
) -> plt.Figure:
    if confidence_levels is None:
        confidence_levels = [0.95, 0.99]
    mu = returns.mean()
    sigma = returns.std()
    days = np.arange(1, horizon + 1)

    fig, ax = plt.subplots(figsize=(10, 5))
    for cl in confidence_levels:
        from scipy.stats import norm
        z = norm.ppf(1 - cl)
        lower = mu * days + z * sigma * np.sqrt(days)
        ax.fill_between(days, lower * 100, 0, alpha=0.2, label=f"{cl:.0%} VaR")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(title)
    ax.set_xlabel("Days forward")
    ax.set_ylabel("Cumulative return (%)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig


def plot_correlation_heatmap(corr: pd.DataFrame, title: str = "Asset Correlation") -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr.values, cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.index)
    for i in range(len(corr)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title(title)
    fig.tight_layout()
    return fig
