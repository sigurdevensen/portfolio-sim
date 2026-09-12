"""Fetch VLCC tanker rates and Frontline (FRO) stock from LSEG and plot them.

VLCC rate proxy: Baltic Dirty Tanker Index (.BAID) — the primary LSEG/Baltic
                 Exchange benchmark for dirty tanker freight rates (VLCC,
                 Suezmax, Aframax). VLCC makes up the largest weighting.
Stock:           FRO (Frontline Ltd, NYSE listing).

Requires LSEG Workspace to be running and signed in.
    pip install lseg-data
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

# ---- Configuration -----------------------------------------------------------

# .BAID = Baltic Dirty Tanker Index (daily, LSEG confirmed)
# TD-CRP1-VIZ = Vizor crude tanker route (US->India, daily) — secondary option
VLCC_CANDIDATES = [
    (".BAID",        "TRDPRC_1",  "Baltic Dirty Tanker Index (BDTI)"),
    ("TD-CRP1-VIZ",  "TCE_RATE",  "VLCC TCE Rate (USD/day, Vizor)"),
    (".VLCC",        "TRDPRC_1",  "DBL Hull VLCC 5yr Value/day"),
]

FRO_CANDIDATES = [
    ("FRO",    "TRDPRC_1"),   # NYSE
    ("FRO.OL", "OFF_CLOSE"),  # Oslo
]

HISTORY_START = "2020-01-01"
HISTORY_END   = date.today().isoformat()

# ---- LSEG connection ---------------------------------------------------------

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
        "        Make sure LSEG Workspace is running and signed in."
    )
    return False


def close_connection() -> None:
    if _api_type == "lseg":
        try:
            _ld.close_session()
        except Exception:
            pass


# ---- Data fetching -----------------------------------------------------------

def _get_history(ric: str) -> pd.DataFrame:
    try:
        if _api_type == "lseg":
            df = _ld.get_history(
                universe=ric,
                interval="daily",
                start=HISTORY_START,
                end=HISTORY_END,
            )
        else:
            df = _ld.get_timeseries(
                rics=ric,
                fields=["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
                start_date=HISTORY_START,
                end_date=HISTORY_END,
            )
        return df if (df is not None and not df.empty) else pd.DataFrame()
    except Exception as exc:
        print(f"      [{ric}] {exc}")
        return pd.DataFrame()


def fetch_tanker_rate() -> tuple[pd.Series, str]:
    for ric, col, label in VLCC_CANDIDATES:
        print(f"  Trying {ric!r} (column '{col}') ...")
        df = _get_history(ric)
        if df.empty:
            continue
        if col not in df.columns:
            # Fall back to any numeric column
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                col = num_cols[0]
            else:
                continue
        s = df[col].dropna()
        if s.empty:
            continue
        print(f"  -> {ric!r}: {len(s)} points, "
              f"{s.index[0].date()} to {s.index[-1].date()}, "
              f"latest = {s.iloc[-1]:.2f}")
        return s, label
    return pd.Series(dtype=float), "Tanker Rate"


def fetch_fro() -> pd.Series:
    for ric, col in FRO_CANDIDATES:
        print(f"  Trying {ric!r} (column '{col}') ...")
        df = _get_history(ric)
        if df.empty:
            continue
        if col not in df.columns:
            num_cols = df.select_dtypes(include="number").columns.tolist()
            col = num_cols[0] if num_cols else None
            if col is None:
                continue
        s = df[col].dropna()
        if s.empty:
            continue
        print(f"  -> {ric!r}: {len(s)} points, "
              f"{s.index[0].date()} to {s.index[-1].date()}, "
              f"latest = {s.iloc[-1]:.2f}")
        return s
    return pd.Series(dtype=float)


# ---- Plotting ----------------------------------------------------------------

def plot(tanker: pd.Series, tanker_label: str, fro: pd.Series) -> Path:
    # Align on common dates
    tanker.index = pd.to_datetime(tanker.index).normalize()
    fro.index    = pd.to_datetime(fro.index).normalize()
    common = tanker.index.intersection(fro.index)

    if len(common) < 10:
        raise ValueError(
            f"Only {len(common)} overlapping dates — cannot plot."
        )

    t_aligned = tanker.reindex(common).astype(float)
    f_aligned = fro.reindex(common).astype(float)

    # Stats
    price_corr  = t_aligned.corr(f_aligned)
    return_corr = t_aligned.pct_change().corr(f_aligned.pct_change())

    # ---- Figure ----------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(14, 7))
    BG = "#0f0f0f"
    fig.patch.set_facecolor(BG)
    ax1.set_facecolor(BG)

    TANKER_COL = "#f97316"   # orange
    FRO_COL    = "#38bdf8"   # sky blue
    FILL_ALPHA = 0.08

    # Left axis: tanker rate
    ax1.plot(t_aligned.index, t_aligned.values,
             color=TANKER_COL, linewidth=1.5, label=tanker_label, alpha=0.95, zorder=3)
    ax1.fill_between(t_aligned.index, t_aligned.values,
                     t_aligned.min(), color=TANKER_COL, alpha=FILL_ALPHA)
    ax1.set_ylabel(tanker_label, color=TANKER_COL, fontsize=11, labelpad=8)
    ax1.tick_params(axis="y", labelcolor=TANKER_COL, colors=TANKER_COL)
    ax1.tick_params(axis="x", colors="#94a3b8")
    ax1.yaxis.label.set_color(TANKER_COL)
    for spine in ax1.spines.values():
        spine.set_edgecolor("#1e2936")
    ax1.grid(True, color="#1e2936", linestyle="--", linewidth=0.5, alpha=0.8)
    ax1.set_xlim(common[0], common[-1])

    # Right axis: FRO stock
    ax2 = ax1.twinx()
    ax2.set_facecolor(BG)
    ax2.plot(f_aligned.index, f_aligned.values,
             color=FRO_COL, linewidth=1.5, label="Frontline (FRO) — USD", alpha=0.95, zorder=3)
    ax2.fill_between(f_aligned.index, f_aligned.values,
                     f_aligned.min(), color=FRO_COL, alpha=FILL_ALPHA)
    ax2.set_ylabel("Frontline FRO (USD)", color=FRO_COL, fontsize=11, labelpad=8)
    ax2.tick_params(axis="y", labelcolor=FRO_COL, colors=FRO_COL)
    for spine in ax2.spines.values():
        spine.set_edgecolor("#1e2936")

    # X-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate(rotation=35, ha="right")

    # Title & subtitle
    fig.suptitle(
        "VLCC Tanker Rates vs Frontline (FRO) Stock",
        color="white", fontsize=15, fontweight="bold", y=0.97,
    )
    ax1.set_title(
        f"{HISTORY_START} to {HISTORY_END}  |  "
        f"Price corr: {price_corr:+.2f}  |  "
        f"Daily-return corr: {return_corr:+.2f}  |  "
        f"Source: LSEG Workspace",
        color="#94a3b8", fontsize=9, pad=6,
    )

    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2, labels1 + labels2,
        loc="upper left", facecolor="#1a2030", edgecolor="#2d3748",
        labelcolor="white", fontsize=9,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.94])

    out_path = OUT_DIR / "vlcc_vs_fro.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.show()
    return out_path


# ---- Main --------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print(" VLCC Tanker Rates vs Frontline (FRO) — LSEG")
    print("=" * 60)

    if not open_connection():
        sys.exit(1)

    try:
        print(f"\n[1/2] Fetching tanker rate ({HISTORY_START} to {HISTORY_END})")
        tanker, tanker_label = fetch_tanker_rate()
        if tanker.empty:
            print("[ERROR] No tanker rate data retrieved.")
            sys.exit(1)

        print(f"\n[2/2] Fetching Frontline FRO ({HISTORY_START} to {HISTORY_END})")
        fro = fetch_fro()
        if fro.empty:
            print("[ERROR] No FRO stock data retrieved.")
            sys.exit(1)

        print("\nGenerating chart ...")
        out_path = plot(tanker, tanker_label, fro)
        print(f"\n[DONE] Chart saved: {out_path}")

    finally:
        close_connection()


if __name__ == "__main__":
    main()
