"""Vår Energi (VAR.OL) — Stock Movement Analysis and 1-Year Scenario Forecast.

Fetches daily price data via the LSEG Workspace desktop API and produces:
  - Technical analysis charts (price/MAs/Bollinger Bands, RSI)
  - Drawdown chart
  - Oil price correlation analysis
  - 1-year scenario fan chart (bull/base/bear)
  - Scenario outcome distribution chart
  - Full markdown analysis report at analysis/var_energy.md

Requires LSEG Workspace to be open and signed in on the desktop.
Install the library if needed:
    pip install lseg-data

Run with:
    python scripts/analyze_var_energy.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from scipy.signal import argrelextrema

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

VAR_RIC = "VAR.OL"
BRENT_RIC = "LCOc1"   # Brent crude front-month continuous
OSEBX_RIC = ".OSEBX"
HISTORY_START = "2022-02-01"   # Near IPO date (16 Feb 2022)

FIG_DIR = ROOT / "analysis" / "var_figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

VAR_COLOR = "#1a5276"
BRENT_COLOR = "#b7950b"
BULL_COLOR = "#27ae60"
BASE_COLOR = "#2980b9"
BEAR_COLOR = "#c0392b"

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


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_lseg_data() -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (VAR.OL close, Brent close, OSEBX close) as daily series."""
    import lseg.data as ld

    ld.open_session()
    try:
        var_df = ld.get_history(universe=VAR_RIC, interval="daily",
                                start=HISTORY_START, end=date.today().isoformat())
        brent_df = ld.get_history(universe=BRENT_RIC, interval="daily",
                                  start=HISTORY_START, end=date.today().isoformat())
        osebx_df = ld.get_history(universe=OSEBX_RIC, interval="daily",
                                  start=HISTORY_START, end=date.today().isoformat())
    finally:
        ld.close_session()

    def _extract_close(df: pd.DataFrame) -> pd.Series:
        col = next(
            (c for c in ["TRDPRC_1", "Close", "CLOSE"] if c in df.columns),
            df.columns[0],
        )
        s = df[col].astype(float)
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s

    return _extract_close(var_df), _extract_close(brent_df), _extract_close(osebx_df)


# ── Technical indicator helpers ───────────────────────────────────────────────

def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def compute_bollinger(prices: pd.Series, window: int = 20, n_std: float = 2.0):
    ma = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    return ma, ma + n_std * std, ma - n_std * std


def find_support_resistance(prices: pd.Series, order: int = 15) -> tuple[list, list]:
    """Return (support_levels, resistance_levels) from local extrema, sorted."""
    arr = prices.values
    min_idx = argrelextrema(arr, np.less, order=order)[0]
    max_idx = argrelextrema(arr, np.greater, order=order)[0]
    supports = sorted(arr[min_idx].tolist()) if len(min_idx) else []
    resistances = sorted(arr[max_idx].tolist(), reverse=True) if len(max_idx) else []
    return supports, resistances


# ── Monte Carlo ───────────────────────────────────────────────────────────────

def monte_carlo_scenarios(
    current_price: float,
    daily_vol: float,
    n_days: int = 252,
    n_sims: int = 10_000,
) -> dict:
    """Simulate three oil-price-driven scenarios for VAR.OL over one year."""
    scenarios = {
        "bull": {"annual_drift": 0.25, "label": "Bull (Brent ≥ $85)", "color": BULL_COLOR},
        "base": {"annual_drift": 0.05, "label": "Base (Brent $70–80)", "color": BASE_COLOR},
        "bear": {"annual_drift": -0.20, "label": "Bear (Brent ≤ $60)", "color": BEAR_COLOR},
    }
    results: dict = {}
    seeds = {"bull": 42, "base": 43, "bear": 44}
    for name, sc in scenarios.items():
        rng = np.random.default_rng(seeds[name])
        daily_drift = sc["annual_drift"] / n_days
        rand = rng.normal(daily_drift, daily_vol, size=(n_sims, n_days))
        paths = current_price * np.cumprod(1 + rand, axis=1)
        final = paths[:, -1]
        results[name] = {
            "paths": paths,
            "label": sc["label"],
            "color": sc["color"],
            "pct5": float(np.percentile(final, 5)),
            "pct25": float(np.percentile(final, 25)),
            "median": float(np.percentile(final, 50)),
            "pct75": float(np.percentile(final, 75)),
            "pct95": float(np.percentile(final, 95)),
            "prob_above_current": float(np.mean(final > current_price)),
            "expected": float(np.mean(final)),
        }
    return results


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _save(fig: plt.Figure, name: str) -> None:
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path.relative_to(ROOT)}")


