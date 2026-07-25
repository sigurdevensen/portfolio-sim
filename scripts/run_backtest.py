"""CLI script to run a strategy backtest and print a summary."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtesting.engine import BacktestConfig, BacktestEngine
from data.loader import fetch_prices
from strategies import BuyAndHold, EqualWeight, Momentum, MeanReversion

STRATEGY_MAP = {
    "buy_and_hold": BuyAndHold,
    "equal_weight": EqualWeight,
    "momentum": Momentum,
    "mean_reversion": MeanReversion,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a portfolio backtest.")
    parser.add_argument("--strategy", choices=list(STRATEGY_MAP), default="buy_and_hold")
    parser.add_argument("--tickers", nargs="+", default=["SPY", "QQQ", "GLD", "TLT"])
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    print(f"Strategy: {args.strategy} | Tickers: {args.tickers} | {args.start} → {args.end}")
    prices = fetch_prices(args.tickers, args.start, args.end)
    strategy = STRATEGY_MAP[args.strategy]()
    config = BacktestConfig(start=args.start, end=args.end, initial_capital=args.capital)
    engine = BacktestEngine(config)
    result = engine.run(strategy, prices)

    print("\n--- Metrics ---")
    for k, v in result.metrics.items():
        print(f"  {k}: {v:.4f}")


if __name__ == "__main__":
    main()
