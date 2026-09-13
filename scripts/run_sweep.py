"""CLI: grid-search strategy parameters and print a ranked table.

Example::

    python scripts/run_sweep.py --strategy momentum --tickers AAPL MSFT NVDA \
        --start 2018-01-01 --end 2024-12-31 --grid lookback=20,60,120,252 --grid top_n=1,2 \
        --objective sharpe
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from optimization.sweep import OBJECTIVES, grid_search
from web.registry import STRATEGY_CLASSES


def _parse_value(raw: str):
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            continue
    return raw


def _parse_grid(items: list[str]) -> dict[str, list]:
    grid: dict[str, list] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--grid expects name=v1,v2,..., got '{item}'")
        key, values = item.split("=", 1)
        grid[key.strip()] = [_parse_value(v.strip()) for v in values.split(",") if v.strip()]
    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-search strategy parameters.")
    parser.add_argument("--strategy", choices=sorted(STRATEGY_CLASSES), required=True)
    parser.add_argument("--grid", action="append", default=[], metavar="NAME=V1,V2,...", required=True)
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--objective", choices=OBJECTIVES, default="sharpe")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--execution-lag", type=int, default=1)
    parser.add_argument("--data-source", choices=["yfinance", "lseg"], default="yfinance")
    parser.add_argument("--output", default=None, help="Optional path to write the ranked table as JSON")
    args = parser.parse_args()

    if args.data_source == "lseg":
        from data.lseg import LSEGDataFeed
        prices = LSEGDataFeed().fetch_prices(args.tickers, args.start, args.end)
    else:
        from data.loader import fetch_prices
        prices = fetch_prices(args.tickers, args.start, args.end)

    grid = _parse_grid(args.grid)
    print(f"Sweeping {args.strategy} over {grid} on {args.tickers} ({args.start} -> {args.end}) ...")
    res = grid_search(
        args.strategy, grid, prices, objective=args.objective, initial_capital=args.capital,
        commission=args.commission, slippage_bps=args.slippage_bps, execution_lag=args.execution_lag,
    )
    cols = list(grid) + ["sharpe", "sortino", "cagr", "max_drawdown", "total_return", "n_trades", "win_rate", "error"]
    with __import__("pandas").option_context("display.width", 200, "display.max_columns", 30):
        print(res.table[cols].round(4).to_string(index=False))
    print(f"\nBest by {args.objective}: {{ {', '.join(f'{k}={res.best[k]}' for k in grid)} }}")
    if args.output:
        Path(args.output).write_text(json.dumps(res.to_dict(), indent=2), encoding="utf-8")
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
