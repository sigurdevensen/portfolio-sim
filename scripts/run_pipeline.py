"""CLI entry point: run a strategy backtest end-to-end via Pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.pipeline import Pipeline
from strategies import BuyAndHold, EqualWeight, Momentum, MeanReversion

_STRATEGIES = {
    "buy_and_hold": lambda: BuyAndHold(),
    "equal_weight": lambda: EqualWeight(),
    "momentum": lambda: Momentum(),
    "mean_reversion": lambda: MeanReversion(),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a trading strategy backtest.")
    parser.add_argument("--strategy", choices=list(_STRATEGIES), default="buy_and_hold")
    parser.add_argument("--tickers", nargs="+", required=True, help="Ticker symbols, e.g. AAPL MSFT")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--data-source", choices=["yfinance", "lseg"], default="yfinance")
    parser.add_argument("--output", default="reports/", help="Directory for report output")
    args = parser.parse_args()

    strategy = _STRATEGIES[args.strategy]()

    print(f"Running {args.strategy} on {args.tickers} ({args.start} -> {args.end}) ...")

    p = (
        Pipeline(
            strategy=strategy,
            tickers=args.tickers,
            start=args.start,
            end=args.end,
            data_source=args.data_source,
            initial_capital=args.capital,
            commission=args.commission,
            slippage_bps=args.slippage_bps,
        )
        .run()
        .evaluate()
        .report(output=args.output)
    )

    m = p.get_report().metrics
    print("\n-- Results -------------------------------------------")
    print(f"  Total Return:  {m.get('total_return', 0):.2%}")
    print(f"  CAGR:          {m.get('cagr', 0):.2%}")
    print(f"  Sharpe:        {m.get('sharpe', 0):.2f}")
    print(f"  Max Drawdown:  {m.get('max_drawdown', 0):.2%}")
    print(f"  Volatility:    {m.get('annualised_volatility', 0):.2%}")
    print(f"\nReport saved to: {args.output}/report.md")


if __name__ == "__main__":
    main()