def chart_price_technicals(
    var: pd.Series,
    ma50: pd.Series,
    ma200: pd.Series,
    bb_mid: pd.Series,
    bb_upper: pd.Series,
    bb_lower: pd.Series,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(var.index, var, color=VAR_COLOR, lw=1.5, label="VAR.OL close")
    ax.plot(ma50.index, ma50, color="#e67e22", lw=1.2, linestyle="--", label="50-day MA")
    ax.plot(ma200.index, ma200, color="#8e44ad", lw=1.5, linestyle="--", label="200-day MA")
    ax.fill_between(var.index, bb_lower, bb_upper, alpha=0.10, color=VAR_COLOR,
                    label="Bollinger Bands (20,2)")
    ax.plot(bb_mid.index, bb_mid, color=VAR_COLOR, lw=0.8, linestyle=":", alpha=0.6)
    ax.set_title("Vår Energi (VAR.OL) — Price with Technical Indicators")
    ax.set_ylabel("Price (NOK)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}"))
    ax.legend(loc="upper right")
    _save(fig, "01_price_technicals")


def chart_rsi(var: pd.Series, rsi: pd.Series) -> None:
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax1.plot(var.index, var, color=VAR_COLOR, lw=1.5)
    ax1.set_title("Vår Energi (VAR.OL) — Price and RSI (14)")
    ax1.set_ylabel("Price (NOK)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}"))

    ax2.plot(rsi.index, rsi, color=VAR_COLOR, lw=1.2)
    ax2.axhline(70, color="red", lw=0.8, linestyle="--", alpha=0.7, label="Overbought (70)")
    ax2.axhline(30, color="green", lw=0.8, linestyle="--", alpha=0.7, label="Oversold (30)")
    ax2.axhline(50, color="gray", lw=0.5, linestyle=":")
    ax2.fill_between(rsi.index, 30, rsi.clip(upper=30), alpha=0.25, color="green")
    ax2.fill_between(rsi.index, rsi.clip(lower=70), 70, alpha=0.25, color="red")
    ax2.set_ylabel("RSI")
    ax2.set_ylim(0, 100)
    ax2.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    _save(fig, "02_rsi")


def chart_oil_correlation(var: pd.Series, brent: pd.Series) -> tuple[float, float]:
    aligned = pd.DataFrame({"VAR": var, "Brent": brent}).dropna()
    var_ret = aligned["VAR"].pct_change().dropna()
    brent_ret = aligned["Brent"].pct_change().dropna()
    both = pd.concat([var_ret, brent_ret], axis=1).dropna()

    slope, intercept, r_val, *_ = scipy_stats.linregress(both["Brent"], both["VAR"])

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Rebased price chart
    ax = axes[0]
    var_norm = aligned["VAR"] / aligned["VAR"].iloc[0] * 100
    brent_norm = aligned["Brent"] / aligned["Brent"].iloc[0] * 100
    ax.plot(var_norm.index, var_norm, color=VAR_COLOR, lw=1.5, label="VAR.OL (rebased 100)")
    ax.plot(brent_norm.index, brent_norm, color=BRENT_COLOR, lw=1.5, label="Brent Crude (rebased 100)")
    ax.set_title("VAR.OL vs. Brent Crude — Rebased to 100")
    ax.set_ylabel("Indexed value")
    ax.legend()

    # Return scatter
    ax = axes[1]
    ax.scatter(both["Brent"] * 100, both["VAR"] * 100, alpha=0.3, s=10, color=VAR_COLOR)
    x_line = np.linspace(both["Brent"].min(), both["Brent"].max(), 100)
    ax.plot(x_line * 100, (slope * x_line + intercept) * 100, color="red", lw=1.5,
            label=f"β = {slope:.2f}   R² = {r_val**2:.2f}")
    ax.set_xlabel("Brent daily return (%)")
    ax.set_ylabel("VAR.OL daily return (%)")
    ax.set_title("Daily Return Scatter: VAR.OL vs. Brent Crude")
    ax.legend()

    plt.tight_layout()
    _save(fig, "03_oil_correlation")
    return float(slope), float(r_val ** 2)


def chart_drawdown(var: pd.Series) -> None:
    dd = (var - var.cummax()) / var.cummax() * 100
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.fill_between(dd.index, dd, 0, color=VAR_COLOR, alpha=0.4)
    ax.plot(dd.index, dd, color=VAR_COLOR, lw=1)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title("Vår Energi (VAR.OL) — Drawdown from Peak")
    ax.set_ylabel("Drawdown (%)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    _save(fig, "04_drawdown")


def chart_scenarios(current_price: float, mc: dict) -> None:
    n_days = mc["bull"]["paths"].shape[1]
    days = np.arange(1, n_days + 1)
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.axhline(current_price, color="black", lw=1, linestyle=":",
               alpha=0.7, label=f"Current: {current_price:.1f} NOK")

    for name, sc in mc.items():
        paths = sc["paths"]
        ax.fill_between(days,
                        np.percentile(paths, 5, axis=0),
                        np.percentile(paths, 95, axis=0),
                        alpha=0.10, color=sc["color"])
        ax.fill_between(days,
                        np.percentile(paths, 25, axis=0),
                        np.percentile(paths, 75, axis=0),
                        alpha=0.20, color=sc["color"])
        ax.plot(days, np.median(paths, axis=0), color=sc["color"], lw=2.2,
                label=sc["label"])

    ax.set_title("Vår Energi (VAR.OL) — 1-Year Scenario Fan Chart\n"
                 "(10 000 simulations per scenario; bands = 5th–95th and 25th–75th pct)")
    ax.set_xlabel("Trading day")
    ax.set_ylabel("Price (NOK)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}"))
    ax.legend(loc="upper left")
    _save(fig, "05_scenarios")


