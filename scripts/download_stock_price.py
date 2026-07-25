"""Download daily (or monthly) price history for any RIC via LSEG Workspace.

Requires LSEG Workspace to be running on the desktop.

Install the library:
    pip install lseg-data

Usage examples:
    python scripts/download_stock_price.py EQNR.OL
    python scripts/download_stock_price.py AAPL.O --start 2010-01-01 --interval monthly
    python scripts/download_stock_price.py DNB.OL --start 2015-01-01 --end 2024-12-31
    python scripts/download_stock_price.py .OSEBX --out data/raw/osebx_daily.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# Maps known LSEG/RDP field names to standard output names
_COLUMN_MAP = {
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

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=_COLUMN_MAP)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]


def _fetch_lseg(ric: str, start: str, end: str, interval: str) -> pd.DataFrame:
    import lseg.data as ld

    ld.open_session()
    try:
        df = ld.get_history(universe=ric, interval=interval, start=start, end=end)
    finally:
        ld.close_session()

    if df is None or df.empty:
        return pd.DataFrame()
    return _normalise_columns(df)


def _safe_filename(ric: str) -> str:
    return ric.replace(".", "_").replace("/", "_").replace("\\", "_")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download price history for any RIC ticker.")
    parser.add_argument("ticker", help="LSEG RIC, e.g. EQNR.OL, AAPL.O, .OSEBX")
    parser.add_argument("--start", default="2000-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=date.today().isoformat(), help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--interval",
        default="daily",
        choices=["daily", "weekly", "monthly", "quarterly", "yearly"],
        help="Price interval (default: daily)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path (default: data/raw/<ticker>_<interval>.csv)",
    )
    args = parser.parse_args()

    out_path = (
        Path(args.out)
        if args.out
        else Path(__file__).parent.parent
        / "data"
        / "raw"
        / f"{_safe_filename(args.ticker)}_{args.interval}.csv"
    )

    print(f"Downloading {args.ticker} {args.interval} prices ({args.start} to {args.end})...")

    try:
        import lseg.data  # noqa: F401
    except ImportError:
        print("lseg-data is not installed. Run: pip install lseg-data")
        sys.exit(1)

    df = _fetch_lseg(args.ticker, args.start, args.end, args.interval)

    if df is None or df.empty:
        print("No data returned. Make sure LSEG Workspace is open and you are signed in.")
        sys.exit(1)

    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path)

    print(
        f"Saved {len(df)} rows "
        f"({df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}) "
        f"to {out_path}"
    )


if __name__ == "__main__":
    main()
