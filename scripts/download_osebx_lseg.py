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
# eikon.get_timeseries uses these short names; lseg-data omits fields entirely
# so the API returns its default price columns for the instrument type.
EIKON_FIELDS = ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
# OSEBX history starts around 1996-01-02
HISTORY_START = "1996-01-01"
OUT_PATH = Path(__file__).parent.parent / "data" / "raw" / "osebx_monthly.csv"


def _fetch_lseg_data() -> pd.DataFrame:
    """Fetch via the modern lseg-data library (recommended).

    No explicit fields are passed — the API returns its default columns for
    the instrument type (typically TRDPRC_1, HIGH_1, LOW_1, OPEN_PRC, ACVOL_UNS
    for index RICs). They are renamed to Open/High/Low/Close/Volume afterwards.
    """
    import lseg.data as ld

    ld.open_session()
    try:
        df = ld.get_history(
            universe=RIC,
            interval="monthly",
            start=HISTORY_START,
            end=date.today().isoformat(),
        )
    finally:
        ld.close_session()

    if df is None or df.empty:
        return pd.DataFrame()

    # Normalise whatever column names the API returned
    df = _normalise_columns(df)
    return df


# Maps known LSEG/RDP field names to our standard output names
_COLUMN_MAP = {
    "TRDPRC_1": "Close",
    "HIGH_1": "High",
    "LOW_1": "Low",
    "OPEN_PRC": "Open",
    "ACVOL_UNS": "Volume",
    # already-capitalised fallbacks
    "OPEN": "Open",
    "HIGH": "High",
    "LOW": "Low",
    "CLOSE": "Close",
    "VOLUME": "Volume",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=_COLUMN_MAP)
    # Keep only recognised columns; drop anything else (e.g. metadata fields)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]




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

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH)

    start_str = df.index[0].strftime("%Y-%m-%d")
    end_str = df.index[-1].strftime("%Y-%m-%d")
    print(f"Saved {len(df)} rows ({start_str} to {end_str}) to {OUT_PATH}")


if __name__ == "__main__":
    main()
