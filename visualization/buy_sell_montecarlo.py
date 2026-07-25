import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data.loader import load_csv
from data.cleaner import fill_na_values

from strategies.buy_sell_randomly import buy_sell_randomly


def plot_buy_sell_index(
    buy_sell_index: pd.DataFrame,
    x: list,
    n_runs: int = 10000,
    title: str = "Buy/Sell Index",
    fee_rate: float = 0.001,
) -> None:
    runs = np.array([
        buy_sell_randomly(buy_sell_index, capital=10000.0, fee_rate=fee_rate)
        for _ in range(n_runs)
    ])  # shape: (n_runs, n_days)

    p5, p25, p50, p75, p95 = np.percentile(runs, [5, 25, 50, 75, 95], axis=0)

    BG      = "#0E1525"  # deep navy — dark enough without pure black harshness
    OUTER   = "#1A4A7A"  # dark steel blue — subtle outer uncertainty band
    INNER   = "#2878B8"  # medium blue — more vivid inner band
    MEDIAN  = "#56CCF2"  # bright sky cyan — most prominent element
    REFLINE = "#3D5166"  # muted slate — unobtrusive reference line
    TEXT    = "#A0AEC0"  # cool grey — readable without glare
    TITLE   = "#EDF2F7"  # near-white
    SPINE   = "#1E3A5F"  # dark blue border

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    ax.tick_params(colors=TEXT)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TITLE)
    for spine in ax.spines.values():
        spine.set_edgecolor(SPINE)
    ax.fill_between(x, p5, p95, color=OUTER, alpha=0.5, label="5-95%")
    ax.fill_between(x, p25, p75, color=INNER, alpha=0.65, label="25-75%")
    ax.plot(x, p50, color=MEDIAN, linewidth=1.5, label="Median")
    ax.axhline(10_000, color=REFLINE, linestyle="--", linewidth=0.8, label="Starting capital")

    ax.set_title(title)
    ax.set_xlabel("Dato")
    ax.set_ylabel("Portfolio Verdi (NOK)")
    ax.legend(facecolor=BG, edgecolor=SPINE, labelcolor=TEXT)
    ax.grid(True, alpha=0.12, color=TEXT)
    ax.set_xlim(x[0], x[-1])
    plt.tight_layout()
    plt.savefig("visualization/buy_sell_montecarlo.png", bbox_inches="tight")
    plt.show()


def main():
    loaded_data = load_csv("data/raw/osebx_monthly.csv")
    loaded_data = fill_na_values(loaded_data)  # ffill NA values in the DataFrame
    x = loaded_data.index.tolist()

    plot_buy_sell_index(
        loaded_data, 
        x, 
        title="Tilfeldig kjøp/salg-strategi på OSEBX-indeksen", 
        n_runs=10000,
        fee_rate=0.0
    )

if __name__ == "__main__":
    main()