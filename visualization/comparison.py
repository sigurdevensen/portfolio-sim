"""Multi-strategy comparison charts."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_strategy_comparison(
    nav_dict: dict[str, pd.Series],
    title: str = "Strategy Comparison",
) -> plt.Figure:
    """Plot normalised NAV curves for multiple strategies on one chart.

    Args:
        nav_dict: Mapping of strategy name → NAV series.
        title: Chart title.
    """
    fig, ax = plt.subplots(figsize=(12, 5))
    for name, nav in nav_dict.items():
        normalised = nav / nav.iloc[0] * 100
        ax.plot(normalised.index, normalised.values, label=name, linewidth=1.5)
    ax.set_title(title)
    ax.set_ylabel("Indexed Value (base=100)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig
