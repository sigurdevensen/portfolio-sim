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
from research.library import families, filter_algorithms, library_for
from research.report import batch_to_dict
from research.universes import UNIVERSES, load_universe


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-test the algorithm library with overfitting controls.")
    parser.add_argument("--tickers", nargs="+", default=None, help="Explicit tickers (or use --universe)")
    parser.add_argument("--universe", choices=sorted(UNIVERSES), default=None,
                        help="Named universe with external series + dividends (enables macro/event algorithms)")
    parser.add_argument("--start", default=None)
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
    parser.add_argument("--sizing", choices=["fixed", "active"], default="fixed",
                        help="fixed: 1/n_tickers per name; active: 1/n_held per name (fully invested)")
    parser.add_argument("--rebalance-band", type=float, default=0.0,
                        help="Only resize a held name when |target/current-1| exceeds this (e.g. 0.25)")
    parser.add_argument("--prior-trials", type=int, default=0,
                        help="Algorithms tried in earlier rounds/configs; added to N for the corrections")
    parser.add_argument("--n-jobs", type=int, default=1, help="Worker processes (0 = all cores)")
    parser.add_argument("--data-source", choices=["yfinance", "lseg"], default="yfinance")
    parser.add_argument("--output", default=None, help="Directory for batch.json (+ batch.html)")
    parser.add_argument("--top", type=int, default=20, help="Rows to print")
    args = parser.parse_args()

    if not args.tickers and not args.universe:
        raise SystemExit("Provide --tickers or --universe")
    if args.universe:
        market = load_universe(args.universe, start=args.start, end=args.end)
        args.tickers = market.tickers
        args.start = args.start or UNIVERSES[args.universe]["default_start"]
        if market.meta.get("dropped"):
            print(f"Dropped (insufficient history): {market.meta['dropped']}")
    elif args.data_source == "lseg":
        from data.lseg import LSEGDataFeed
        from data.market import MarketData
        args.start = args.start or "2015-01-01"
        market = MarketData.from_close(LSEGDataFeed().fetch_prices(args.tickers, args.start, args.end))
    else:
        from data.market import fetch_market_data
        args.start = args.start or "2015-01-01"
        market = fetch_market_data(args.tickers, args.start, args.end)

    specs = filter_algorithms(families=args.families, data_types=args.data_types, limit=args.limit, universe=args.universe)
    cfg = BatchConfig(
        start=args.start, end=args.end, initial_capital=args.capital, commission=args.commission,
        slippage_bps=args.slippage_bps, execution_lag=args.execution_lag, is_fraction=args.is_fraction,
        n_boot=args.n_boot, pbo_blocks=args.pbo_blocks, min_trades=args.min_trades,
        sizing=args.sizing, prior_trials=args.prior_trials, rebalance_band=args.rebalance_band,
    )
    print(f"Testing {len(specs)} of {len(library_for(args.universe))} algorithms on {args.tickers} ({args.start} -> {args.end}), "
          f"{len(market.index)} days, n_jobs={args.n_jobs} ...")
    t0 = time.time()

    def progress(done: int, total: int, name: str) -> None:
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total}  {name}")

    res = run_batch(specs, market, cfg, n_jobs=args.n_jobs, progress=progress)
    s = res.summary
    print(f"\nDone in {time.time() - t0:.1f}s. {s['n_algorithms']} algorithms, {s['n_failed']} failed.")
    print("\n-- Batch verdict (all statistics on returns in EXCESS of equal-weight buy-and-hold) --")
    print(f"  Benchmark Sharpe (buy & hold): {s['benchmark_sharpe']:.2f}")
    print(f"  Sizing: {args.sizing} (band {args.rebalance_band})   trials counted N={s['n_trials']} (this batch {s['n_algorithms']} + prior {args.prior_trials})")
    print(f"  Expected max excess Sharpe under H0 (N={s['n_trials']}): {s['expected_max_sharpe']:.2f}"
          f"   observed max: {s['observed_max_sharpe']:.2f}")
    print(f"  White's Reality Check p-value:  {s['reality_check_p']:.4f}   (best: {s['reality_check_best']})")
    print(f"  Probability of Backtest Overfitting (CSCV): {s['pbo']:.2f}  over {s['pbo_combinations']} splits")
    print(f"  IS/OOS Sharpe rank correlation: {s['is_oos_rank_corr']}")
    print(f"  Strong edges: {s['n_strong']}   candidates: {s['n_candidate']}   "
          f"random controls flagged strong: {s['n_random_controls_strong']}")
    print(f"  Best in-sample: {s['best_is_name']}  IS excess Sharpe {s['best_is_sharpe_is']:.2f} -> OOS {s['best_is_oos_sharpe']:.2f}")
    print(f"  Beta-adjusted view (Jensen alpha, HAC t-stat, FDR over N): strong {s['n_alpha_strong']}  "
          f"candidates {s['n_alpha_candidate']}  best {s['best_alpha_name']} t={s['best_alpha_t']:.2f} "
          f"p_fdr={s['best_alpha_p_fdr']:.3f}  random controls flagged {s['n_random_controls_alpha_strong']}")
    if s["best_is_consistent_with_luck"]:
        print("  => The best result is consistent with luck given the number of trials.")
    else:
        print("  => The best result is NOT explained by selection alone.")

    cols = ["family", "excess_sharpe_is", "excess_sharpe_oos", "sharpe_full", "max_drawdown_full", "n_trades",
            "p_fdr", "dsr", "edge", "alpha_ann", "alpha_oos_ann", "beta", "alpha_t", "p_alpha_fdr", "alpha_edge"]
    import pandas as pd
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print("\n-- Leaderboard (sorted by in-sample excess Sharpe) -----")
        print(res.leaderboard[cols].head(args.top).round(3).to_string())
        print("\n-- Top by alpha t-stat -----------------------------------")
        print(res.leaderboard.sort_values("alpha_t", ascending=False)[cols].head(min(args.top, 12)).round(3).to_string())
    if res.errors:
        print("\nErrors:")
        for k, v in res.errors.items():
            print(f"  {k}: {v}")

    if args.output:
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        d = batch_to_dict(res, meta={"batch_id": out.name, "tickers": args.tickers, "universe": args.universe})
        (out / "batch.json").write_text(json.dumps(d), encoding="utf-8")
        try:
            from evaluation.html_reporter import BatchHTMLReporter
            BatchHTMLReporter().write(d, out)
        except ImportError:
            pass
        print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
