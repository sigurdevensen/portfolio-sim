"""CLI: test the whole algorithm library on one universe and rank by edge.

Examples::

    python scripts/run_batch.py --tickers AAPL MSFT NVDA AMZN GOOGL META JPM XOM JNJ PG \
        --start 2015-01-01 --end 2024-12-31 --n-jobs 4 --output reports/batches/us10

    python scripts/run_batch.py --tickers EQNR.OL DNB.OL --families sma_cross rsi_reversal random --n-boot 500
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from research.batch import BatchConfig, run_batch
from research.library import ALGORITHMS, families, filter_algorithms
from research.report import batch_to_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-test the algorithm library with overfitting controls.")
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--families", nargs="*", default=None, help=f"Subset of families. Available: {', '.join(families())}")
    parser.add_argument("--data-types", nargs="*", default=None, choices=["price", "ohlc", "volume", "calendar", "cross_sectional"])
    parser.add_argument("--limit", type=int, default=None, help="Only the first N algorithms (for quick runs)")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--execution-lag", type=int, default=1)
    parser.add_argument("--is-fraction", type=float, default=0.6, help="Share of days used in-sample")
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--pbo-blocks", type=int, default=16)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--n-jobs", type=int, default=1, help="Worker processes (0 = all cores)")
    parser.add_argument("--data-source", choices=["yfinance", "lseg"], default="yfinance")
    parser.add_argument("--output", default=None, help="Directory for batch.json (+ batch.html)")
    parser.add_argument("--top", type=int, default=20, help="Rows to print")
    args = parser.parse_args()

    if args.data_source == "lseg":
        from data.lseg import LSEGDataFeed
        from data.market import MarketData
        market = MarketData.from_close(LSEGDataFeed().fetch_prices(args.tickers, args.start, args.end))
    else:
        from data.market import fetch_market_data
        market = fetch_market_data(args.tickers, args.start, args.end)

    specs = filter_algorithms(families=args.families, data_types=args.data_types, limit=args.limit)
    cfg = BatchConfig(
        start=args.start, end=args.end, initial_capital=args.capital, commission=args.commission,
        slippage_bps=args.slippage_bps, execution_lag=args.execution_lag, is_fraction=args.is_fraction,
        n_boot=args.n_boot, pbo_blocks=args.pbo_blocks, min_trades=args.min_trades,
    )
    print(f"Testing {len(specs)} of {len(ALGORITHMS)} algorithms on {args.tickers} ({args.start} -> {args.end}), "
          f"{len(market.index)} days, n_jobs={args.n_jobs} ...")
    t0 = time.time()

    def progress(done: int, total: int, name: str) -> None:
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total}  {name}")

    res = run_batch(specs, market, cfg, n_jobs=args.n_jobs, progress=progress)
    s = res.summary
    print(f"\nDone in {time.time() - t0:.1f}s. {s['n_algorithms']} algorithms, {s['n_failed']} failed.")
    print("\n-- Batch verdict ---------------------------------------")
    print(f"  Expected max Sharpe under H0 (N={s['n_algorithms']}): {s['expected_max_sharpe']:.2f}"
          f"   observed max: {s['observed_max_sharpe']:.2f}")
    print(f"  White's Reality Check p-value:  {s['reality_check_p']:.4f}   (best: {s['reality_check_best']})")
    print(f"  Probability of Backtest Overfitting (CSCV): {s['pbo']:.2f}  over {s['pbo_combinations']} splits")
    print(f"  IS/OOS Sharpe rank correlation: {s['is_oos_rank_corr']}")
    print(f"  Strong edges: {s['n_strong']}   candidates: {s['n_candidate']}   "
          f"random controls flagged strong: {s['n_random_controls_strong']}")
    print(f"  Best in-sample: {s['best_is_name']}  IS Sharpe {s['best_is_sharpe_is']:.2f} -> OOS Sharpe {s['best_is_oos_sharpe']:.2f}")
    if s["best_is_consistent_with_luck"]:
        print("  => The best result is consistent with luck given the number of trials.")
    else:
        print("  => The best result is NOT explained by selection alone.")

    cols = ["family", "sharpe_is", "sharpe_oos", "sharpe_full", "cagr_full", "max_drawdown_full", "n_trades",
            "p_value", "p_fdr", "dsr", "stability", "edge"]
    import pandas as pd
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print("\n-- Leaderboard (sorted by in-sample Sharpe) ------------")
        print(res.leaderboard[cols].head(args.top).round(3).to_string())
    if res.errors:
        print("\nErrors:")
        for k, v in res.errors.items():
            print(f"  {k}: {v}")

    if args.output:
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        d = batch_to_dict(res, meta={"batch_id": out.name, "tickers": args.tickers})
        (out / "batch.json").write_text(json.dumps(d), encoding="utf-8")
        try:
            from evaluation.html_reporter import BatchHTMLReporter
            BatchHTMLReporter().write(d, out)
        except ImportError:
            pass
        print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
