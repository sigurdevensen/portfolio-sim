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
    fee_rate: float = 0.00,
) -> None:
    runs = np.array([
        buy_sell_randomly(buy_sell_index, capital=10000.0, fee_rate=fee_rate)
        for _ in range(n_runs)
    ])  # shape: (n_runs, n_days)

    p5, p25, p50, p75, p95 = np.percentile(runs, [5, 25, 50, 75, 95], axis=0)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.fill_between(x, p5, p25, color="C0", alpha=0.3, label="5–25 persentil")
    ax.fill_between(x, p25, p50, color="C0", alpha=0.5, label="25–50 persentil")
    ax.fill_between(x, p50, p75, color="C0", alpha=0.5, label="50–75 persentil")
    ax.fill_between(x, p75, p95, color="C0", alpha=0.3, label="75–95 persentil")
    ax.plot(x, p50, color="C0", linewidth=1.5, label="Median")
    ax.axhline(10_000, color="RED", linestyle="--", linewidth=0.8, label="Startkapital")

    dates = pd.to_datetime(x)
    years_elapsed = (dates - dates[0]).days / 365.25
    savings = 10_000 * (1.04 ** years_elapsed)
    ax.plot(x, savings, color="C2", linewidth=1.5, linestyle="-.", label="Sparekonto (4% p.a.)")

    ax.set_title(title)
    ax.set_xlabel("Dato")
    ax.set_ylabel("Portfolio Verdi (NOK)")
    ax.legend()
    ax.grid(True, alpha=0.3)
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