import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data.loader import load_csv
from data.cleaner import fill_na_values

from strategies.index_buy_sell_randomly import buy_sell_randomly


def plot_buy_sell_index(
    buy_sell_index: pd.DataFrame,
    x: list,
    n_runs: int = 10000,
    title: str = "Buy/Sell Index",
) -> None:
    runs = np.array([
        buy_sell_randomly(buy_sell_index, capital=10000.0)
        for _ in range(n_runs)
    ])  # shape: (n_runs, n_days)

    p5, p25, p50, p75, p95 = np.percentile(runs, [5, 25, 50, 75, 95], axis=0)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.fill_between(x, p5, p95, alpha=0.15, label="5-95%")
    ax.fill_between(x, p25, p75, alpha=0.35, label="25-75%")
    ax.plot(x, p50, linewidth=1.5, label="Median")
    ax.axhline(10_000, color="grey", linestyle="--", linewidth=0.8, label="Starting capital")

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio Value")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def main():
    loaded_data = load_csv("data/raw/EQNR_OL_monthly.csv")
    loaded_data = fill_na_values(loaded_data)  # ffill NA values in the DataFrame
    x = loaded_data.index.tolist()

    plot_buy_sell_index(loaded_data, x, title="Buy/Sell Index")

if __name__ == "__main__":
    main()