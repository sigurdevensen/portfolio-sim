"""OSEBX vs. Norwegian Savings Account — Risk/Return Analysis.

Fetches data via the LSEG Workspace desktop API and produces:
- Summary statistics (printed + saved to analysis/osebx_stats.json)
- Seven publication-quality charts saved to analysis/figures/

Run with:
    python scripts/analyze_osebx_vs_savings.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from risk.var import value_at_risk, conditional_var
from risk.drawdown import drawdown_series, max_drawdown, recovery_periods


# ── LSEG data fetch ──────────────────────────────────────────────────────────

def fetch_lseg_data() -> tuple[pd.Series, pd.Series]:
    """Return (osebx_close, savings_rate_annual_pct) as monthly series."""
    import lseg.data as ld

    ld.open_session()
    try:
        osebx_df = ld.get_history(
            universe=".OSEBX",
            interval="monthly",
            start="1996-01-01",
            end="2026-07-31",
        )
        rate_df = ld.get_history(
            universe="NO6MT=RR",
            interval="monthly",
            start="1996-01-01",
            end="2026-07-31",
        )
    finally:
        ld.close_session()

    # OSEBX close price
    close_col = next(
        (c for c in ["TRDPRC_1", "Close", "CLOSE"] if c in osebx_df.columns),
        osebx_df.columns[0],
    )
    osebx = osebx_df[close_col].astype(float)
    osebx.index = pd.to_datetime(osebx.index).tz_localize(None)
    osebx.name = "OSEBX"

    # Norwegian 6-month T-bill MID yield (annual %)
    savings = rate_df["MID_YLD_1"].astype(float)
    savings.index = pd.to_datetime(savings.index).tz_localize(None)
    savings.name = "savings_rate_pct"

    return osebx, savings


# ── Return series helpers ────────────────────────────────────────────────────

def monthly_savings_returns(annual_rate_pct: pd.Series) -> pd.Series:
    """Convert annual % rate to monthly compounded returns."""
    monthly = (1 + annual_rate_pct / 100) ** (1 / 12) - 1
    return monthly


def cumulative_nav(returns: pd.Series, start: float = 100.0) -> pd.Series:
    return (1 + returns).cumprod() * start


def annualised_return(nav: pd.Series) -> float:
    n_years = len(nav) / 12
    return float((nav.iloc[-1] / nav.iloc[0]) ** (1 / n_years) - 1) if n_years > 0 else 0.0


def annualised_vol(monthly_returns: pd.Series) -> float:
    return float(monthly_returns.std() * np.sqrt(12))


def sharpe(monthly_returns: pd.Series, monthly_rf: pd.Series) -> float:
    excess = monthly_returns - monthly_rf
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(12))


# ── Rolling outperformance ───────────────────────────────────────────────────

def probability_of_outperformance(
    osebx_monthly: pd.Series,
    savings_monthly: pd.Series,
    horizons_years: list[int],
) -> dict[int, float]:
    result = {}
    for h in horizons_years:
        n = h * 12
        wins = 0
        total = 0
        for start in range(len(osebx_monthly) - n):
            osebx_cum = (1 + osebx_monthly.iloc[start : start + n]).prod()
            sav_cum = (1 + savings_monthly.iloc[start : start + n]).prod()
            wins += osebx_cum > sav_cum
            total += 1
        result[h] = wins / total if total > 0 else float("nan")
    return result


# ── Monte Carlo simulation ───────────────────────────────────────────────────

def monte_carlo(
    mu_monthly: float,
    sigma_monthly: float,
    savings_monthly_mean: float,
    n_months: int = 120,
    n_sims: int = 5000,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    sim = rng.normal(mu_monthly, sigma_monthly, size=(n_sims, n_months))
    paths = np.cumprod(1 + sim, axis=1) * 100

    savings_nav = (1 + savings_monthly_mean) ** np.arange(1, n_months + 1) * 100

    final = paths[:, -1]
    sav_final = savings_nav[-1]
    return {
        "paths": paths,
        "savings_nav": savings_nav,
        "pct5": np.percentile(final, 5),
        "pct25": np.percentile(final, 25),
        "median": np.percentile(final, 50),
        "pct75": np.percentile(final, 75),
        "pct95": np.percentile(final, 95),
        "savings_final": sav_final,
        "prob_beat": float(np.mean(final > sav_final)),
    }


# ── Styling helpers ──────────────────────────────────────────────────────────

OSEBX_COLOR = "#003087"   # dark navy
SAVINGS_COLOR = "#E8720C"  # orange
FIG_DIR = ROOT / "analysis" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f9f9f9",
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linestyle": "--",
    "grid.linewidth": 0.6,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "legend.fontsize": 10,
    "figure.dpi": 150,
})


def save(fig: plt.Figure, name: str) -> Path:
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path.relative_to(ROOT)}")
    return path


# ── Individual chart functions ───────────────────────────────────────────────

def chart_cumulative(osebx_nav: pd.Series, savings_nav: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(osebx_nav.index, osebx_nav, color=OSEBX_COLOR, lw=2, label="OSEBX")
    ax.plot(savings_nav.index, savings_nav, color=SAVINGS_COLOR, lw=2, label="Savings account (6M NIBOR)")
    ax.set_title("Cumulative Growth of 100 NOK — OSEBX vs. Savings Account")
    ax.set_ylabel("Portfolio value (NOK)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend()
    save(fig, "01_cumulative_growth")


def chart_annual_returns(osebx_ann: pd.Series, savings_ann: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    years = osebx_ann.index.year
    x = np.arange(len(years))
    w = 0.4
    ax.bar(x - w / 2, osebx_ann.values * 100, w, label="OSEBX", color=OSEBX_COLOR, alpha=0.85)
    ax.bar(x + w / 2, savings_ann.values * 100, w, label="Savings account", color=SAVINGS_COLOR, alpha=0.85)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(years, rotation=45, ha="right", fontsize=8)
    ax.set_title("Annual Returns: OSEBX vs. Savings Account")
    ax.set_ylabel("Return (%)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.legend()
    save(fig, "02_annual_returns")


def chart_drawdown(osebx_nav: pd.Series) -> None:
    dd = drawdown_series(osebx_nav) * 100
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(dd.index, dd, 0, color=OSEBX_COLOR, alpha=0.4, label="Drawdown")
    ax.plot(dd.index, dd, color=OSEBX_COLOR, lw=1)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title("OSEBX Drawdown from Peak")
    ax.set_ylabel("Drawdown (%)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    save(fig, "03_drawdown")


def chart_return_distribution(osebx_ret: pd.Series, savings_ret: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(osebx_ret * 100, bins=50, alpha=0.6, color=OSEBX_COLOR, label="OSEBX monthly returns", density=True)
    ax.hist(savings_ret * 100, bins=30, alpha=0.6, color=SAVINGS_COLOR, label="Savings monthly returns", density=True)
    ax.axvline(0, color="black", lw=0.8, linestyle="--")
    ax.set_title("Distribution of Monthly Returns")
    ax.set_xlabel("Monthly return (%)")
    ax.set_ylabel("Density")
    ax.legend()
    save(fig, "04_return_distribution")


def chart_rolling_sharpe(osebx_ret: pd.Series, savings_ret: pd.Series, window: int = 36) -> None:
    excess = osebx_ret - savings_ret
    rolling_sharpe = excess.rolling(window).mean() / excess.rolling(window).std() * np.sqrt(12)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(rolling_sharpe.index, rolling_sharpe, color=OSEBX_COLOR, lw=1.5, label=f"{window}-month rolling Sharpe")
    ax.axhline(0, color="black", lw=0.8, linestyle="--")
    ax.axhline(1, color="green", lw=0.8, linestyle=":", alpha=0.7, label="Sharpe = 1 (target)")
    ax.set_title(f"Rolling {window}-Month Sharpe Ratio (vs. Savings Rate)")
    ax.set_ylabel("Sharpe ratio")
    ax.legend()
    save(fig, "05_rolling_sharpe")


def chart_outperformance_probability(probs: dict[int, float]) -> None:
    horizons = list(probs.keys())
    vals = [v * 100 for v in probs.values()]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(horizons, vals, color=OSEBX_COLOR, alpha=0.85, width=0.6)
    ax.axhline(50, color="red", lw=1.2, linestyle="--", label="50% break-even")
    ax.set_xticks(horizons)
    ax.set_xticklabels([f"{h}Y" for h in horizons])
    ax.set_title("Probability of OSEBX Outperforming Savings Account\nby Investment Horizon")
    ax.set_ylabel("Probability (%)")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{val:.0f}%",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.legend()
    save(fig, "06_outperformance_probability")


def chart_monte_carlo(mc: dict, n_months: int, savings_monthly_mean: float) -> None:
    paths = mc["paths"]
    months = np.arange(1, n_months + 1)
    fig, ax = plt.subplots(figsize=(10, 6))

    # Draw 200 random paths
    rng = np.random.default_rng(0)
    sample_idx = rng.choice(len(paths), size=min(200, len(paths)), replace=False)
    for i in sample_idx:
        ax.plot(months, paths[i], color=OSEBX_COLOR, alpha=0.04, lw=0.6)

    # Percentile bands
    ax.fill_between(months, mc["pct5"], mc["pct95"], alpha=0.15, color=OSEBX_COLOR, label="5th–95th pct")
    ax.fill_between(months, mc["pct25"], mc["pct75"], alpha=0.25, color=OSEBX_COLOR, label="25th–75th pct")
    ax.plot(months, [mc["median"]] * 0 + [np.median(paths[:, i]) for i in range(n_months)],
            color=OSEBX_COLOR, lw=2.5, label="OSEBX median")
    ax.plot(months, mc["savings_nav"], color=SAVINGS_COLOR, lw=2.5, linestyle="--", label="Savings account")
    ax.set_title(f"Monte Carlo: OSEBX vs. Savings over {n_months // 12}-Year Horizon\n"
                 f"({len(paths):,} simulations, starting NOK 100)")
    ax.set_xlabel("Month")
    ax.set_ylabel("Portfolio value (NOK)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.legend(loc="upper left")
    save(fig, "07_monte_carlo")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Fetching data from LSEG Workspace...")
    osebx_price, savings_rate = fetch_lseg_data()

    # Align series
    combined = pd.DataFrame({"osebx": osebx_price, "rate": savings_rate}).dropna()
    osebx_price = combined["osebx"]
    savings_rate = combined["rate"]

    print(f"  OSEBX: {combined.index[0].date()} — {combined.index[-1].date()} ({len(combined)} months)")

    # Monthly returns
    osebx_ret = osebx_price.pct_change().dropna()
    savings_ret = monthly_savings_returns(savings_rate.reindex(osebx_ret.index).ffill())

    # NAV series (starting at 100)
    osebx_nav = cumulative_nav(osebx_ret)
    sav_nav = cumulative_nav(savings_ret)

    # Annual returns (calendar year)
    osebx_ann = (1 + osebx_ret).resample("A").prod() - 1
    sav_ann = (1 + savings_ret).resample("A").prod() - 1
    # Remove partial current year
    current_year = pd.Timestamp.now().year
    osebx_ann = osebx_ann[osebx_ann.index.year < current_year]
    sav_ann = sav_ann[sav_ann.index.year < current_year]

    # ── Core metrics ─────────────────────────────────────────────────────────
    osebx_cagr = annualised_return(osebx_nav)
    sav_cagr = annualised_return(sav_nav)
    osebx_vol = annualised_vol(osebx_ret)
    sav_vol = annualised_vol(savings_ret)
    osebx_sharpe = sharpe(osebx_ret, savings_ret)
    osebx_maxdd = max_drawdown(osebx_nav)
    osebx_var95 = value_at_risk(osebx_ret, confidence=0.95)
    osebx_var99 = value_at_risk(osebx_ret, confidence=0.99)
    osebx_cvar95 = conditional_var(osebx_ret, confidence=0.95)
    sav_var95 = value_at_risk(savings_ret, confidence=0.95)

    # Skewness / kurtosis
    osebx_skew = float(stats.skew(osebx_ret.dropna()))
    osebx_kurt = float(stats.kurtosis(osebx_ret.dropna()))

    # Calmar ratio
    calmar = osebx_cagr / abs(osebx_maxdd) if osebx_maxdd != 0 else float("inf")

    # Recovery periods for big drawdowns
    recoveries = recovery_periods(osebx_nav, threshold=-0.15)

    # Win rate: how many calendar years did OSEBX beat savings?
    yearly_osebx_beats = (osebx_ann.values > sav_ann.reindex(osebx_ann.index).values)
    win_rate_annual = float(yearly_osebx_beats.sum() / len(yearly_osebx_beats))

    # Rolling outperformance
    print("Computing rolling outperformance probabilities...")
    horizons = [1, 3, 5, 10, 15, 20]
    probs = probability_of_outperformance(osebx_ret, savings_ret, horizons)

    # Monte Carlo (10-year horizon)
    print("Running Monte Carlo simulation...")
    n_months = 120
    mc = monte_carlo(
        mu_monthly=float(osebx_ret.mean()),
        sigma_monthly=float(osebx_ret.std()),
        savings_monthly_mean=float(savings_ret.mean()),
        n_months=n_months,
        n_sims=10_000,
    )

    # ── Charts ───────────────────────────────────────────────────────────────
    print("Generating charts...")
    chart_cumulative(osebx_nav, sav_nav)
    chart_annual_returns(osebx_ann, sav_ann.reindex(osebx_ann.index))
    chart_drawdown(osebx_nav)
    chart_return_distribution(osebx_ret, savings_ret)
    chart_rolling_sharpe(osebx_ret, savings_ret)
    chart_outperformance_probability(probs)
    chart_monte_carlo(mc, n_months, float(savings_ret.mean()))

    # ── Summary stats ────────────────────────────────────────────────────────
    first_year = combined.index[0].year
    last_year = combined.index[-1].year

    summary = {
        "period": f"{first_year}–{last_year}",
        "n_months": int(len(osebx_ret)),
        "osebx": {
            "cagr_pct": round(osebx_cagr * 100, 2),
            "annualised_vol_pct": round(osebx_vol * 100, 2),
            "sharpe_vs_savings": round(osebx_sharpe, 3),
            "max_drawdown_pct": round(osebx_maxdd * 100, 2),
            "calmar_ratio": round(calmar, 3),
            "var95_monthly_pct": round(osebx_var95 * 100, 2),
            "var99_monthly_pct": round(osebx_var99 * 100, 2),
            "cvar95_monthly_pct": round(osebx_cvar95 * 100, 2),
            "skewness": round(osebx_skew, 3),
            "excess_kurtosis": round(osebx_kurt, 3),
            "total_return_pct": round((osebx_nav.iloc[-1] / 100 - 1) * 100, 1),
        },
        "savings": {
            "cagr_pct": round(sav_cagr * 100, 2),
            "annualised_vol_pct": round(sav_vol * 100, 2),
            "var95_monthly_pct": round(sav_var95 * 100, 2),
            "total_return_pct": round((sav_nav.iloc[-1] / 100 - 1) * 100, 1),
            "mean_annual_rate_pct": round(float(savings_rate.mean()), 2),
        },
        "comparison": {
            "annual_win_rate_pct": round(win_rate_annual * 100, 1),
            "outperformance_prob_by_horizon": {str(k): round(v * 100, 1) for k, v in probs.items()},
        },
        "drawdown_episodes": [
            {
                "peak": str(r.peak_date.date()),
                "trough": str(r.trough_date.date()),
                "recovery": str(r.recovery_date.date()) if r.recovery_date else "Not yet",
                "drawdown_pct": round(r.drawdown * 100, 1),
                "duration_days": r.duration_days,
            }
            for r in sorted(recoveries, key=lambda x: x.drawdown)[:5]
        ],
        "monte_carlo_10yr": {
            "pct5": round(mc["pct5"], 1),
            "pct25": round(mc["pct25"], 1),
            "median": round(mc["median"], 1),
            "pct75": round(mc["pct75"], 1),
            "pct95": round(mc["pct95"], 1),
            "savings_final": round(mc["savings_final"], 1),
            "prob_beat_pct": round(mc["prob_beat"] * 100, 1),
        },
    }

    out_path = ROOT / "analysis" / "osebx_stats.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to {out_path.relative_to(ROOT)}")

    # Print key stats
    print("\n" + "=" * 60)
    print(f"Period: {summary['period']} ({summary['n_months']} months)")
    print(f"\n{'':25s}  {'OSEBX':>10s}  {'Savings':>10s}")
    print(f"{'CAGR':25s}  {summary['osebx']['cagr_pct']:>9.1f}%  {summary['savings']['cagr_pct']:>9.1f}%")
    print(f"{'Annualised volatility':25s}  {summary['osebx']['annualised_vol_pct']:>9.1f}%  {summary['savings']['annualised_vol_pct']:>9.1f}%")
    print(f"{'Max drawdown':25s}  {summary['osebx']['max_drawdown_pct']:>9.1f}%  {'0.0':>9s}%")
    print(f"{'Sharpe ratio':25s}  {summary['osebx']['sharpe_vs_savings']:>10.3f}")
    print(f"{'VaR 95% (monthly)':25s}  {summary['osebx']['var95_monthly_pct']:>9.1f}%  {summary['savings']['var95_monthly_pct']:>9.1f}%")
    print(f"{'Total return':25s}  {summary['osebx']['total_return_pct']:>9.1f}%  {summary['savings']['total_return_pct']:>9.1f}%")
    print(f"\nAnnual win rate:  {summary['comparison']['annual_win_rate_pct']}% of years OSEBX beat savings")
    print("=" * 60)


if __name__ == "__main__":
    main()
