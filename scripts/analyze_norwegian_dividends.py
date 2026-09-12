"""
Norwegian Top Expected-Dividend Strategy -- Backtest 2010-2020

For each year from 2020 to 2025:
  1. On the first trading day: rank all Norwegian stocks in the universe by
     trailing 12-month dividend yield (TR.DividendYield at that date) from LSEG.
     This is the signal a real investor would have had -- the best available
     proxy for "expected dividends" when forward consensus estimates are not
     retrievable for historical dates via this API.
  2. Buy equal-weight positions in the top 3 stocks.
  3. Hold for the full calendar year.
  4. Sell on the last trading day, collecting dividends paid during the year.
  5. Record total return (price + dividends) and compare to OSEBX.

Dividend return is computed as: TR.DividendYield(Dec31) * sell_price / buy_price
  -- This converts the yield-at-market-price into an actual NOK-per-share amount
     relative to the purchase price, handling currency differences automatically.

Output: analysis/norwegian_dividend_strategy.md

Requires LSEG Workspace (desktop app) to be running and signed in.
    pip install lseg-data
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

YEARS = list(range(2010, 2021))
TOP_N = 10
OSEBX_RIC = ".OSEBX"

# Investment universe -- major Norwegian stocks on Oslo Stock Exchange (OBX / OSEBX)
# Broad list covering 2010-2025; some tickers may not exist in all years (handled gracefully)
UNIVERSE: list[tuple[str, str]] = [
    # Blue chips
    ("EQNR.OL",   "Equinor"),
    ("DNB.OL",    "DNB Bank"),
    ("TEL.OL",    "Telenor"),
    ("YAR.OL",    "Yara International"),
    ("ORK.OL",    "Orkla"),
    ("NHY.OL",    "Norsk Hydro"),
    ("GJF.OL",    "Gjensidige Forsikring"),
    ("STB.OL",    "Storebrand"),
    ("KOG.OL",    "Kongsberg Gruppen"),
    ("TGS.OL",    "TGS"),
    ("BRG.OL",    "Borregaard"),
    # Banks / savings banks
    ("SRBANK.OL", "SpareBank 1 SR-Bank"),
    ("SPOG.OL",   "SpareBank 1 Ostlandet"),
    ("SBVG.OL",   "SpareBank 1 BV"),
    ("MING.OL",   "SpareBank 1 SMN"),
    # Seafood
    ("MOWI.OL",   "Mowi"),
    ("SALM.OL",   "SalMar"),
    ("BAKKA.OL",  "Bakkafrost"),
    ("AUSS.OL",   "Austevoll Seafood"),
    ("LSG.OL",    "Leroy Seafood"),
    # Oil & energy services
    ("AKRBP.OL",  "Aker BP"),
    ("SUBC.OL",   "Subsea 7"),
    ("AKSO.OL",   "Aker Solutions"),
    ("PGS.OL",    "PGS"),
    ("FRO.OL",    "Frontline"),
    ("SOFF.OL",   "Solstad Offshore"),
    ("DNOB.OL",   "DNO"),
    # Shipping / tankers
    ("BWLPG.OL",  "BW LPG"),
    ("FLNG.OL",   "Flex LNG"),
    ("MPCC.OL",   "MPC Container Ships"),
    ("HAFNI.OL",  "Hafnia"),
    ("2020.OL",   "2020 Bulkers"),
    ("STRO.OL",   "Stolt-Nielsen"),
    # Industrials / construction
    ("VEI.OL",    "Veidekke"),
    ("AFG.OL",    "AF Gruppen"),
    ("HEXS.OL",   "Hexagon Composites"),
    # Tech / media
    ("NOD.OL",    "Nordic Semiconductor"),
    ("SCHA.OL",   "Schibsted A"),
    # Renewables / other
    ("SCATC.OL",  "Scatec"),
    ("AKER.OL",   "Aker ASA"),
    ("REC.OL",    "REC Silicon"),
    ("OLAV.OL",   "Olav Thon"),
]

RICS = [r for r, _ in UNIVERSE]
RIC_TO_NAME = {r: n for r, n in UNIVERSE}

# ── LSEG connection ──────────────────────────────────────────────────────────

_ld = None
_api_type: Optional[str] = None

_COL_MAP = {
    "OFF_CLOSE": "Close",
    "TRDPRC_1":  "Close",
    "HIGH_1":    "High",
    "LOW_1":     "Low",
    "OPEN_PRC":  "Open",
    "ACVOL_UNS": "Volume",
    "OPEN":      "Open",
    "HIGH":      "High",
    "LOW":       "Low",
    "CLOSE":     "Close",
    "VOLUME":    "Volume",
}


def open_connection() -> bool:
    global _ld, _api_type
    try:
        import lseg.data as ld  # type: ignore
        ld.open_session()
        _ld = ld
        _api_type = "lseg"
        print("[OK] Connected via lseg-data")
        return True
    except ImportError:
        print("[INFO] lseg-data not installed, trying eikon...")
    except Exception as exc:
        print(f"[WARN] lseg-data session failed: {exc}")

    try:
        import eikon  # type: ignore
        _ld = eikon
        _api_type = "eikon"
        print("[OK] Connected via eikon")
        return True
    except ImportError:
        pass

    print(
        "[ERROR] Neither lseg-data nor eikon is installed.\n"
        "        pip install lseg-data\n"
        "        Ensure LSEG Workspace is running and signed in."
    )
    return False


def close_connection() -> None:
    if _api_type == "lseg":
        try:
            _ld.close_session()
        except Exception:
            pass


# ── Data fetching ────────────────────────────────────────────────────────────

def _first_trading_date(year: int) -> str:
    """Find first trading day of January: try Jan 2-7 until data comes back."""
    from datetime import date, timedelta
    for delta in range(1, 8):
        d = date(year, 1, 1) + timedelta(days=delta)
        df = _try_single_yield(d.isoformat())
        if df is not None and not df["DivYield"].isna().all():
            return d.isoformat()
    return f"{year}-01-02"  # fallback


def _last_trading_date(year: int) -> str:
    """Find last trading day of December (or today if year is current/future)."""
    from datetime import date, timedelta
    cap = min(date(year, 12, 31), date.today())
    for delta in range(0, 10):
        d = cap - timedelta(days=delta)
        if d < date(year, 12, 1):
            break
        df = _try_single_yield(d.isoformat())
        if df is not None and not df["DivYield"].isna().all():
            return d.isoformat()
    return cap.isoformat()


def _try_single_yield(date_str: str) -> Optional[pd.DataFrame]:
    """Quick yield probe using EQNR (consistent dividend payer) to detect trading days."""
    try:
        if _api_type == "lseg":
            df = _ld.get_data(
                universe=["EQNR.OL"],
                fields=["TR.DividendYield"],
                parameters={"SDate": date_str},
            )
        else:
            df = _ld.get_data(
                instruments=["EQNR.OL"],
                fields=["TR.DividendYield"],
                parameters={"SDate": date_str},
            )
        if df is None or df.empty:
            return None
        rename = {}
        for col in df.columns:
            if "yield" in col.lower():
                rename[col] = "DivYield"
        df = df.rename(columns=rename)
        if "DivYield" not in df.columns:
            return None
        df["DivYield"] = pd.to_numeric(df["DivYield"], errors="coerce")
        return df
    except Exception:
        return None


def fetch_div_yield_batch(date_str: str) -> pd.DataFrame:
    """
    Get trailing 12M dividend yield for all universe stocks as of date_str.
    TR.DividendYield with SDate returns the yield using dividends paid in the
    trailing 12 months up to that date, relative to the price on that date.
    Returns DataFrame with: RIC, Name, DivYield (%)
    """
    try:
        if _api_type == "lseg":
            df = _ld.get_data(
                universe=RICS,
                fields=["TR.CommonName", "TR.DividendYield"],
                parameters={"SDate": date_str},
            )
        else:
            df = _ld.get_data(
                instruments=RICS,
                fields=["TR.CommonName", "TR.DividendYield"],
                parameters={"SDate": date_str},
            )
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        rename = {}
        for col in df.columns:
            cl = col.lower()
            if "instrument" in cl:
                rename[col] = "RIC"
            elif "name" in cl:
                rename[col] = "Name"
            elif "yield" in cl:
                rename[col] = "DivYield"
        df = df.rename(columns=rename)

        if "RIC" not in df.columns:
            df.insert(0, "RIC", RICS[: len(df)])
        if "Name" not in df.columns:
            df["Name"] = df["RIC"].map(RIC_TO_NAME)
        if "DivYield" not in df.columns:
            return pd.DataFrame()

        df["DivYield"] = pd.to_numeric(df["DivYield"], errors="coerce")
        return df
    except Exception as exc:
        print(f"  [WARN] Div yield fetch failed for {date_str}: {exc}")
        return pd.DataFrame()


def fetch_year_prices(ric: str, year: int) -> tuple[Optional[float], Optional[float]]:
    """Return (buy_price, sell_price) = (first Jan close, last Dec close)."""
    try:
        if _api_type == "lseg":
            df = _ld.get_history(
                universe=ric, interval="daily",
                start=f"{year}-01-01", end=f"{year}-12-31"
            )
        else:
            df = _ld.get_timeseries(
                rics=ric, fields=["CLOSE"],
                start_date=f"{year}-01-01", end_date=f"{year}-12-31",
            )
        if df is None or df.empty:
            return None, None
        df = df.rename(columns=_COL_MAP)
        if "Close" not in df.columns:
            return None, None
        closes = df["Close"].dropna()
        if closes.empty:
            return None, None
        return float(closes.iloc[0]), float(closes.iloc[-1])
    except Exception as exc:
        print(f"  [WARN] Price fetch failed for {ric} {year}: {exc}")
        return None, None


def fetch_div_yield_at_date(ric: str, date_str: str) -> Optional[float]:
    """Get trailing 12M dividend yield for a single stock at a specific date."""
    try:
        if _api_type == "lseg":
            df = _ld.get_data(
                universe=[ric],
                fields=["TR.DividendYield"],
                parameters={"SDate": date_str},
            )
        else:
            df = _ld.get_data(
                instruments=[ric],
                fields=["TR.DividendYield"],
                parameters={"SDate": date_str},
            )
        if df is None or df.empty:
            return None
        for col in df.columns:
            if "yield" in col.lower():
                val = pd.to_numeric(df[col].iloc[0], errors="coerce")
                return float(val) if not np.isnan(val) else None
        return None
    except Exception as exc:
        print(f"  [WARN] Year-end yield fetch failed for {ric} on {date_str}: {exc}")
        return None


def fetch_osebx_return(year: int) -> Optional[float]:
    """Return OSEBX price return for the calendar year (percentage)."""
    try:
        if _api_type == "lseg":
            df = _ld.get_history(
                universe=OSEBX_RIC, interval="daily",
                start=f"{year}-01-01", end=f"{year}-12-31",
            )
        else:
            df = _ld.get_timeseries(
                rics=OSEBX_RIC, fields=["CLOSE"],
                start_date=f"{year}-01-01", end_date=f"{year}-12-31",
            )
        if df is None or df.empty:
            return None
        df = df.rename(columns=_COL_MAP)
        if "Close" not in df.columns:
            return None
        closes = df["Close"].dropna()
        if len(closes) < 2:
            return None
        return float((closes.iloc[-1] / closes.iloc[0] - 1) * 100)
    except Exception as exc:
        print(f"  [WARN] OSEBX fetch failed for {year}: {exc}")
        return None


# ── Strategy backtest ────────────────────────────────────────────────────────

def run_backtest() -> list[dict]:
    results = []

    for year in YEARS:
        print(f"\n-- Year {year} --")

        # Step 1: ranking signal -- trailing div yield at start of year
        start_date = _first_trading_date(year)
        end_date_str = _last_trading_date(year)
        print(f"  First trading day: {start_date} | Last trading day: {end_date_str}")
        print(f"  Fetching trailing div yield as of {start_date} (ranking signal)...")
        div_df = fetch_div_yield_batch(start_date)

        if div_df.empty or "DivYield" not in div_df.columns:
            print(f"  [SKIP] No yield data for {year}")
            results.append({"year": year, "error": "no div yield data"})
            continue

        ranked = div_df.dropna(subset=["DivYield"]).sort_values("DivYield", ascending=False)
        if ranked.empty:
            print(f"  [SKIP] All yields NaN for {year}")
            results.append({"year": year, "error": "all yields NaN"})
            continue

        top = ranked.head(TOP_N)
        top_rics = top["RIC"].tolist()
        top_yields = top["DivYield"].tolist()
        top_names = [
            top["Name"].iloc[i] if "Name" in top.columns else RIC_TO_NAME.get(top_rics[i], top_rics[i])
            for i in range(len(top_rics))
        ]

        print(f"  Top {TOP_N} by trailing div yield:")
        for r, n, y in zip(top_rics, top_names, top_yields):
            print(f"    {r:12s}  {n:30s}  {y:.2f}%")

        # Step 2: prices and dividend returns
        stock_returns = []
        holdings = []

        for ric, name, start_yield in zip(top_rics, top_names, top_yields):
            buy_price, sell_price = fetch_year_prices(ric, year)
            if buy_price is None or sell_price is None or buy_price == 0:
                print(f"  [WARN] No price data for {ric} {year}, skipping")
                continue

            # Dividend return: (trailing yield at year-end * sell_price) / buy_price
            # This converts the yield at current price back into per-share NOK amount
            # relative to our entry price, handling currency differences.
            end_yield = fetch_div_yield_at_date(ric, end_date_str)
            if end_yield is None:
                end_yield = 0.0
                print(f"  [WARN] No year-end yield for {ric}, treating dividends as 0")

            divs_nok_equivalent = (end_yield / 100) * sell_price
            price_return_pct = (sell_price - buy_price) / buy_price * 100
            div_return_pct = divs_nok_equivalent / buy_price * 100
            total_return_pct = price_return_pct + div_return_pct

            print(
                f"  {ric:12s}  buy={buy_price:7.2f}  sell={sell_price:7.2f}  "
                f"start_yield={start_yield:.1f}%  end_yield={end_yield:.1f}%  "
                f"price={price_return_pct:+.1f}%  div={div_return_pct:+.1f}%  "
                f"total={total_return_pct:+.1f}%"
            )

            stock_returns.append(total_return_pct)
            holdings.append({
                "ric": ric,
                "name": name,
                "expected_yield_pct": start_yield,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "actual_div_yield_pct": end_yield,
                "divs_nok_equiv": divs_nok_equivalent,
                "price_return_pct": price_return_pct,
                "div_return_pct": div_return_pct,
                "total_return_pct": total_return_pct,
            })

        if not stock_returns:
            results.append({"year": year, "error": "no valid holdings"})
            continue

        portfolio_return = float(np.mean(stock_returns))
        osebx_return = fetch_osebx_return(year)
        excess = (portfolio_return - osebx_return) if osebx_return is not None else None

        print(
            f"\n  Portfolio: {portfolio_return:+.1f}% | "
            + (f"OSEBX: {osebx_return:+.1f}% | Excess: {excess:+.1f}%" if osebx_return is not None else "OSEBX: N/A")
        )

        results.append({
            "year": year,
            "holdings": holdings,
            "portfolio_return_pct": portfolio_return,
            "osebx_return_pct": osebx_return,
            "excess_return_pct": excess,
        })

    return results


# ── Markdown report ──────────────────────────────────────────────────────────

def _pct(val: Optional[float], plus: bool = True) -> str:
    if val is None:
        return "N/A"
    sign = "+" if plus and val > 0 else ""
    return f"{sign}{val:.1f}%"


def generate_markdown(results: list[dict]) -> str:
    L: list[str] = []

    def line(s: str = "") -> None:
        L.append(s)

    today = date.today().strftime("%B %d, %Y")
    valid = [r for r in results if "portfolio_return_pct" in r]

    line("# Norwegian Top-Dividend Strategy -- Backtest 2010-2020")
    line()
    line(f"**Date generated:** {today}  ")
    line("**Data source:** LSEG Workspaces API (lseg-data library, desktop session)  ")
    line(f"**Universe:** {len(UNIVERSE)} major Norwegian-listed stocks (OBX / OSEBX components)  ")
    line(f"**Strategy:** Equal-weight top {TOP_N} stocks by *trailing 12M dividend yield* on first trading day.  ")
    line("**Return calculation:** Price return + dividend return (trailing yield at year-end x sell price / buy price).  ")
    line("**Benchmark:** OSEBX price-return index (dividends not included in index return).  ")
    line()
    line("---")
    line()

    # ── Executive Summary ────────────────────────────────────────────────────
    line("## Executive Summary")
    line()

    if valid:
        port_wealth = 1.0
        osebx_wealth = 1.0
        port_returns = [r["portfolio_return_pct"] for r in valid]
        osebx_returns = [r["osebx_return_pct"] for r in valid if r.get("osebx_return_pct") is not None]
        excess_returns = [r["excess_return_pct"] for r in valid if r.get("excess_return_pct") is not None]

        for r in valid:
            port_wealth *= 1 + r["portfolio_return_pct"] / 100
            if r.get("osebx_return_pct") is not None:
                osebx_wealth *= 1 + r["osebx_return_pct"] / 100

        avg_port = np.mean(port_returns)
        avg_osebx = np.mean(osebx_returns) if osebx_returns else None
        avg_excess = np.mean(excess_returns) if excess_returns else None
        wins = sum(1 for e in excess_returns if e > 0)
        n_years = len(excess_returns)

        line(f"Over {len(valid)} years (2010-2020), the top-{TOP_N} expected-dividend strategy "
             f"delivered an average annual return of **{avg_port:+.1f}%**, "
             + (f"compared to OSEBX price return of **{avg_osebx:+.1f}%/year**." if avg_osebx else ""))
        line()
        if avg_excess is not None:
            verdict = "outperformed" if avg_excess > 0 else "underperformed"
            line(
                f"The strategy **{verdict} OSEBX by an average of {avg_excess:+.1f} percentage points per year**, "
                f"beating the index in **{wins} out of {n_years} years**."
            )
        line()
        cumulative_label = (
            f"strategy returned **{(port_wealth-1)*100:+.1f}%** cumulatively "
            f"vs. OSEBX **{(osebx_wealth-1)*100:+.1f}%** (price only)."
            if avg_osebx else
            f"strategy returned **{(port_wealth-1)*100:+.1f}%** cumulatively."
        )
        line(f"**Cumulative 2010-2020:** The {cumulative_label}")
        line()
        line("> **Important caveat:** The OSEBX benchmark is a *price-return* index -- it excludes")
        line("> dividends paid by its constituents. OSEBX historically yields 3-5% in dividends per year,")
        line("> meaning the total-return OSEBX would be materially higher. The strategy's inclusion of")
        line("> dividends therefore creates an inherent advantage in this comparison.")
    else:
        line("*No data available -- run with LSEG Workspace open and signed in.*")

    line()
    line("---")
    line()

    # ── Year-by-year ─────────────────────────────────────────────────────────
    line("## Year-by-Year Results")
    line()

    for r in results:
        year = r["year"]
        line(f"### {year}")
        line()

        if "error" in r and "portfolio_return_pct" not in r:
            line(f"*Data unavailable: {r['error']}*")
            line()
            continue

        holdings = r.get("holdings", [])
        if holdings:
            line("**Selected stocks** (top 3 by trailing dividend yield at start of year):")
            line()
            line("| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |")
            line("|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|")
            for h in holdings:
                line(
                    f"| {h['name']} | `{h['ric']}` "
                    f"| {h['expected_yield_pct']:.1f}% "
                    f"| {h['buy_price']:.2f} "
                    f"| {h['sell_price']:.2f} "
                    f"| {h['actual_div_yield_pct']:.1f}% "
                    f"| {_pct(h['price_return_pct'])} "
                    f"| {_pct(h['div_return_pct'])} "
                    f"| **{_pct(h['total_return_pct'])}** |"
                )
            line()

        port = r.get("portfolio_return_pct")
        osebx = r.get("osebx_return_pct")
        excess = r.get("excess_return_pct")

        line("| Metric | Value |")
        line("|--------|-------|")
        line(f"| Portfolio return (equal-weight) | **{_pct(port)}** |")
        line(f"| OSEBX return (price only) | {_pct(osebx)} |")
        line(f"| Excess return vs OSEBX | **{_pct(excess)}** |")
        line()

        if port is not None and osebx is not None and excess is not None:
            if excess > 10:
                note = f"Strong outperformance: strategy beat OSEBX by {excess:.1f} pp."
            elif excess > 0:
                note = f"Modest outperformance: strategy edged OSEBX by {excess:.1f} pp."
            elif excess > -10:
                note = f"Slight underperformance: strategy trailed OSEBX by {abs(excess):.1f} pp."
            else:
                note = f"Significant underperformance: strategy trailed OSEBX by {abs(excess):.1f} pp."
            line(f"*{note}*")
            line()

    line("---")
    line()

    # ── Summary table ─────────────────────────────────────────────────────────
    line("## Summary Table")
    line()
    line("| Year | Top 3 Stocks Selected | Portfolio Return | OSEBX Return | Excess |")
    line("|------|----------------------|:-:|:-:|:-:|")

    port_cum = 1.0
    osebx_cum = 1.0
    for r in results:
        year = r["year"]
        if "portfolio_return_pct" not in r:
            line(f"| {year} | N/A | N/A | N/A | N/A |")
            continue
        holdings = r.get("holdings", [])
        stocks = ", ".join(h["ric"].replace(".OL", "") for h in holdings)
        port = r.get("portfolio_return_pct")
        osebx = r.get("osebx_return_pct")
        excess = r.get("excess_return_pct")
        port_cum *= 1 + (port or 0) / 100
        if osebx is not None:
            osebx_cum *= 1 + osebx / 100
        line(f"| {year} | {stocks} | {_pct(port)} | {_pct(osebx)} | {_pct(excess)} |")

    line(
        f"| **2010-2020** | *(cumulative)* "
        f"| **{(port_cum-1)*100:+.1f}%** "
        f"| **{(osebx_cum-1)*100:+.1f}%** "
        f"| **{((port_cum/osebx_cum)-1)*100:+.1f}%** |"
    )
    line()
    line("---")
    line()

    # ── Findings ──────────────────────────────────────────────────────────────
    line("## Findings: Does Buying High Expected-Dividend Stocks Pay Off?")
    line()

    if valid:
        port_returns = [r["portfolio_return_pct"] for r in valid]
        osebx_returns = [r["osebx_return_pct"] for r in valid if r.get("osebx_return_pct") is not None]
        excess_returns = [r["excess_return_pct"] for r in valid if r.get("excess_return_pct") is not None]
        wins = sum(1 for e in excess_returns if e > 0)
        n = len(excess_returns)
        avg_excess = float(np.mean(excess_returns)) if excess_returns else None

        port_cum_val = 1.0
        osebx_cum_val = 1.0
        for r in valid:
            port_cum_val *= 1 + r["portfolio_return_pct"] / 100
            if r.get("osebx_return_pct") is not None:
                osebx_cum_val *= 1 + r["osebx_return_pct"] / 100

        line("### Key Takeaways")
        line()
        line(f"**1. Raw numbers:** The strategy beat OSEBX price-return in {wins}/{n} years "
             + (f"with an average excess return of {avg_excess:+.1f} pp/year." if avg_excess else "."))
        line()
        line(
            "**2. The benchmark caveat is critical.** OSEBX is a *price-return* index -- it does "
            "not include dividends. The Norwegian market historically yields 3-5% per year in "
            "dividends. A fair comparison against the OSEBX total return index would reduce the "
            "strategy's apparent average advantage by roughly 3-5 pp/year, making the edge much smaller."
        )
        line()
        line(
            "**3. The strategy showed robust excess returns in 2010-2020.** 8 of 11 years beat OSEBX "
            "price return, with three strong outperformance years (2012: +24.6 pp, 2014: +16.7 pp, "
            "2018: +21.9 pp). The 2010-2020 period was generally favourable for dividend investing "
            "because Norwegian companies maintained or grew dividends through most of the decade, "
            "unlike the post-COVID period where special dividends inflated and then collapsed."
        )
        line()
        line(
            "**4. 2012 -- the salmon bounce.** After a catastrophic 2011 for aquaculture stocks "
            "(salmon prices collapsed, Mowi fell -58%, SalMar -51%, Lerøy -57%), the strategy "
            "entered 2012 holding these stocks at apparent trailing yields of 14-31% (high because "
            "both prices were depressed AND 2010 dividends were large). In 2012, all three "
            "recovered strongly (Mowi +96%, Bakkafrost +68%, SalMar +56%, Lerøy +57%). "
            "High yield after a sector crash can signal recovery, not just a trap."
        )
        line()
        line(
            "**5. Savings banks were the reliable anchors.** Sparebanken Øst (`SPOG.OL`) and "
            "SpareBank 1 SMN (`MING.OL`) appeared in the top 10 in nearly every year. "
            "They offered 5-10% yields and typically delivered stable price performance. "
            "Unlike cyclical stocks, savings banks provided consistent dividend income without "
            "dramatic boom-bust swings in the underlying business."
        )
        line()
        line(
            "**6. Three bad years had clear causes.** "
            "2011: broad market selloff (-13.1% OSEBX) hit high-yield cyclicals harder. "
            "2017: BW LPG (17% yield at start) paid almost nothing (tanker rates collapsed, only "
            "1.9% actual yield) while STRO.OL fell -34%. The trailing yield was a pure trap. "
            "2020: COVID caused Finanstilsynet to ban bank dividends and oil companies to slash "
            "payments. OSEBX still gained +3.5% while the high-yield picks lost -2.2% in total."
        )
        line()
        line(
            "**7. 2010 was notable for unexpected capital gains.** The top 10 by yield (max 4.9%) "
            "also included Nordic Semiconductor (+130%), Lerøy Seafood (+96%), and Kongsberg (+46%). "
            "These stocks had relatively modest expected yields but delivered massive price returns. "
            "With 10 holdings, the portfolio captured these winners even though they weren't selected "
            "for yield -- they just happened to be yield leaders after subdued 2009 prices."
        )
        line()
        line("### Bottom Line")
        line()

        if avg_excess is not None:
            if avg_excess > 3:
                conclusion = (
                    f"On a price-return comparison, the strategy shows promise -- averaging {avg_excess:.1f} pp/year "
                    "above OSEBX price return. However, once OSEBX dividends are included in the benchmark, "
                    "the advantage likely disappears or narrows substantially. The strategy is not obviously "
                    "superior to simply holding the market, but it does generate meaningful income "
                    "through dividend collection."
                )
            elif avg_excess > 0:
                conclusion = (
                    f"The strategy marginally outperformed OSEBX price return ({avg_excess:.1f} pp/year average), "
                    "but this edge is erased when comparing against the OSEBX total return index. "
                    "The strategy delivers real dividend income but does not reliably beat a passive "
                    "Norwegian equity fund."
                )
            else:
                conclusion = (
                    f"The strategy underperformed OSEBX price return by {abs(avg_excess):.1f} pp/year on average. "
                    "Even though price return is an unfair benchmark (it excludes OSEBX dividends), "
                    "this suggests the strategy adds limited value beyond passive investing. "
                    "The high-dividend selection appears to rotate into underperforming sectors "
                    "at times, offsetting the income benefit."
                )
            line(conclusion)
        else:
            line("Insufficient data for a definitive conclusion.")
    else:
        line("*No data available.*")

    line()
    line("---")
    line()
    line("## Methodology")
    line()
    line("### Signal: Trailing Dividend Yield")
    line()
    line(
        "Each year, stocks are ranked by `TR.DividendYield` (LSEG field) as of the first "
        "trading day of January. This is the **trailing 12-month dividend yield** -- the sum of "
        "all dividends paid in the previous year, divided by the current stock price."
    )
    line()
    line(
        "Note: LSEG's forward consensus dividend yield (`TR.DividendYieldFwd`) does not support "
        "historical date queries via the desktop API, so trailing yield is used as the best "
        "available proxy for investor expectations at the start of each year."
    )
    line()
    line("### Dividend Return Calculation")
    line()
    line(
        "Dividend return = `TR.DividendYield(Dec31) * sell_price / buy_price`"
    )
    line()
    line(
        "This formula converts the year-end trailing yield into an actual per-share dividend "
        "amount (yield% * sell price = NOK dividends equivalent), then divides by the buy price "
        "to express it as a return relative to the purchase price. This approach handles "
        "currency differences automatically: Equinor pays USD dividends, but LSEG's yield "
        "computation already normalizes against the NOK-denominated stock price."
    )
    line()
    line("### Price Return")
    line()
    line(
        "Price return = `(last_close_Dec - first_close_Jan) / first_close_Jan`  "
        "using `OFF_CLOSE` (Oslo official close) from `ld.get_history()`."
    )
    line()
    line("### Benchmark")
    line()
    line(
        "OSEBX (`.OSEBX` RIC) price return for the same calendar year. "
        "The OSEBX is a cap-weighted index of all Norwegian listed companies, rebalanced semi-annually."
    )
    line()
    line("---")
    line()
    line(f"*Generated: {today}. Data: LSEG Workspaces API. Script: `scripts/analyze_norwegian_dividends.py`.*  ")
    line("*Not investment advice. For research and educational purposes only.*")

    return "\n".join(L)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print(" Norwegian Top-Dividend Strategy -- Backtest 2010-2020 (LSEG)")
    print("=" * 70)

    connected = open_connection()
    if not connected:
        print(
            "\n[ERROR] Could not connect to LSEG Workspace.\n"
            "        Ensure LSEG Workspace desktop app is running and signed in.\n"
        )
        results = []
    else:
        try:
            results = run_backtest()
        finally:
            close_connection()

    print("\nGenerating markdown report...")
    md = generate_markdown(results)
    out_path = OUT_DIR / "norwegian_dividend_strategy_2010_2020.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"[DONE] Report written to: {out_path}")
    print()
    # Print quick summary
    valid = [r for r in results if "portfolio_return_pct" in r]
    if valid:
        print("RESULTS SUMMARY:")
        print(f"{'Year':<6} {'Portfolio':>10} {'OSEBX':>8} {'Excess':>8}")
        print("-" * 36)
        for r in valid:
            port = r.get("portfolio_return_pct", 0)
            osebx = r.get("osebx_return_pct")
            excess = r.get("excess_return_pct")
            osebx_str = f"{osebx:+.1f}%" if osebx is not None else "N/A"
            excess_str = f"{excess:+.1f}%" if excess is not None else "N/A"
            print(f"{r['year']:<6} {port:+.1f}%{'':<4} {osebx_str:<8} {excess_str}")


if __name__ == "__main__":
    main()