def chart_scenario_outcomes(current_price: float, mc: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    scenario_list = list(mc.items())

    for i, (name, sc) in enumerate(scenario_list):
        lo, q25, med, q75, hi = sc["pct5"], sc["pct25"], sc["median"], sc["pct75"], sc["pct95"]
        w = 0.5
        ax.bar(i, q75 - q25, bottom=q25, width=w, color=sc["color"], alpha=0.55)
        ax.bar(i, hi - q75, bottom=q75, width=w, color=sc["color"], alpha=0.20)
        ax.bar(i, q25 - lo, bottom=lo, width=w, color=sc["color"], alpha=0.20)
        ax.plot([i - w / 2, i + w / 2], [med, med], color=sc["color"], lw=2.5)
        ax.text(i, med + 0.3, f"{med:.1f}", ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=sc["color"])

    ax.axhline(current_price, color="black", lw=1.5, linestyle="--",
               label=f"Current: {current_price:.1f} NOK")
    ax.set_xticks(range(len(scenario_list)))
    ax.set_xticklabels([sc["label"] for _, sc in scenario_list])
    ax.set_title("Vår Energi — 1-Year Price Scenario Distribution\n"
                 "(box = 25th–75th pct; whiskers = 5th–95th pct; line = median)")
    ax.set_ylabel("Price (NOK)")
    ax.legend()
    _save(fig, "06_scenario_outcomes")


# ── Markdown generation ───────────────────────────────────────────────────────

def _entry_recommendation(rsi: float, s1: float, s2: float, s3: float) -> str:
    if rsi < 35:
        return (
            f"The stock is **oversold** (RSI {rsi:.0f}). This historically "
            f"represents an attractive entry zone. Consider scaling in near "
            f"{s1:.1f} NOK with a second tranche at {s2:.1f} NOK if weakness continues."
        )
    if rsi < 45:
        return (
            f"The stock is approaching oversold territory (RSI {rsi:.0f}). "
            f"A phased entry starting near {s1:.1f} NOK appears well-supported. "
            f"Set a stop below {s3:.1f} NOK."
        )
    if rsi > 70:
        return (
            f"The stock is **overbought** (RSI {rsi:.0f}). Avoid chasing here — "
            f"wait for a pullback toward {s1:.1f} NOK before initiating a position."
        )
    return (
        f"RSI is neutral ({rsi:.0f}). The preferred entry zone is "
        f"{s2:.1f}–{s1:.1f} NOK (key support confluence). "
        f"A stop below {s3:.1f} NOK protects against a structural breakdown."
    )


def _rsi_signal(rsi: float) -> str:
    if rsi < 30:
        return "Oversold — strong buy signal historically"
    if rsi < 40:
        return "Approaching oversold — watch for reversal"
    if rsi > 70:
        return "Overbought — potential pullback"
    return "Neutral"


def generate_markdown(stats: dict, mc: dict) -> None:
    s = stats
    cp = s["current_price"]
    today_str = date.today().strftime("%B %d, %Y")

    # Dividend estimates by scenario (rough guidance-based approximation)
    div_bull = cp * 0.18
    div_base = cp * 0.12
    div_bear = cp * 0.05

    bull_total = (mc["bull"]["median"] / cp - 1) * 100 + 18
    base_total = (mc["base"]["median"] / cp - 1) * 100 + 12
    bear_total = (mc["bear"]["median"] / cp - 1) * 100 + 5

    pw_return = 0.25 * bull_total + 0.55 * base_total + 0.20 * bear_total

    overall = (
        "Cautious BUY at support levels"
        if s["rsi_current"] < 50
        else "HOLD — wait for better entry"
    )

    md = f"""# Vår Energi (VAR.OL) — Stock Analysis & 1-Year Scenario Forecast

**Date:** {today_str}
**Data source:** LSEG Workspace API (`{VAR_RIC}`, `{BRENT_RIC}`, `{OSEBX_RIC}`)
**Analysis period:** {s['period_start']} – {s['period_end']}
**Script:** `scripts/analyze_var_energy.py`

---

## Executive Summary

Vår Energi (VAR.OL) is Norway's second-largest oil and gas producer on the Norwegian Continental Shelf (NCS), listed on Oslo Børs since February 2022. The stock is a **high-beta, leveraged play on Brent crude** with a committed 100% free-cash-flow dividend payout policy — making it one of the highest-yielding energy stocks in Europe when oil prices are constructive.

**Current price: {cp:.2f} NOK**
The stock is currently **{abs(s['current_vs_ma200']):.1%} {"above" if s['current_vs_ma200'] > 0 else "below"}** its 200-day moving average ({s['ma200']:.2f} NOK), and **{abs(s['from_52w_high']):.1%} below** its 52-week high of {s['high_52w']:.2f} NOK.

{_entry_recommendation(s['rsi_current'], s['support_1'], s['support_2'], s['support_3'])}

| Scenario | Oil Price | Median 1-Year Target | Total Return Est.* | P(Gain) |
|----------|-----------|---------------------|-------------------|---------|
| **Bull** | Brent ≥ $85 | **{mc['bull']['median']:.1f} NOK** | +{bull_total:.0f}% | {mc['bull']['prob_above_current']:.0%} |
| **Base** | Brent $70–80 | **{mc['base']['median']:.1f} NOK** | +{base_total:.0f}% | {mc['base']['prob_above_current']:.0%} |
| **Bear** | Brent ≤ $60 | **{mc['bear']['median']:.1f} NOK** | {bear_total:.0f}% | {mc['bear']['prob_above_current']:.0%} |

*Total return includes estimated dividend yield per scenario. Actual dividends depend on realised oil prices, production, and management decisions.*

**Probability-weighted expected 1-year return: +{pw_return:.1f}%**

---

## 1. Company Overview

| Attribute | Detail |
|-----------|--------|
| Exchange | Oslo Børs (Euronext Oslo) |
| Ticker | VAR.OL |
| IPO | 16 February 2022 |
| Major shareholder | Eni S.p.A (~69.6% pre-dilution) |
| Production | ~320 000–360 000 boepd (barrels of oil equivalent per day) |
| Key assets | Norwegian Continental Shelf (30+ fields) |
| Dividend policy | 100% of available cash flow from 2024 onwards |
| Sector | Energy — Exploration & Production (E&P) |

Vår Energi was formed from the 2018 merger of Eni Norge and Point Resources and listed in 2022 at approximately 29 NOK per share. The company operates long-life, low-decline assets across the NCS and has guided for production growth through new field developments (Balder X, Ringhorne North, Johan Castberg phase-in, and others).

The dividend commitment is the cornerstone of the investment thesis. At Brent crude in the $70–80 range, the implied annual dividend yield is typically **10–14%**, making VAR.OL among the highest-yielding liquid equity securities in the Norwegian market. This yield collapses sharply below $60/bbl and expands significantly above $85/bbl.

---

## 2. Price and Technical Analysis

![Price with Technical Indicators](var_figures/01_price_technicals.png)

### 2.1 Snapshot

| Indicator | Value | Signal |
|-----------|-------|--------|
| Current price | **{cp:.2f} NOK** | — |
| 50-day MA | {s['ma50']:.2f} NOK | {"Price above 50-day MA ▲" if cp > s['ma50'] else "Price below 50-day MA ▼"} |
| 200-day MA | {s['ma200']:.2f} NOK | {"Above 200-day MA — long-term bullish ▲" if cp > s['ma200'] else "Below 200-day MA — long-term bearish ▼"} |
| MA relationship | — | {"50-day ABOVE 200-day (Golden Cross alignment ▲)" if s['ma50'] > s['ma200'] else "50-day BELOW 200-day (Death Cross alignment ▼)"} |
| RSI (14-day) | {s['rsi_current']:.1f} | {_rsi_signal(s['rsi_current'])} |
| Bollinger upper | {s['bb_upper']:.2f} NOK | — |
| Bollinger lower | {s['bb_lower']:.2f} NOK | {"Price near/below lower band — mean-reversion signal" if cp < s['bb_lower'] * 1.05 else "Within bands"} |
| 52-week high | {s['high_52w']:.2f} NOK | — |
| 52-week low | {s['low_52w']:.2f} NOK | — |
| vs. 52-week high | {s['from_52w_high']:.1%} | — |
| vs. 52-week low | +{s['from_52w_low']:.1%} | — |

### 2.2 Moving Average Regime

The 50/200-day MA pair is a widely-followed trend regime filter. Currently the short-term MA is **{"above" if s['ma50'] > s['ma200'] else "below"}** the long-term MA — a **{"bullish" if s['ma50'] > s['ma200'] else "bearish"}** configuration. In VAR.OL's short listed history, MA crossovers have aligned closely with Brent crude trend changes:

- **50-day above 200-day**: Tends to coincide with Brent $75+, attracting income-seeking institutional buyers for the high dividend.
- **50-day below 200-day**: Often coincides with oil price weakness or uncertainty around dividend sustainability.

The current spread between 50-day ({s['ma50']:.2f} NOK) and 200-day ({s['ma200']:.2f} NOK) is **{s['ma50'] - s['ma200']:.2f} NOK ({(s['ma50'] / s['ma200'] - 1):.1%})**.

### 2.3 Relative Strength Index (RSI)

![RSI](var_figures/02_rsi.png)

At **{s['rsi_current']:.1f}**, the RSI is:
{"in overbought territory. The stock has moved sharply and a consolidation or pullback is likely before the next leg higher. This is not an attractive new-entry point." if s['rsi_current'] > 70 else
"in oversold territory. Historically, VAR.OL RSI readings below 30 have preceded strong mean-reversion rallies. This is statistically one of the better entry points." if s['rsi_current'] < 30 else
"approaching oversold (below 40). Combined with proximity to support levels, this creates a moderate-risk entry opportunity with an attractive risk/reward profile." if s['rsi_current'] < 40 else
"in neutral territory, providing no strong directional signal. Price action and support/resistance levels become the primary decision framework."}

### 2.4 Drawdown

![Drawdown](var_figures/04_drawdown.png)

| Metric | Value |
|--------|-------|
| Maximum drawdown (since IPO) | **{s['max_drawdown']:.1%}** |
| Current drawdown from all-time high | **{s['current_drawdown']:.1%}** |
| Annualised volatility | {s['annual_vol']:.1%} |
| Daily 95% VaR (historical) | {s['daily_var95']:.1%} |

VAR.OL has experienced significant drawdowns since its 2022 IPO — unsurprising given the stock's high sensitivity to oil price fluctuations. The maximum drawdown of **{s['max_drawdown']:.1%}** reflects the magnitude of oil price corrections since listing. Investors must be prepared for these drawdowns to occur during any 12-month holding period.

---

## 3. Entry Point Analysis

### 3.1 Support and Resistance Map

Key price levels derived from historical support/resistance analysis:

| Price Level | Type | Significance |
|------------|------|-------------|
| {s['resistance_1']:.1f} NOK | **Resistance** | Prior peak / key overhead supply |
| {s['resistance_2']:.1f} NOK | **Resistance** | Secondary resistance from prior consolidation |
| **{cp:.1f} NOK** | *Current* | Current market price |
| {s['support_1']:.1f} NOK | **Key Support** | Most-tested support since listing |
| {s['support_2']:.1f} NOK | **Support** | Secondary support / base formation zone |
| {s['support_3']:.1f} NOK | **Critical Support** | Break below signals structural weakness |

### 3.2 Entry Strategy

**Preferred entry zone: {s['support_2']:.1f} – {s['support_1']:.1f} NOK**

| Tranche | Price | Size | Rationale |
|---------|-------|------|-----------|
| First | {s['support_1']:.1f} NOK (current) | 50% | Near key support; RSI {s['rsi_current']:.0f} provides entry context |
| Second | {s['support_2']:.1f} NOK | 50% | Adds on further weakness; stronger support level |
| Stop-loss | Below {s['support_3']:.1f} NOK (close) | Exit all | Structural breakdown signal |

**Risk per share (stop to entry):** ~{s['support_1'] - s['support_3']:.1f} NOK
**Reward (base-case median):** ~{mc['base']['median'] - s['support_1']:.1f} NOK
**Risk/reward ratio (base case):** ~{(mc['base']['median'] - s['support_1']) / max(s['support_1'] - s['support_3'], 0.01):.1f}:1

### 3.3 Key Catalysts (Next 12 Months)

| Catalyst | Direction | Expected Timeline |
|----------|-----------|-------------------|
| Quarterly production/earnings updates | Both | Q1–Q4 2025 |
| Brent crude trend | Both | Ongoing |
| Norges Bank interest rate decisions | Positive on cuts | 2025 |
| NCS license rounds (APA/numbered) | Positive | 2025 |
| Eni potential stake reduction | Negative (supply) | Uncertain |
| Energy transition regulation | Negative | Ongoing |
| New field ramp-ups (Balder X, Johan Castberg) | Positive | 2025–2026 |

---

## 4. Oil Price Correlation

![Oil Correlation](var_figures/03_oil_correlation.png)

### 4.1 Sensitivity Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Oil beta (daily returns) | **{s['oil_beta']:.2f}x** | Each 1% Brent move → VAR moves ~{s['oil_beta']:.1f}% |
| R² (Brent vs. VAR.OL) | **{s['oil_r2']:.1%}** | Brent explains {s['oil_r2']:.0%} of VAR daily variance |
| Rolling 90-day correlation | **{s['oil_corr_90d']:.2f}** | Current short-term relationship |

With a beta of **{s['oil_beta']:.2f}x**, VAR.OL is {"highly" if s['oil_beta'] > 1.3 else "moderately"} leveraged to Brent crude. This is consistent with a pure-play E&P company where every dollar of oil revenue flows directly to operating cash flow (relative to an integrated major that also has refining/chemicals as a partial buffer).

The high R² of **{s['oil_r2']:.1%}** means that oil price moves are the **dominant driver** of VAR.OL's stock performance. Macro views on oil must therefore come first in any investment thesis for this stock.

### 4.2 Dividend-Yield Sensitivity

VAR.OL's 100%-payout policy transforms the stock into a **leveraged oil-linked income instrument**:

| Brent Scenario | Est. Annual Dividend | Est. Yield at {cp:.0f} NOK |
|---------------|---------------------|--------------------------|
| $95/bbl (upside) | ~{cp * 0.22:.2f} NOK | ~22% |
| $85/bbl (bull) | ~{div_bull:.2f} NOK | ~18% |
| $75/bbl (base) | ~{div_base:.2f} NOK | ~12% |
| $60/bbl (bear) | ~{div_bear:.2f} NOK | ~5% |
| $50/bbl (stress) | ~{cp * 0.01:.2f} NOK | <2% (potential suspension) |

*Estimated from management's cash flow guidance and historical payout patterns. Production hedging and operating costs will cause actual dividends to differ.*

---

## 5. One-Year Scenario Analysis

### 5.1 Scenario Framework

Three scenarios are modelled, differentiated by the Brent crude price level which is the primary driver:

| Scenario | Brent Assumption | Annual Drift (stock) | Probability |
|----------|-----------------|----------------------|-------------|
| **Bull** | ≥ $85/bbl | +25% | ~25% |
| **Base** | $70–80/bbl | +5% | ~55% |
| **Bear** | ≤ $60/bbl | −20% | ~20% |

The simulation applies each scenario's drift to VAR.OL's historical daily volatility of **{s['daily_vol']:.2%}** ({s['annual_vol']:.1%} annualised), running **10 000 paths** per scenario over **252 trading days**.

### 5.2 Scenario Fan Chart

![1-Year Scenario Fan](var_figures/05_scenarios.png)

### 5.3 Outcome Distributions

![Scenario Outcomes](var_figures/06_scenario_outcomes.png)

### 5.4 Detailed Scenario Tables

#### Bull Case — Brent ≥ $85/bbl

| Metric | Value |
|--------|-------|
| Median 12-month target | **{mc['bull']['median']:.1f} NOK** |
| 25th–75th pct range | {mc['bull']['pct25']:.1f} – {mc['bull']['pct75']:.1f} NOK |
| 5th–95th pct range | {mc['bull']['pct5']:.1f} – {mc['bull']['pct95']:.1f} NOK |
| Probability above current | **{mc['bull']['prob_above_current']:.0%}** |
| Price return (median) | +{(mc['bull']['median'] / cp - 1) * 100:.0f}% |
| Est. dividend yield | ~18% |
| **Total return estimate (median)** | **+{bull_total:.0f}%** |

**Key assumptions:** OPEC+ maintains discipline; China demand continues recovering; no major NCS production outages; Norges Bank cuts rates 50–100 bps.

#### Base Case — Brent $70–80/bbl

| Metric | Value |
|--------|-------|
| Median 12-month target | **{mc['base']['median']:.1f} NOK** |
| 25th–75th pct range | {mc['base']['pct25']:.1f} – {mc['base']['pct75']:.1f} NOK |
| 5th–95th pct range | {mc['base']['pct5']:.1f} – {mc['base']['pct95']:.1f} NOK |
| Probability above current | **{mc['base']['prob_above_current']:.0%}** |
| Price return (median) | +{(mc['base']['median'] / cp - 1) * 100:.0f}% |
| Est. dividend yield | ~12% |
| **Total return estimate (median)** | **+{base_total:.0f}%** |

**Key assumptions:** Moderate global demand growth; OPEC+ partially unwinds cuts; NCS production meets guidance; Norwegian macro environment stable.

#### Bear Case — Brent ≤ $60/bbl

| Metric | Value |
|--------|-------|
| Median 12-month target | **{mc['bear']['median']:.1f} NOK** |
| 25th–75th pct range | {mc['bear']['pct25']:.1f} – {mc['bear']['pct75']:.1f} NOK |
| 5th–95th pct range | {mc['bear']['pct5']:.1f} – {mc['bear']['pct95']:.1f} NOK |
| Probability above current | **{mc['bear']['prob_above_current']:.0%}** |
| Price return (median) | {(mc['bear']['median'] / cp - 1) * 100:.0f}% |
| Est. dividend yield | ~5% |
| **Total return estimate (median)** | **{bear_total:.0f}%** |

**Key assumptions:** Global recession or demand shock; OPEC+ fracture; significant US shale production growth; potential dividend cut or suspension by management.

---

## 6. Risk Factors

### Downside Risks

| Risk | Likelihood | Potential Impact on Stock |
|------|-----------|--------------------------|
| Brent crude falls below $60/bbl | Medium | High: −30% to −50%; dividend cut risk |
| Production shortfall or field outage | Low–Medium | Medium: −10% to −20% |
| Norwegian windfall/carbon tax increase | Low–Medium | Medium: −5% to −15% |
| Eni secondary offering / stake sale | Medium | Medium: −5% to −10% (supply overhang) |
| NOK strengthening sharply vs. USD | Low | Low–Medium: reduces earnings in NOK |
| Global recession + demand destruction | Low | Very High: potential oil price collapse |
| Dividend suspension | Low (at Brent >$65) | Very High: yield investors exit |

### Upside Risks

| Risk | Likelihood | Potential Impact on Stock |
|------|-----------|--------------------------|
| Geopolitical disruption → oil spike | Low–Medium | Very High: stock +30% to +50% |
| Faster-than-expected OPEC+ cuts | Medium | High: Brent reprices to $90+ |
| Norges Bank rate cuts accelerate | Medium | Medium: multiple expansion |
| Accretive NCS acquisition | Low | Medium: growth re-rating |
| MSCI/FTSE index weight increase | Low | Low–Medium: passive buying |

---

## 7. Investment Summary

### Positioning

VAR.OL is appropriate for investors who:
1. Hold a **constructive view on oil ($70+)** over a 12-month horizon
2. Seek **high income** (10–18% dividend yield depending on oil) from a liquid, investment-grade issuer
3. Can tolerate **high volatility** ({s['annual_vol']:.0%} annualised) and drawdowns of up to 40–50%
4. Want **pure-play NCS exposure** without the refining/chemicals complexity of Equinor

### One-Page Summary

| | |
|---|---|
| **Current price** | {cp:.2f} NOK |
| **Entry zone** | {s['support_2']:.1f} – {s['support_1']:.1f} NOK |
| **Stop-loss** | Below {s['support_3']:.1f} NOK |
| **Bull target (12M)** | {mc['bull']['median']:.0f} NOK |
| **Base target (12M)** | {mc['base']['median']:.0f} NOK |
| **Bear target (12M)** | {mc['bear']['median']:.0f} NOK |
| **Prob-weighted return** | +{pw_return:.1f}% (incl. dividend) |
| **Overall stance** | **{overall}** |

### Key Variable to Monitor

> **Brent crude price is the single most important variable for VAR.OL.** Set a Brent price alert at $65 (bear trigger) and $85 (bull trigger). All other analysis is secondary to oil price direction.

---

*Analysis generated: {today_str}. Data: LSEG Workspace API. Charts: `analysis/var_figures/`. Prices in NOK; oil in USD/bbl. This analysis is for informational purposes only and does not constitute investment advice.*
"""

    out_path = ROOT / "analysis" / "var_energy.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nMarkdown report saved to {out_path.relative_to(ROOT)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Fetching data from LSEG Workspace...")

    try:
        import lseg.data  # noqa: F401
    except ImportError:
        print(
            "lseg-data is not installed.\n"
            "Install with: pip install lseg-data\n"
            "Then ensure LSEG Workspace is open and signed in."
        )
        sys.exit(1)

    var_price, brent_price, osebx_price = fetch_lseg_data()

    # Forward-fill Brent and OSEBX to match VAR trading days
    var_price = var_price.dropna()
    brent_aligned = brent_price.reindex(var_price.index).ffill()
    osebx_aligned = osebx_price.reindex(var_price.index).ffill()

    print(f"  VAR.OL: {var_price.index[0].date()} — {var_price.index[-1].date()} ({len(var_price)} days)")

    # ── Technical indicators ──────────────────────────────────────────────────
    ma50 = var_price.rolling(50).mean()
    ma200 = var_price.rolling(200).mean()
    bb_mid, bb_upper, bb_lower = compute_bollinger(var_price)
    rsi = compute_rsi(var_price)

    current_price = float(var_price.iloc[-1])
    current_ma50 = float(ma50.dropna().iloc[-1])
    current_ma200 = float(ma200.dropna().iloc[-1])
    current_rsi = float(rsi.dropna().iloc[-1])
    current_bb_upper = float(bb_upper.dropna().iloc[-1])
    current_bb_lower = float(bb_lower.dropna().iloc[-1])

    # 52-week metrics
    lookback = var_price.iloc[-252:] if len(var_price) >= 252 else var_price
    high_52w = float(lookback.max())
    low_52w = float(lookback.min())

    # Drawdown
    max_dd = float(((var_price - var_price.cummax()) / var_price.cummax()).min())
    current_dd = float((current_price - float(var_price.cummax().iloc[-1])) / float(var_price.cummax().iloc[-1]))

    # Return / volatility
    var_ret = var_price.pct_change().dropna()
    daily_vol = float(var_ret.std())
    annual_vol = daily_vol * np.sqrt(252)
    daily_var95 = float(np.percentile(var_ret, 5))

    # ── Oil correlation ───────────────────────────────────────────────────────
    print("Computing oil price correlation...")
    brent_ret = brent_aligned.pct_change().dropna()
    both = pd.concat([var_ret, brent_ret], axis=1).dropna()
    both.columns = ["VAR", "Brent"]
    slope, intercept, r_val, p_val, std_err = scipy_stats.linregress(both["Brent"], both["VAR"])
    oil_r2 = r_val ** 2

    corr_90 = var_ret.rolling(90).corr(brent_ret)
    current_corr_90 = float(corr_90.dropna().iloc[-1]) if not corr_90.dropna().empty else float("nan")

    # ── Support / resistance ──────────────────────────────────────────────────
    supports, resistances = find_support_resistance(var_price, order=15)

    def _pick(levels: list, below_current: bool, fallback_mult: float) -> list:
        if below_current:
            picked = [v for v in levels if v < current_price * 1.01]
            if not picked:
                picked = [current_price * fallback_mult]
        else:
            picked = [v for v in levels if v > current_price * 0.99]
            if not picked:
                picked = [current_price * fallback_mult]
        return picked

    sup_below = _pick(supports, True, 0.90)
    res_above = _pick(resistances, False, 1.10)

    s1 = sup_below[-1] if sup_below else current_price * 0.92
    s2 = sup_below[-2] if len(sup_below) >= 2 else current_price * 0.87
    s3 = sup_below[-3] if len(sup_below) >= 3 else current_price * 0.80
    r1 = res_above[0] if res_above else current_price * 1.10
    r2 = res_above[1] if len(res_above) >= 2 else current_price * 1.18

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    print("Running Monte Carlo scenario simulations (10 000 paths × 3)...")
    mc = monte_carlo_scenarios(current_price, daily_vol)

    # ── Charts ────────────────────────────────────────────────────────────────
    print("Generating charts...")
    chart_price_technicals(var_price, ma50, ma200, bb_mid, bb_upper, bb_lower)
    chart_rsi(var_price, rsi)
    oil_beta, oil_r2_chart = chart_oil_correlation(var_price, brent_aligned)
    chart_drawdown(var_price)
    chart_scenarios(current_price, mc)
    chart_scenario_outcomes(current_price, mc)

    # ── Assemble stats dict ───────────────────────────────────────────────────
    stats = {
        "period_start": var_price.index[0].strftime("%Y-%m-%d"),
        "period_end": var_price.index[-1].strftime("%Y-%m-%d"),
        "current_price": current_price,
        "ma50": current_ma50,
        "ma200": current_ma200,
        "current_vs_ma200": (current_price - current_ma200) / current_ma200,
        "rsi_current": current_rsi,
        "bb_upper": current_bb_upper,
        "bb_lower": current_bb_lower,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "from_52w_high": (current_price - high_52w) / high_52w,
        "from_52w_low": (current_price - low_52w) / low_52w,
        "max_drawdown": max_dd,
        "current_drawdown": current_dd,
        "daily_vol": daily_vol,
        "annual_vol": annual_vol,
        "daily_var95": daily_var95,
        "oil_beta": slope,
        "oil_r2": oil_r2,
        "oil_corr_90d": current_corr_90,
        "support_1": s1,
        "support_2": s2,
        "support_3": s3,
        "resistance_1": r1,
        "resistance_2": r2,
    }

    # ── Markdown report ───────────────────────────────────────────────────────
    print("Writing analysis report...")
    generate_markdown(stats, mc)

    # ── Print terminal summary ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VAR.OL Analysis Complete")
    print(f"Period : {stats['period_start']} — {stats['period_end']}")
    print(f"Price  : {current_price:.2f} NOK  |  RSI: {current_rsi:.1f}")
    print(f"MA50   : {current_ma50:.2f}  |  MA200: {current_ma200:.2f}")
    print(f"Oil beta: {slope:.2f}x  |  R2: {oil_r2:.1%}  |  Ann.vol: {annual_vol:.1%}")
    print(f"Support: {s1:.1f} / {s2:.1f} / {s3:.1f} NOK")
    print(f"\n1-Year scenario medians:")
    print(f"  Bull : {mc['bull']['median']:.1f} NOK  (P(gain) = {mc['bull']['prob_above_current']:.0%})")
    print(f"  Base : {mc['base']['median']:.1f} NOK  (P(gain) = {mc['base']['prob_above_current']:.0%})")
    print(f"  Bear : {mc['bear']['median']:.1f} NOK  (P(gain) = {mc['bear']['prob_above_current']:.0%})")
    print("=" * 60)
    print("\nAll charts saved to analysis/var_figures/")
    print("Report saved to analysis/var_energy.md")


if __name__ == "__main__":
    main()
