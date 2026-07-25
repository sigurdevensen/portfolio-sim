"""CLI script to run risk analysis on a set of tickers."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loader import fetch_prices
from risk import value_at_risk, conditional_var, max_drawdown, correlation_heatmap_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run risk analysis on a set of tickers.")
    parser.add_argument("--tickers", nargs="+", default=["SPY", "QQQ", "GLD"])
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--confidence", type=float, default=0.95)
    args = parser.parse_args()

    prices = fetch_prices(args.tickers, args.start, args.end)
    returns = prices.pct_change().dropna()

    print(f"\n--- Risk Analysis: {args.tickers} ({args.start} → {args.end}) ---\n")
    for ticker in args.tickers:
        r = returns[ticker]
        var = value_at_risk(r, confidence=args.confidence)
        cvar = conditional_var(r, confidence=args.confidence)
        mdd = max_drawdown(prices[ticker])
        print(f"  {ticker}")
        print(f"    VaR  ({args.confidence:.0%}): {var:.4f}")
        print(f"    CVaR ({args.confidence:.0%}): {cvar:.4f}")
        print(f"    Max Drawdown:         {mdd:.2%}")

    print("\n--- Correlation Matrix ---")
    print(correlation_heatmap_data(returns).round(3).to_string())


if __name__ == "__main__":
    main()
