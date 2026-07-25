"""Download OSEBX (Oslo Stock Exchange Benchmark Index) daily prices to CSV.

Fetches the maximum available history from yfinance (^OSEBX) and writes
OHLCV + adjusted-close data to data/raw/osebx_daily.csv.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf

TICKER = "^OSEBX"
OUT_PATH = Path(__file__).parent.parent / "data" / "raw" / "osebx_daily.csv"


def main() -> None:
    print(f"Downloading {TICKER} (max history)...")

    ticker = yf.Ticker(TICKER)
    df = ticker.history(period="max", interval="1d", auto_adjust=True)

    if df.empty:
        print("No data returned. Check ticker symbol or network connection.")
        sys.exit(1)

    # Drop intraday columns added by yfinance that don't apply to daily data
    df = df.drop(columns=["Dividends", "Stock Splits"], errors="ignore")
    df.index = df.index.tz_localize(None)  # strip timezone for plain CSV readability
    df.index.name = "Date"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH)

    start = df.index[0].strftime("%Y-%m-%d")
    end = df.index[-1].strftime("%Y-%m-%d")
    print(f"Saved {len(df)} rows ({start} → {end}) to {OUT_PATH}")


if __name__ == "__main__":
    main()
