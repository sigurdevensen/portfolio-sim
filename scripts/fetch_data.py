"""CLI script to download and cache market data."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loader import fetch_prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Download adjusted-close prices from yfinance.")
    parser.add_argument("--tickers", nargs="+", required=True, help="Ticker symbols")
    parser.add_argument("--start", default="2015-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--no-cache", action="store_true", help="Skip local cache")
    args = parser.parse_args()

    print(f"Fetching {args.tickers} from {args.start} to {args.end or 'today'}...")
    prices = fetch_prices(args.tickers, args.start, args.end or "2099-01-01", use_cache=not args.no_cache)
    print(prices.tail())
    print(f"\nShape: {prices.shape}")


if __name__ == "__main__":
    main()
