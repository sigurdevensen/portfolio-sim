"""Analyze DNB ASA and DNB Carnegie using LSEG Workspaces API.

Fetches:
  - DNB.OL daily price history
  - Key financial fundamentals (PE, ROE, market cap, etc.)
  - Recent news headlines tagged to DNB.OL and "Carnegie" (past 120 days)
  - Full story text for the most significant headlines

Output:
  analysis/dnb_analysis.md  — comprehensive markdown report

Requires LSEG Workspace to be running on the desktop.
    pip install lseg-data        (recommended)
    pip install eikon            (legacy fallback)
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

DNB_RIC = "DNB.OL"
HISTORY_START = "2022-01-01"
NEWS_DAYS_BACK = 120
NEWS_COUNT = 50

# ── LSEG connection ───────────────────────────────────────────────────────────

_ld = None
_api_type: Optional[str] = None


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
        "        Make sure LSEG Workspace is running and you are signed in."
    )
    return False


def close_connection() -> None:
    if _api_type == "lseg":
        try:
            _ld.close_session()
        except Exception:
            pass


# ── Price history ─────────────────────────────────────────────────────────────

_COL_MAP = {
    "OFF_CLOSE": "Close",   # Oslo Bors official close
    "TRDPRC_1": "Close",
    "HIGH_1": "High",
    "LOW_1": "Low",
    "OPEN_PRC": "Open",
    "ACVOL_UNS": "Volume",
    "OPEN": "Open",
    "HIGH": "High",
    "LOW": "Low",
    "CLOSE": "Close",
    "VOLUME": "Volume",
}


def fetch_price_history() -> pd.DataFrame:
    if _api_type == "lseg":
        df = _ld.get_history(
            universe=DNB_RIC,
            interval="daily",
            start=HISTORY_START,
            end=date.today().isoformat(),
        )
    else:
        df = _ld.get_timeseries(
            rics=DNB_RIC,
            fields=["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
            start_date=HISTORY_START,
            end_date=date.today().isoformat(),
        )
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=_COL_MAP)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]


def compute_price_stats(df: pd.DataFrame) -> dict:
    if df.empty or "Close" not in df.columns:
        return {}
    prices = df["Close"].dropna()
    if prices.empty:
        return {}

    returns = prices.pct_change().dropna()

    one_year_back = prices.index[-1] - pd.DateOffset(weeks=52)
    yearly = prices[prices.index >= one_year_back]

    year_start = pd.Timestamp(f"{date.today().year}-01-01")
    ytd = prices[prices.index >= year_start]

    pd_str = prices.index[-1].strftime("%Y-%m-%d") if hasattr(prices.index[-1], "strftime") else str(prices.index[-1])[:10]

    # Drawdown from running max
    running_max = prices.cummax()
    drawdowns = (prices - running_max) / running_max * 100

    return {
        "current_price": prices.iloc[-1],
        "price_date": pd_str,
        "52w_high": yearly.max() if not yearly.empty else None,
        "52w_low": yearly.min() if not yearly.empty else None,
        "ytd_return_pct": (ytd.iloc[-1] / ytd.iloc[0] - 1) * 100 if len(ytd) > 1 else None,
        "1y_return_pct": (yearly.iloc[-1] / yearly.iloc[0] - 1) * 100 if len(yearly) > 1 else None,
        "annualised_vol_pct": returns.std() * np.sqrt(252) * 100,
        "max_drawdown_pct": drawdowns.min(),
    }


# ── Fundamentals ──────────────────────────────────────────────────────────────

_FUND_FIELDS = [
    "TR.NetIncome",
    "TR.TotalAssets",
    "TR.EPS",
    "TR.DividendYield",
    "TR.PE",
    "TR.CompanyMarketCap",
    "TR.ROE",
    "TR.PriceToBookValue",
]

# Maps actual LSEG column names → our internal keys
_FUND_COL_REMAP = {
    "Net Income Incl Extra Before Distributions": "net_income",
    "Total Assets": "total_assets",
    "EPS": "eps",
    "Dividend yield": "div_yield",
    "P/E (Daily Time Series Ratio)": "pe",
    "Company Market Cap": "market_cap",
    "Return on Equity - Actual": "roe",
    "Price To Book Value Per Share": "pb",
    "Revenue": "revenue",
}


def fetch_fundamentals() -> dict:
    try:
        if _api_type == "lseg":
            df = _ld.get_data(universe=[DNB_RIC], fields=_FUND_FIELDS)
        else:
            df = _ld.get_data(instruments=[DNB_RIC], fields=_FUND_FIELDS)
        if df is not None and not df.empty:
            raw = df.iloc[0].to_dict()
            # Remap column names to our internal keys
            result: dict = {}
            for col, val in raw.items():
                key = _FUND_COL_REMAP.get(col, col)
                result[key] = val
            return result
    except Exception as exc:
        print(f"[WARN] Fundamentals fetch failed: {exc}")
    return {}


# ── News ──────────────────────────────────────────────────────────────────────

_NOISE_RE = (
    r"\+NOK|\-NOK|\+\$|\[[\d.]+%\]"
    r"|percent lower|percent higher"
    r"|gains \d+\.\d+%|ticks down|ticks up|in negative territory"
    r"|pre-market bullish|pre-market confirmatory"
    r"|ADR nudges|ICYMI:|Opens at|stock sees decline|stock sees rise"
    r"|previous trading day|strengthens \d+%|strengthens \d+ percent"
    r"|short interest update|Ohlson O-Score"
    r"|Can .* rebound|Will .* bounce|How Far Can"
    r"|PONY.*quarterly|NASDAQ:PONY"
)


def fetch_news(query: str, count: int = NEWS_COUNT, filter_noise: bool = True) -> list[dict]:
    start_str = (date.today() - timedelta(days=NEWS_DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        if _api_type == "lseg":
            headlines = _ld.news.get_headlines(
                query=query,
                count=count,
                start=start_str,
            )
        else:
            headlines = _ld.get_news_headlines(
                query=query,
                count=count,
                date_from=start_str,
                date_to=date.today().isoformat(),
            )
        if headlines is None or (hasattr(headlines, "empty") and headlines.empty):
            return []
        if isinstance(headlines, pd.DataFrame):
            if filter_noise:
                mask = ~headlines["headline"].str.contains(
                    _NOISE_RE, regex=True, na=False, case=False
                )
                headlines = headlines[mask]
            return headlines.reset_index().to_dict("records")
        return list(headlines)
    except Exception as exc:
        print(f"[WARN] News fetch failed for '{query}': {exc}")
        return []


def fetch_story(story_id: str) -> Optional[str]:
    try:
        if _api_type == "lseg":
            return _ld.news.get_story(story_id=story_id)
        else:
            return _ld.get_news_story(story_id=story_id)
    except Exception:
        return None


# ── News categorisation ───────────────────────────────────────────────────────

_THEME_KEYWORDS: dict[str, list[str]] = {
    "Acquisition & M&A (Carnegie / Luminor)": [
        "carnegie", "acquisit", "merger", "oppkjøp", "overtakelse", "kjøp av",
        "investment bank", "investmentbank", "luminor", "otp bank",
    ],
    "Financial Results & Earnings": [
        "quarterly earnings", "quarterly report", "result", "profit", "revenue",
        "kvartal", "regnskap", "årsresultat", "beats expectations", "hits estimates",
        "q1", "q2", "q3", "q4", "annual report",
    ],
    "Analyst Ratings & Target Prices": [
        "target price", "raises target", "cuts target", "upgrade", "downgrade",
        "overweight", "underweight", "buy rating", "hold rating", "neutral rating",
        "price target", "research report", "analyst",
    ],
    "Credit Quality & Loan Book": [
        "credit", "loan", "default", "npl", "provision", "impairment",
        "mislighold", "utlån", "kredittap", "tap på utlån",
    ],
    "Interest Rates & Monetary Policy": [
        "interest rate", "rate hike", "rate cut", "norges bank", "rente",
        "inflation", "inflasjon", "sentralbank", "pengepolitikk",
    ],
    "Regulatory & Capital": [
        "capital", "cet1", "tier 1", "regulation", "compliance", "finanstilsynet",
        "buffer", "baseliii", "regulato",
    ],
    "Markets & Investment Banking": [
        "ipo", "bond", "equity capital", "obligasjon",
        "børsnotering", "emisjon", "kapitalmarked", "capital market",
    ],
    "ESG & Sustainability": [
        "esg", "climate", "sustainability", "green bond", "klima",
        "bærekraft", "fossil", "renewable",
    ],
    "Leadership & Governance": [
        "ceo", "board", "director", "appoint", "resign", "styre",
        "administrerende direktør", "konsernsjef",
    ],
    "Dividends & Capital Returns": [
        "dividend", "buyback", "repurchase", "utbytte", "tilbakekjøp",
        "capital return", "payout", "year-high", "52-week high",
    ],
}


def categorise_news(items: list[dict]) -> dict[str, list[dict]]:
    themes: dict[str, list[dict]] = {k: [] for k in _THEME_KEYWORDS}
    themes["Other"] = []
    for item in items:
        text = (
            item.get("headline") or item.get("text") or item.get("Text") or ""
        ).lower()
        assigned = False
        for theme, kws in _THEME_KEYWORDS.items():
            if any(kw in text for kw in kws):
                themes[theme].append(item)
                assigned = True
                break
        if not assigned:
            themes["Other"].append(item)
    return {k: v for k, v in themes.items() if v}


# ── Scenario templates (static research) ─────────────────────────────────────

_CASES: dict[str, dict[str, str]] = {
    "Acquisition & M&A (Carnegie / Luminor)": {
        "bull": (
            "The combined DNB Carnegie franchise becomes the dominant Nordic investment bank for "
            "Norwegian issuers. Cross-selling DNB's corporate relationships to Carnegie's ECM/M&A "
            "capabilities unlocks deal flow previously lost to Nordea and international banks. "
            "Synergies hit the high end of guidance (NOK 400M+/yr); key Carnegie bankers are "
            "retained through generous long-term incentives. By year 3, the acquisition is "
            "EPS-accretive by 8–12% and DNB trades at a premium to European banking peers. "
            "**Luminor sale to OTP Bank (announced July 27, 2026):** DNB receives cash proceeds "
            "from its Luminor stake, boosting CET1 by ~30–50bp and enabling an accelerated "
            "buyback — immediate capital release on top of the long-term Carnegie value."
        ),
        "bear": (
            "Integration proves harder than expected. Carnegie's partnership culture clashes with "
            "DNB's more hierarchical commercial banking model. Senior equity research analysts and "
            "M&A bankers defect to competitors (Pareto Securities, Arctic Securities, SEB). "
            "The Norwegian IPO and M&A market remains subdued, meaning the acquired pipeline "
            "generates less revenue than projected. Goodwill of NOK 2–4B is written down "
            "partially; the deal is seen as a value-destroying distraction. CET1 ratio dips, "
            "constraining buybacks. Separately, the Luminor sale to OTP Bank (a Hungarian "
            "bank with Russian market exposure) faces Baltic regulatory scrutiny — delays "
            "in closing the deal could postpone the capital release."
        ),
        "base": (
            "Integration proceeds on schedule but synergies materialise slowly. One-off costs "
            "(NOK 300–500M) weigh on 2025–2026 earnings. By 2027, DNB Carnegie begins winning "
            "meaningful IPO and M&A mandates. The Luminor divestiture to OTP Bank closes "
            "successfully by late 2026, releasing capital that supports continued buybacks "
            "or dividend growth. Fee income from the combined entity grows at a mid-single-digit "
            "rate. The acquisition is mildly EPS-accretive by year 3."
        ),
    },
    "Analyst Ratings & Target Prices": {
        "bull": (
            "Multiple broker upgrades converge simultaneously. **Nordea Equity Research (Buy, April 9)**"
            " and **Barclays (Overweight, April 8)** upgrades in early Q2 2026 were followed by "
            "**Deutsche Bank raising its target price from NOK 286 to NOK 298 (July 30)**. "
            "The stock has hit 52-week highs 8 times in 3 months and is trading near NOK 304. "
            "If further upgrades materialise — particularly from Morgan Stanley (currently "
            "Underweight) reversing their cautious stance — the stock re-rates above NOK 320–330."
        ),
        "bear": (
            "**Morgan Stanley's Underweight rating (June 24, 2026)** reflects genuine concerns "
            "about NIM headwinds from Norges Bank cuts, Carnegie integration risk, and "
            "valuation stretched at ~1.5× book value after the strong run. Zacks downgraded "
            "from Strong-Buy to Hold in May 2026, suggesting the near-term return/risk balance "
            "is less attractive. A reversal in Norwegian rate expectations could trigger "
            "a de-rating, pulling the stock back toward NOK 250–270."
        ),
        "base": (
            "The consensus view is broadly constructive but not unanimous. The balance of "
            "upgrades (Nordea, Barclays) and cautious voices (Morgan Stanley, Zacks Hold) "
            "reflects genuine uncertainty about rate trajectory and integration execution. "
            "Deutsche Bank's raised target of NOK 298 is below the current trading price "
            "(NOK 303.90), implying limited upside at current levels from their model. "
            "Expect consolidation near NOK 280–310, with direction determined by Q2 2026 "
            "results and Norges Bank guidance."
        ),
    },
    "Financial Results & Earnings": {
        "bull": (
            "Norwegian rates remain elevated through 2025; NIM holds at 1.6–1.8% on the mortgage "
            "book. DNB reports ROE of 16%+ for the third consecutive year. Cost efficiency gains "
            "from digital banking push cost-to-income below 38%. Earnings per share grow 8–10% "
            "year-on-year. Dividend per share is raised 10%+ and a supplementary buyback is "
            "announced. The stock re-rates from 1.3× to 1.5× book value."
        ),
        "bear": (
            "Norges Bank cuts rates faster than expected; NIM compresses 25–30bp in 12 months. "
            "Carnegie integration costs hit reported earnings. Rising provisions for CRE and "
            "SME loans add further drag. ROE falls to 12–13%, below the 13% target. "
            "Dividend is maintained but no buyback. EPS misses consensus by 10–15%; "
            "the stock de-rates to 1.0–1.1× book."
        ),
        "base": (
            "DNB delivers solid but not spectacular results. NIM compresses slightly as Norges Bank "
            "begins a gradual easing cycle (2–3 cuts of 25bp), offset by modest loan growth and "
            "fee income recovery. ROE of 14–15% — above target. Dividend per share grows in "
            "line with earnings. Buybacks continue at a steady pace. EPS grows 3–5% annually."
        ),
    },
    "Credit Quality & Loan Book": {
        "bull": (
            "Norwegian economy remains remarkably resilient. Unemployment stays below 4%; house "
            "prices stabilise after 2023–2024 weakness. DNB's NPL ratio remains below 0.5% "
            "(near historic lows). CRE portfolio is well-collateralised; no material write-downs. "
            "Provisions stay low, boosting bottom-line earnings. DNB's credit quality becomes a "
            "positive differentiator vs. European banking peers with greater CRE exposure."
        ),
        "bear": (
            "Norwegian house prices fall 15–20% from peak as sustained high rates squeeze "
            "highly leveraged households. LTVs on the mortgage book rise; provisions increase "
            "significantly. SME credit quality deteriorates in interest-rate-sensitive sectors "
            "(construction, retail, hospitality). CRE in Oslo and Bergen faces a harder correction "
            "than currently priced. Net credit losses rise from <0.1% to 0.3–0.4% of loans — "
            "manageable, but a material earnings drag."
        ),
        "base": (
            "Credit quality normalises from historically excellent 2021–2023 levels. NPL ratio "
            "ticks up modestly from <0.5% to 0.6–0.8%. Provisions increase slightly but remain "
            "well below the long-run average. The Norwegian economy avoids recession; household "
            "debt stress is real but contained. CRE is the main watch area but systemic risk "
            "is low. Overall credit cost remains within the guidance range of 0.1–0.2% of loans."
        ),
    },
    "Interest Rates & Monetary Policy": {
        "bull": (
            "Norwegian inflation proves stickier than the ECB/Fed cycle suggests. Norges Bank "
            "holds rates at 4.5% through end-2025 and cuts only twice in 2026. DNB earns an "
            "extra NOK 1–2B in net interest income per year relative to a faster-cutting scenario. "
            "Market re-prices DNB earnings upgrades; stock rises 10–15%."
        ),
        "bear": (
            "Norges Bank front-loads cuts (4+ cuts of 25bp in 2025) as global recession fears "
            "mount or Norwegian housing market stress accelerates. NIM drops 35–45bp within "
            "12 months. DNB's earnings guidance is cut twice in one year. The stock "
            "underperforms European banking peers, which are less exposed to NIM compression "
            "in a falling-rate environment."
        ),
        "base": (
            "Norges Bank delivers 2–3 cuts of 25bp in 2025–2026, bringing the policy rate to "
            "3.75–4.00%. This is broadly in line with market pricing. DNB's NIM compresses "
            "15–25bp but remains well above the 2015–2021 average (~1.2%). The easing cycle "
            "is also modestly supportive of mortgage lending volumes and fee income from "
            "property-related transactions."
        ),
    },
    "Regulatory & Capital": {
        "bull": (
            "Finanstilsynet reviews the systemic risk buffer and reduces the requirement by 0.5pp "
            "(consistent with Norges Bank's financial stability report findings). DNB's CET1 "
            "requirement drops from ~16.8% to ~16.3%, releasing approximately NOK 4–6B of "
            "excess capital. Management announces an accelerated buyback programme. "
            "Capital-light fee businesses (Carnegie, asset management) grow as a share of "
            "revenue, improving return on regulatory capital."
        ),
        "bear": (
            "The Basel IV final rules (fully implemented 2025) increase RWA density for mortgage "
            "portfolios. DNB's CET1 ratio falls 50–100bp post-implementation, requiring the "
            "bank to pause buybacks and potentially raise equity in a rights issue. "
            "Finanstilsynet raises the countercyclical capital buffer as Norwegian mortgage "
            "growth accelerates. Capital discipline limits shareholder returns for 2–3 years."
        ),
        "base": (
            "CET1 ratio remains comfortably above the regulatory minimum. Carnegie acquisition "
            "temporarily consumes ~40–80bp of CET1 but this is rebuilt within 18 months. "
            "Basel IV implementation has manageable impact on DNB's reported ratio (mortgage "
            "risk weights are relatively low in Norway given full-recourse structure). "
            "Buyback and dividend policy continues without material change."
        ),
    },
    "Markets & Investment Banking": {
        "bull": (
            "Nordic ECM recovers strongly: Norwegian energy transition IPOs (offshore wind, "
            "hydrogen, battery minerals), tech IPOs, and seafood company listings generate "
            "a pipeline not seen since 2021. DNB Carnegie captures 20–25% market share "
            "in Norwegian ECM (up from DNB Markets' 10–15% alone). M&A advisory fees "
            "are another growth driver as private equity activity resumes. DNB Carnegie's "
            "fixed income franchise benefits from a wave of green bond issuance."
        ),
        "bear": (
            "Nordic IPO market remains subdued as global risk appetite stays low (high rates, "
            "geopolitical uncertainty). M&A activity is limited by valuation gaps between "
            "buyers and sellers. DNB Carnegie's investment banking revenues disappoint in "
            "the first 1–2 years post-merger. The trading revenues that sustained Carnegie "
            "as a standalone are compressed by tighter market-making margins. Fee income "
            "fails to offset NIM compression, leading to overall earnings miss."
        ),
        "base": (
            "Gradual recovery in Nordic capital markets from the 2022–2023 trough. "
            "DNB Carnegie participates in 8–12 significant transactions per year "
            "(IPOs, bond issues, M&A mandates). Fee income grows 15–20% annually "
            "from a low 2023–2024 base. The investment banking business is subscale "
            "vs. European bulge brackets but holds a structurally advantaged position "
            "in Norwegian domestic capital markets."
        ),
    },
    "ESG & Sustainability": {
        "bull": (
            "DNB's early moves to establish green lending targets and exit coal financing "
            "attract ESG-focused institutional investors (pension funds, sovereign wealth). "
            "Green bond issuance for DNB itself becomes cheaper (green premium). "
            "DNB Carnegie leads the Norwegian green bond market, capturing structuring fees. "
            "Regulatory tailwinds (EU taxonomy, SFDR) force competitors to disclose "
            "fossil fuel exposure, favouring DNB's cleaner balance sheet narrative."
        ),
        "bear": (
            "Oil price rises sharply; political pressure to support domestic energy production "
            "increases. DNB's ambiguous stance on oil sector financing (still financing "
            "Norwegian shelf development) becomes a target for NGO campaigns. "
            "Greenwashing allegations emerge around some 'green' loan classifications. "
            "ESG-driven selling by international investors creates share price overhang."
        ),
        "base": (
            "DNB makes steady but unspectacular progress on sustainability targets. "
            "Green lending portfolio grows; fossil fuel exposure gradually reduces "
            "as North Sea oil investment naturally declines. ESG is a modest positive "
            "for the franchise with institutional investors but not a significant "
            "driver of short-term earnings."
        ),
    },
    "Leadership & Governance": {
        "bull": (
            "CEO Kjerstin Braathen's long tenure provides strategic continuity through the "
            "Carnegie integration — a major advantage when key banker retention is critical. "
            "A smooth Carnegie integration under stable leadership signals to the market "
            "that management can execute complex deals. Any new appointments (Carnegie CEO "
            "integration leadership) are drawn from the investment banking industry and "
            "signal cultural seriousness about the new business."
        ),
        "bear": (
            "Leadership turnover during a complex integration raises concerns. If the Carnegie "
            "CEO or key division heads depart post-merger, revenue attrition accelerates. "
            "Norwegian government (34% shareholder) intervenes in strategic decisions, "
            "potentially blocking capital returns or mandating below-market lending rates. "
            "Board composition concerns emerge around independence vs. government representation."
        ),
        "base": (
            "Leadership team is stable and experienced. The integration of Carnegie management "
            "into DNB's structure is the main test — expect some departures but core retention "
            "of the equity research and ECM teams that are most valuable. "
            "Government ownership (34%) is a feature of Norwegian banking; DNB management "
            "has historically managed this relationship constructively."
        ),
    },
    "Dividends & Capital Returns": {
        "bull": (
            "DNB raises the ordinary dividend payout ratio to 55–60% and announces a "
            "NOK 5–8B buyback programme for 2025–2026. Total shareholder yield exceeds "
            "8–10%. Dividend per share grows 10%+ following strong earnings. "
            "DNB is re-rated as one of Europe's most attractive income stocks, "
            "attracting yield-seeking institutional investors."
        ),
        "bear": (
            "Carnegie acquisition temporarily requires capital retention; buyback is paused. "
            "If earnings disappoint due to NIM compression or credit costs, the payout "
            "ratio is maintained (50%) but dividend per share grows slowly. "
            "Government pressure to restrict buybacks (as seen at other Nordic state-owned banks) "
            "limits total shareholder return. Dividend yield remains attractive in absolute "
            "terms but does not offer material upside surprise."
        ),
        "base": (
            "DNB maintains the 50% payout ratio, with ordinary dividend per share growing "
            "in line with EPS (3–5% annually). Buyback programme continues at a moderate "
            "pace (NOK 2–4B per year) subject to capital adequacy. Total shareholder yield "
            "of 6–8% (dividend + buyback) makes DNB a compelling income investment "
            "vs. Norwegian fixed income at 4–4.5%."
        ),
    },
}


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _fmt_fund(val, prefix: str = "", suffix: str = "", decimals: int = 1) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    if abs(v) >= 1e9:
        return f"{prefix}{v / 1e9:.{decimals}f}B{suffix}"
    if abs(v) >= 1e6:
        return f"{prefix}{v / 1e6:.{decimals}f}M{suffix}"
    return f"{prefix}{v:.{decimals}f}{suffix}"


def _fmt_pct(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{float(val):+.1f}%"


def _headline_date(item: dict) -> str:
    # After reset_index(), the former index is now a column called "versionCreated"
    for key in ("versionCreated", "date", "Date", "publishedAt", "index"):
        val = item.get(key)
        if val is None:
            continue
        if hasattr(val, "strftime"):
            return val.strftime("%Y-%m-%d")
        s = str(val)
        return s[:10]
    return ""


def _story_link(item: dict) -> str:
    """Return a Refinitiv workspace URL for the story, if we have a storyId."""
    sid = item.get("storyId") or item.get("story_id") or item.get("StoryId")
    if sid:
        return f"https://workspace.refinitiv.com/web/apps/news-monitor/?storyId={sid}"
    return ""


# ── Markdown generator ────────────────────────────────────────────────────────

def generate_markdown(
    price_stats: dict,
    fundamentals: dict,
    dnb_news: list[dict],
    carnegie_news: list[dict],
    analysis_date: str,
) -> str:
    all_news = dnb_news + carnegie_news
    seen: set[str] = set()
    unique_news: list[dict] = []
    for item in all_news:
        sid = (
            item.get("storyId")
            or item.get("story_id")
            or item.get("StoryId")
            or str(item.get("text", ""))[:80]
        )
        if sid not in seen:
            seen.add(sid)
            unique_news.append(item)

    categorised = categorise_news(unique_news)
    L: list[str] = []

    def line(s: str = "") -> None:
        L.append(s)

    # ── Header ────────────────────────────────────────────────────────────────
    line("# DNB ASA & DNB Carnegie — Investment Analysis")
    line()
    line(f"**Date:** {analysis_date}  ")
    line(f"**Data source:** LSEG Workspaces API (desktop)  ")
    line(f"**Ticker:** `DNB.OL` (Oslo Stock Exchange)  ")
    line(f"**Script:** `scripts/analyze_dnb.py`  ")
    line(f"**News window:** past {NEWS_DAYS_BACK} days | "
         f"**Price history:** {HISTORY_START} – {date.today().isoformat()}")
    line()
    line("---")
    line()

    # ── Executive Summary ─────────────────────────────────────────────────────
    line("## Executive Summary")
    line()
    line(
        "DNB ASA is Norway's largest financial institution and one of the Nordic region's most "
        "systemically important banks. With total assets exceeding NOK 4 trillion and a "
        "~34% Norwegian state shareholding, DNB occupies a unique position: commercially "
        "driven yet implicitly state-backed. The bank earns the majority of its revenue from "
        "net interest income on its dominant Norwegian mortgage and corporate lending book, "
        "supplemented by asset management fees, payment services, and — following the landmark "
        "acquisition of Carnegie Investment Bank's Norwegian franchise — investment banking."
    )
    line()
    line(
        "The **Carnegie acquisition** is the defining strategic event of DNB's recent history. "
        "It transforms DNB from a predominantly universal commercial bank into a full-service "
        "financial group with genuine Nordic investment banking capability. This report analyses "
        "DNB's current financial position, the Carnegie strategic rationale, and the implications "
        "of recent news across bull, base, and bear scenarios."
    )
    line()
    line("---")
    line()

    # ── 1. Corporate Profile ─────────────────────────────────────────────────
    line("## 1. DNB Group — Corporate Profile")
    line()
    line("| Item | Detail |")
    line("|------|--------|")
    line("| **Legal name** | DNB ASA |")
    line("| **Founded** | 1822 (Christiania Sparebank, predecessor) |")
    line("| **Headquarters** | Bjørvika, Oslo, Norway |")
    line("| **Exchange / Ticker** | Oslo Stock Exchange — `DNB.OL` |")
    line("| **Norwegian state ownership** | ~34.0% (via the Ministry of Trade and Industry) |")
    line("| **Employees (FTE)** | ~12,000 across Norway and international offices |")
    line("| **Key subsidiaries** | DNB Bank ASA, DNB Asset Management, DNB Livsforsikring, DNB Carnegie |")
    line()
    line("### 1.1 Core Business Segments")
    line()
    line(
        "**Personal Customers:** Norway's largest retail bank by mortgage market share (~30%). "
        "Products span mortgages, consumer credit, savings, investments, and insurance. "
        "Aggressively digital-first — DNB has reduced its branch network by >60% since 2010 "
        "while growing its digital customer base. Co-founder of **Vipps MobilePay** "
        "(11M+ users across Nordics), Norway's dominant mobile payment platform."
    )
    line()
    line(
        "**SME Banking:** Serves Norway's small-and-medium enterprise backbone. Deep relationships "
        "in the energy supply chain, maritime services, retail, and property sectors. "
        "SME banking generates both lending revenue and high-value cash management fees."
    )
    line()
    line(
        "**Large Corporates & International:** Serves Norwegian multinationals and international "
        "companies with Norwegian exposure. DNB is among the world's leading lenders to the "
        "oil & gas and shipping sectors, with offices in New York, London, Singapore, and Houston."
    )
    line()
    line(
        "**DNB Carnegie (Markets & Investment Banking):** Following the acquisition of Carnegie's "
        "Norwegian business, DNB's capital markets arm now spans fixed income trading, FX, "
        "equity research (150+ companies), ECM (IPOs, secondary offerings), M&A advisory, "
        "and Nordic bond markets. DNB Carnegie competes directly with Nordea Markets, "
        "Arctic Securities, Pareto Securities, and the Nordic desks of international banks."
    )
    line()
    line(
        "**DNB Asset Management:** One of the largest Nordic asset managers, with approximately "
        "NOK 700–800 billion AUM. Manages equity, fixed income, and multi-asset funds for "
        "institutional and retail clients. Also manages Norway's major occupational pension "
        "schemes through DNB Livsforsikring."
    )
    line()
    line("---")
    line()

    # ── 2. DNB Carnegie Background ───────────────────────────────────────────
    line("## 2. DNB Carnegie — Background & Strategic Rationale")
    line()
    line(
        "Carnegie Investment Bank was founded in Stockholm in 1803 and built one of the most "
        "respected Nordic investment banking franchises over two centuries. Carnegie's Norwegian "
        "operations were particularly strong in:"
    )
    line()
    line("- **Equity Research:** Top-ranked coverage of 150+ Norwegian and Nordic listed companies")
    line("- **ECM (Equity Capital Markets):** Consistent top-2 or top-3 Norwegian IPO book-runner")
    line("- **M&A Advisory:** Mid-to-large cap Nordic M&A, with strength in energy, shipping, and seafood")
    line("- **Norwegian Fixed Income:** Bond origination and distribution for corporate issuers")
    line("- **Private Banking / Wealth Management:** High-net-worth client services")
    line()
    line(
        "**Why did DNB buy Carnegie?** DNB Markets had long competed with Carnegie for Norwegian "
        "capital markets mandates. By acquiring Carnegie, DNB eliminates a key domestic rival "
        "and gains a platform with significantly stronger equity research, ECM, and advisory "
        "credentials than DNB Markets had built organically. The strategic logic mirrors similar "
        "bank-acquires-boutique transactions seen across Europe."
    )
    line()
    line("**Key integration challenges:**")
    line()
    line("1. **Culture:** Carnegie's partnership-style boutique culture vs. DNB's corporate bank culture")
    line("2. **Talent retention:** Investment bankers have high external mobility — compensation and "
         "autonomy must be preserved")
    line("3. **Client conflicts:** Some corporates used Carnegie precisely because it was *independent* "
         "of a large commercial bank; they may now prefer competitors")
    line("4. **Timing:** The acquisition occurs as Nordic capital markets are recovering from a multi-year "
         "drought — deal flow may lag integration costs")
    line()
    line("---")
    line()

    # ── 3. Stock Performance ─────────────────────────────────────────────────
    line("## 3. Stock Performance — `DNB.OL`")
    line()
    if price_stats:
        cp = price_stats.get("current_price")
        pd_ = price_stats.get("price_date", "N/A")
        h52 = price_stats.get("52w_high")
        l52 = price_stats.get("52w_low")
        ytd = price_stats.get("ytd_return_pct")
        one_yr = price_stats.get("1y_return_pct")
        vol = price_stats.get("annualised_vol_pct")
        mdd = price_stats.get("max_drawdown_pct")

        line("| Metric | Value |")
        line("|--------|-------|")
        line(f"| **Current Price** | {'NOK {:.2f} ({})'.format(cp, pd_) if cp else 'N/A'} |")
        line(f"| **52-Week High** | {'NOK {:.2f}'.format(h52) if h52 else 'N/A'} |")
        line(f"| **52-Week Low** | {'NOK {:.2f}'.format(l52) if l52 else 'N/A'} |")
        line(f"| **YTD Return** | {'{:+.1f}%'.format(ytd) if ytd is not None else 'N/A'} |")
        line(f"| **1-Year Return** | {'{:+.1f}%'.format(one_yr) if one_yr is not None else 'N/A'} |")
        line(f"| **Annualised Volatility** | {'{:.1f}%'.format(vol) if vol is not None else 'N/A'} |")
        line(f"| **Max Drawdown (since {HISTORY_START})** | "
             f"{'{:.1f}%'.format(mdd) if mdd is not None else 'N/A'} |")
    else:
        line("*Price data not available — LSEG Workspace connection required.*")
    line()
    line("---")
    line()

    # ── 4. Financial Highlights ──────────────────────────────────────────────
    line("## 4. Financial Highlights")
    line()
    if fundamentals:
        line("| Metric | Value |")
        line("|--------|-------|")
        line(f"| **Market Capitalisation** | {_fmt_fund(fundamentals.get('market_cap'), 'NOK ')} |")
        line(f"| **Total Assets** | {_fmt_fund(fundamentals.get('total_assets'), 'NOK ')} |")
        line(f"| **Net Income (TTM)** | {_fmt_fund(fundamentals.get('net_income'), 'NOK ')} |")
        line(f"| **EPS** | {_fmt_fund(fundamentals.get('eps'), 'NOK ', decimals=2)} |")
        line(f"| **P/E Ratio** | {_fmt_fund(fundamentals.get('pe'), suffix='x')} |")
        line(f"| **Price/Book** | {_fmt_fund(fundamentals.get('pb'), suffix='x')} |")
        line(f"| **Dividend Yield** | {_fmt_fund(fundamentals.get('div_yield'), suffix='%')} |")
        line(f"| **Return on Equity (ROE)** | {_fmt_fund(fundamentals.get('roe'), suffix='%')} |")
    else:
        line("*Fundamental data not available — LSEG Workspace connection required.*")
    line()
    line("### 4.1 Q1 2026 Results — DNB Group (NOK millions)")
    line()
    line("| Line Item | Q1 2026 | Q1 2025 | FY 2025 |")
    line("|-----------|---------|---------|---------|")
    line("| **Net Interest Income** | 15,299 | 16,410 | 64,731 |")
    line("| **Net Other Operating Income** | 6,494 | 5,503 | 25,918 |")
    line("| **Total Income** | 21,793 | 21,913 | 90,649 |")
    line("| **Operating Expenses** | (8,395) | (7,885) | (34,319) |")
    line("| **Pre-tax profit (before impairment)** | 13,353 | 14,006 | 56,173 |")
    line("| **Impairment** | (644) | (410) | (2,803) |")
    line("| **Pre-tax profit** | 12,711 | 13,614 | 53,398 |")
    line("| **Net Profit** | 9,860 | 10,849 | 43,586 |")
    line()
    line("*Source: DNB Group Q1 2026 quarterly report (unaudited), April 23 2026 via LSEG.*")
    line()
    line("### 4.2 Q2 2026 Results — Key Highlights")
    line()
    line(
        "DNB reported Q2 2026 earnings on July 15, 2026 — **beating consensus estimates:**"
    )
    line()
    line("| Metric | Q2 2026 Actual | Consensus Estimate | Beat/Miss |")
    line("|--------|---------------|-------------------|-----------|")
    line("| **EPS (USD ADR)** | $0.69 | $0.66 | **Beat +$0.03** |")
    line("| **Revenue** | $2.31 billion | $2.28 billion | **Beat +$30M** |")
    line("| **ROE** | 14.02% | ~14% | In-line |")
    line("| **Net Margin** | 21.34% | — | — |")
    line()
    line("*Source: Zacks/LSEG consensus data, July 15–16 2026.*")
    line()
    line("### 4.3 Key Earnings Trends")
    line()
    line(
        "**NII under pressure from rate trajectory:**  "
        "NII fell 7% YoY in Q1 2026 (NOK 15,299M vs NOK 16,410M) as Norges Bank began "
        "its easing cycle. However, fee income growth (+18% YoY) almost fully offset the "
        "NII decline, demonstrating the value of DNB's diversified revenue base."
    )
    line()
    line(
        "**Fee income acceleration — the Carnegie effect:**  "
        "Net other operating income grew from NOK 5,503M (Q1'25) to NOK 6,494M (Q1'26). "
        "This reflects growing contribution from DNB Carnegie (advisory and ECM fees) and "
        "strong asset management performance (DNBAM AUM benefiting from Nordic equity "
        "market strength)."
    )
    line()
    line(
        "**Costs rising on integration:**  "
        "Operating expenses increased 6.5% YoY (NOK 8,395M vs NOK 7,885M), reflecting "
        "Carnegie integration one-off costs and staff additions in the investment banking "
        "division. Management targets a cost-to-income ratio below 40%."
    )
    line()
    line(
        "**Impairment normalising:**  "
        "Credit losses of NOK 644M in Q1 2026 (vs NOK 410M in Q1 2025) represent a "
        "modest normalisation from historically low post-COVID levels but remain "
        "well within guidance of 0.1–0.2% of loans."
    )
    line()
    line(
        "**Capital returns — 6% dividend yield:**  "
        "DNB's trailing 12-month dividend of NOK 18.00/share implies a 6% yield at "
        "current prices (NOK ~304). Dividend has grown at a 12.9% compound annual "
        "rate over the past 4 years. A $1,000 investment in DNB 5 years ago is "
        "now worth ~$3,414 (capital gain + dividends), representing a 241% total return."
    )
    line()
    line("---")
    line()

    # ── 5. Recent News Analysis ──────────────────────────────────────────────
    line("## 5. Recent News Analysis")
    line()
    if unique_news:
        line(
            f"*Sourced from LSEG Workspaces — {len(unique_news)} unique headlines across "
            f"DNB and Carnegie queries (past {NEWS_DAYS_BACK} days).*"
        )
    else:
        line("*News data not available — LSEG Workspace connection required.*")
    line()

    if categorised:
        for idx, (theme, items) in enumerate(categorised.items(), start=1):
            line(f"### 5.{idx} {theme}")
            line()
            line("**Recent headlines:**")
            line()
            for item in items[:8]:
                text = (
                    item.get("text")
                    or item.get("headline")
                    or item.get("Text")
                    or "Headline unavailable"
                )
                dt = _headline_date(item)
                src = item.get("sourceCode") or item.get("source") or ""
                link = _story_link(item)
                if link:
                    line(f"- [{text}]({link}) — *{src}* ({dt})")
                else:
                    line(f"- {text} — *{src}* ({dt})")
            line()
            cases = _CASES.get(theme)
            if cases:
                line("**Scenario Analysis:**")
                line()
                line(f"> **Bull Case:** {cases['bull']}")
                line()
                line(f"> **Bear Case:** {cases['bear']}")
                line()
                line(f"> **Base Case (most likely):** {cases['base']}")
            else:
                line(
                    f"*{len(items)} headline(s) categorised here. "
                    "Monitor for announcements that materially affect DNB's financials or strategy.*"
                )
            line()
    else:
        # No live news — provide static scenario analysis for all themes
        line(
            "No live news retrieved. The following scenarios are based on publicly known "
            "strategic context and DNB's most recent investor communications."
        )
        line()
        for theme, cases in _CASES.items():
            line(f"### {theme}")
            line()
            line(f"> **Bull Case:** {cases['bull']}")
            line()
            line(f"> **Bear Case:** {cases['bear']}")
            line()
            line(f"> **Base Case:** {cases['base']}")
            line()

    line("---")
    line()

    # ── 6. How DNB Operates ──────────────────────────────────────────────────
    line("## 6. How DNB Operates — Business Model Details")
    line()
    line("### 6.1 The Norwegian Mortgage Machine")
    line()
    line(
        "With ~30% market share in Norwegian residential mortgages, DNB has a structurally "
        "dominant position in Norway's NOK 3.5 trillion mortgage market. Key features:"
    )
    line()
    line(
        "- **Full-recourse mortgages:** Borrowers remain liable for the full debt even in "
        "default. This eliminates the 'jingle mail' risk common in US markets and keeps "
        "Norwegian NPL rates among the world's lowest.\n"
        "- **Variable-rate dominance:** ~80% of Norwegian mortgages are variable rate. "
        "NIM expands when rates rise (as post-2022) and contracts when they fall.\n"
        "- **LTV regulation:** Finanstilsynet caps mortgages at 85% LTV for most borrowers, "
        "providing significant collateral buffers even in a moderate housing downturn.\n"
        "- **Digital mortgage processing:** DNB processes most mortgage applications fully "
        "digitally, with automated valuation models and straight-through processing."
    )
    line()
    line("### 6.2 Sector Banking — DNB's Specialisation Edge")
    line()
    line(
        "DNB's competitive advantage in Large Corporates comes from deep sector expertise "
        "accumulated over decades:"
    )
    line()
    line(
        "| Sector | DNB's Position | Key Risk |")
    line(
        "|--------|---------------|----------|")
    line(
        "| **Oil & Gas** | Top 3 global E&P lender; reserve-based lending | Oil price; ESG transition |")
    line(
        "| **Shipping** | Top 5 global shipping bank; tanker, dry bulk, LNG | Freight rate cycles |")
    line(
        "| **Seafood/Aquaculture** | Norway's largest aquaculture lender | Disease; regulation; China |")
    line(
        "| **Offshore / Subsea** | Leading lender to Norwegian continental shelf services | Oil capex cycle |")
    line(
        "| **Renewables** | Growing green energy lending; offshore wind focus | Project risk; permitting |")
    line()
    line("### 6.3 Digital Strategy and Vipps MobilePay")
    line()
    line(
        "DNB co-founded Vipps in 2015 as a simple P2P payment app. It now handles "
        "virtually all Norwegian retail payments (person-to-person, merchant, BankID logins, "
        "subscription management). In 2022, Vipps merged with Danish MobilePay to form "
        "**Vipps MobilePay**, the dominant digital payment platform across Denmark, "
        "Finland, and Norway with 11+ million users."
    )
    line()
    line(
        "DNB holds a significant stake in Vipps MobilePay AS. A future IPO or strategic "
        "sale of this company at a platform premium could represent a material one-off "
        "gain for DNB shareholders — a value 'option' not currently priced into most models."
    )
    line()
    line("### 6.4 Asset Management — Recurring Fee Income")
    line()
    line(
        "DNB Asset Management (DNBAM) manages approximately NOK 700–800B in assets, "
        "covering equity funds, fixed income, multi-asset, real estate, and alternatives. "
        "DNBAM earns a blended management fee of ~0.4–0.6% of AUM, generating "
        "NOK 3–4B in annual fee income that is largely independent of the lending cycle."
    )
    line()
    line(
        "DNBAM is a structural beneficiary of Norway's mandatory occupational pension saving "
        "scheme, which channels large, regular contributions into long-duration investment mandates."
    )
    line()
    line("---")
    line()

    # ── 7. Risk Factors ──────────────────────────────────────────────────────
    line("## 7. Key Risk Factors")
    line()
    line("| Risk | Impact | Probability | Notes |")
    line("|------|--------|------------|-------|")
    line("| **NIM compression (rate cuts)** | High | Medium | Each Norges Bank 25bp cut ≈ NOK 500–700M NII loss |")
    line("| **Norwegian housing market** | High | Low-Medium | Household debt-to-income ~250%; 15% price fall raises NPLs |")
    line("| **Carnegie integration failure** | Medium-High | Low-Medium | Key banker attrition; cultural mismatch |")
    line("| **Commercial real estate stress** | Medium | Medium | Norwegian + Swedish CRE repricing at higher rates |")
    line("| **Regulatory capital increase** | Medium | Low-Medium | Basel IV + systemic buffers may constrain buybacks |")
    line("| **Cyber/operational** | Medium | Ongoing | Norway's largest bank = prime target |")
    line("| **ESG / fossil fuel transition** | Low-Medium | Long-term | Reputational and regulatory pressure on oil lending |")
    line("| **Geopolitical (Baltic/Arctic)** | Low-Medium | Tail | Russian activity in Norwegian maritime zones |")
    line("| **Concentration risk** | Low | Ongoing | Heavily exposed to Norwegian economy |")
    line()
    line("---")
    line()

    # ── 8. Management Statements ─────────────────────────────────────────────
    line("## 8. Management Strategy & Targets")
    line()
    line(
        "DNB's senior leadership — CEO **Kjerstin Braathen** (since 2019) and CFO **Ida Lerner** — "
        "has communicated the following strategic priorities and financial targets:"
    )
    line()
    line("| Target | Guidance |")
    line("|--------|----------|")
    line("| **Return on Equity (ROE)** | >13% through the cycle (achieved 15–17% in 2023–2024) |")
    line("| **Cost/Income Ratio** | <40% (digital efficiency programme) |")
    line("| **CET1 Ratio** | ~18% target (above regulatory minimum of ~16.8%) |")
    line("| **Dividend payout** | 50% of net profit (ordinary); supplementary buybacks when CET1 > target |")
    line("| **Carnegie synergies** | NOK 200–400M annual synergies by year 3; NOK 300–500M one-off costs |")
    line("| **ESG / sustainability** | Net-zero lending portfolio by 2050; increase green energy financing |")
    line("| **Digital** | Maintain digital leadership; Vipps MobilePay as ecosystem anchor |")
    line()
    line("---")
    line()

    # ── 9. Conclusion ────────────────────────────────────────────────────────
    line("## 9. Conclusion")
    line()
    line(
        "DNB ASA occupies a structurally privileged position in Norwegian banking: "
        "market-leading mortgage franchise, deep sector expertise in high-margin industries, "
        "low-cost digital infrastructure, and an implicit government backstop. The Carnegie "
        "acquisition adds an investment banking dimension that — if well-executed — creates "
        "a more complete Nordic financial powerhouse."
    )
    line()
    line("**Key conclusions by scenario:**")
    line()
    line(
        "| Scenario | Key Driver | Likely Outcome |")
    line(
        "|----------|------------|---------------|")
    line(
        "| **Bull** | Rates stay high; Carnegie synergies beat plan; Vipps IPO | "
        "Stock re-rates to 1.5× book; total return 15–20%+ |")
    line(
        "| **Base** | 2–3 rate cuts; Carnegie integration on track; steady credit | "
        "Dividend yield + modest appreciation; 8–12% total return |")
    line(
        "| **Bear** | Rapid rate cuts; integration disappointment; Norwegian housing stress | "
        "Stock de-rates to 1.0× book; dividend maintained but buybacks paused; flat returns |")
    line()
    line(
        "For long-term investors, DNB offers a reliable dividend stream (5–7% yield), "
        "moderate earnings growth, and a strategic optionality in DNB Carnegie and "
        "Vipps MobilePay that is not fully priced by the market. "
        "The main near-term risk is the NIM compression from the Norges Bank easing cycle "
        "— but even in a 150bp cutting scenario, DNB's NIM would remain well above "
        "its 2015–2021 average."
    )
    line()
    line("---")
    line()
    line(
        f"*Analysis generated: {analysis_date}. Data: LSEG Workspaces API.  "
        f"Script: `scripts/analyze_dnb.py`.  "
        f"News window: past {NEWS_DAYS_BACK} days.*"
    )
    line()
    line(
        "*Disclaimer: This document is produced within the portfolio-sim educational project. "
        "It does not constitute investment advice. All data and scenario analyses are "
        "for research and learning purposes only.*"
    )

    return "\n".join(L)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 65)
    print(" DNB ASA & DNB Carnegie — Analysis via LSEG Workspaces API")
    print("=" * 65)

    connected = open_connection()
    if not connected:
        print("\n[INFO] Generating analysis with static research content only.")
        print("       Run with LSEG Workspace open for live price and news data.\n")

    try:
        print(f"\n[1/4] Fetching {DNB_RIC} daily price history ({HISTORY_START} – today)...")
        price_df = fetch_price_history() if connected else pd.DataFrame()
        price_stats = compute_price_stats(price_df)
        if price_stats.get("current_price"):
            print(f"      DNB price: NOK {price_stats['current_price']:.2f} ({price_stats['price_date']})")
            print(f"      YTD: {price_stats.get('ytd_return_pct', 0):+.1f}% | "
                  f"1Y: {price_stats.get('1y_return_pct', 0):+.1f}% | "
                  f"Vol: {price_stats.get('annualised_vol_pct', 0):.1f}%")
        else:
            print("      No price data returned.")

        print("\n[2/4] Fetching financial fundamentals...")
        fundamentals = fetch_fundamentals() if connected else {}
        if fundamentals:
            print(f"      ROE: {fundamentals.get('roe', 'N/A')} | "
                  f"PE: {fundamentals.get('pe', 'N/A'):.2f}x | "
                  f"DivYield: {fundamentals.get('div_yield', 'N/A'):.1f}%")
        else:
            print("      No fundamentals returned.")

        print(f"\n[3/4] Fetching DNB news (past {NEWS_DAYS_BACK} days)...")
        dnb_news = (
            fetch_news("DNB.OL", count=NEWS_COUNT)
            if connected
            else []
        )
        print(f"      {len(dnb_news)} DNB headlines found.")

        print("\n[4/4] Fetching Carnegie / Luminor / Analyst / Earnings news...")
        carnegie_news: list[dict] = []
        if connected:
            for q, count in [
                ("Luminor OTP DNB bank", 20),
                ("DNB Carnegie investment bank", 20),
                ("DNB bank quarterly earnings results", 25),
                ("DNB target price analyst upgrade downgrade rating", 20),
            ]:
                items = fetch_news(q, count=count)
                carnegie_news.extend(items)
        print(f"      {len(carnegie_news)} supplementary headlines found.")

        analysis_date = date.today().strftime("%B %d, %Y")
        print("\nGenerating markdown report...")
        md = generate_markdown(
            price_stats=price_stats,
            fundamentals=fundamentals,
            dnb_news=dnb_news,
            carnegie_news=carnegie_news,
            analysis_date=analysis_date,
        )

        out_path = OUT_DIR / "dnb_analysis.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"\n[DONE] Report written to: {out_path}")
        print(f"       Total headlines: {len(dnb_news) + len(carnegie_news)}")
        print(f"       Price data: {'OK' if price_stats else 'N/A'}")
        print(f"       Fundamentals: {'OK' if fundamentals else 'N/A'}")

    finally:
        close_connection()


if __name__ == "__main__":
    main()
