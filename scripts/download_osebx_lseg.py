"""Download OSEBX daily prices via LSEG Workspace desktop API.

Requires LSEG Workspace (or Eikon) to be running on the desktop.

Install the library:
    pip install lseg-data

The eikon library also works if you have that installed instead:
    pip install eikon

OSEBX RIC: .OSEBX
LSEG get_history() returns data in chunks internally, but the older eikon
get_timeseries() is capped at ~3 000 rows per call, so this script loops
over yearly chunks when falling back to that API.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

RIC = ".OSEBX"
FIELDS = ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
# OSEBX history starts around 1996-01-02
HISTORY_START = "1996-01-01"
OUT_PATH = Path(__file__).parent.parent / "data" / "raw" / "osebx_daily.csv"


def _fetch_lseg_data() -> pd.DataFrame:
    """Fetch via the modern lseg-data library (recommended)."""
    import lseg.data as ld

    ld.open_session()
    try:
        df = ld.get_history(
            universe=RIC,
            fields=FIELDS,
            interval="daily",
            start=HISTORY_START,
            end=date.today().isoformat(),
        )
    finally:
        ld.close_session()

    return df


def _fetch_eikon(chunk_years: int = 5) -> pd.DataFrame:
    """Fetch via the legacy eikon library, chunked to stay under the row limit."""
    import eikon as ek

    # App key is read from the Eikon desktop session automatically when
    # Workspace is running; no explicit set_app_key() call needed in most setups.
    # If you do need one: ek.set_app_key("YOUR_APP_KEY_HERE")

    chunks: list[pd.DataFrame] = []
    start = pd.Timestamp(HISTORY_START)
    end = pd.Timestamp(date.today())

    current = start
    while current < end:
        chunk_end = min(current + pd.DateOffset(years=chunk_years), end)
        print(f"  Fetching {current.date()} → {chunk_end.date()}...")
        chunk = ek.get_timeseries(
            RIC,
            fields=FIELDS,
            start_date=current.strftime("%Y-%m-%d"),
            end_date=chunk_end.strftime("%Y-%m-%d"),
            interval="daily",
        )
        if chunk is not None and not chunk.empty:
            chunks.append(chunk)
        current = chunk_end + pd.DateOffset(days=1)

    if not chunks:
        return pd.DataFrame()

    df = pd.concat(chunks)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def main() -> None:
    print(f"Downloading {RIC} daily prices (max history from {HISTORY_START})...")

    df: pd.DataFrame | None = None

    # Try the modern lseg-data library first
    try:
        import lseg.data  # noqa: F401
        print("Using lseg-data library...")
        df = _fetch_lseg_data()
    except ImportError:
        pass

    # Fall back to the legacy eikon library
    if df is None:
        try:
            import eikon  # noqa: F401
            print("Using eikon library (chunked fetch)...")
            df = _fetch_eikon()
        except ImportError:
            print(
                "Neither 'lseg-data' nor 'eikon' is installed.\n"
                "Install one of them:\n"
                "    pip install lseg-data\n"
                "    pip install eikon\n"
                "Then ensure LSEG Workspace is running on your desktop."
            )
            sys.exit(1)

    if df is None or df.empty:
        print("No data returned. Make sure LSEG Workspace is open and you are signed in.")
        sys.exit(1)

    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"
    df.columns = [c.capitalize() for c in df.columns]  # Open, High, Low, Close, Volume

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH)

    start_str = df.index[0].strftime("%Y-%m-%d")
    end_str = df.index[-1].strftime("%Y-%m-%d")
    print(f"Saved {len(df)} rows ({start_str} → {end_str}) to {OUT_PATH}")


if __name__ == "__main__":
    main()
