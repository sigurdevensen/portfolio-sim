"""Market data loading and caching."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def fetch_prices(
    tickers: list[str],
    start: str,
    end: str,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Download adjusted-close prices, optionally reading from a local cache.

    Args:
        tickers: List of ticker symbols.
        start: Start date string (YYYY-MM-DD).
        end: End date string (YYYY-MM-DD).
        use_cache: If True, read/write parquet cache files in data/cache/.

    Returns:
        DataFrame with DatetimeIndex (UTC) and one column per ticker.
    """
    cache_key = "_".join(sorted(tickers)) + f"_{start}_{end}"
    cache_path = CACHE_DIR / f"{cache_key}.parquet"

    if use_cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if len(tickers) == 1:
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        prices = raw["Close"]

    prices.index = pd.to_datetime(prices.index, utc=True)

    if use_cache:
        prices.to_parquet(cache_path)

    return prices


def load_csv(path: str | Path, ticker: str | None = None) -> pd.DataFrame:
    """Load prices from a CSV file in data/raw/.

    Expects columns: Date, Close (or Open, High, Low, Close, Volume).
    """
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    df.index = pd.to_datetime(df.index, utc=True)
    if "Adj Close" in df.columns:
        df = df[["Adj Close"]].rename(columns={"Adj Close": ticker or Path(path).stem})
    elif "Close" in df.columns:
        df = df[["Close"]].rename(columns={"Close": ticker or Path(path).stem})
    return df
