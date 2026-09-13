"""CLI entry point: run a strategy backtest end-to-end via Pipeline.

Examples::

    python scripts/run_pipeline.py --strategy momentum --tickers AAPL MSFT NVDA \
        --start 2018-01-01 --end 2024-12-31 --benchmark SPY --param lookback=120 --param top_n=2

    python scripts/run_pipeline.py --strategy buy_and_hold --tickers EQNR.OL --data-source lseg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.pipeline import Pipeline
from web.registry import STRATEGY_CLASSES, build


def _parse_params(items: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--param expects key=value, got '{item}'")
        key, value = item.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a trading strategy backtest.")
    parser.add_argument("--strategy", choices=sorted(STRATEGY_CLASSES), default="buy_and_hold")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                        help="Strategy constructor parameter (repeatable), e.g. --param lookback=60")
    parser.add_argument("--tickers", nargs="+", required=True, help="Ticker symbols, e.g. AAPL MSFT")
    parser.add_argument("--benchmark", default=None, help="Benchmark ticker for alpha/beta, e.g. SPY")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--execution-lag", type=int, default=1, help="Bars between signal and fill (0 = same close)")
    parser.add_argument("--no-rebalance", action="store_true", help="Ignore repeat long signals on held positions")
    parser.add_argument("--max-weight", type=float, default=None, help="Cap per-ticker target weight (0-1)")
    parser.add_argument("--risk-free-rate", type=float, default=0.0)
    parser.add_argument("--no-significance", action="store_true", help="Skip bootstrap / randomisation tests")
    parser.add_argument("--n-samples", type=int, default=1000, help="Bootstrap sample count")
    parser.add_argument("--data-source", choices=["yfinance", "lseg"], default="yfinance")
    parser.add_argument("--output", default="reports/", help="Directory for report output")
    args = parser.parse_args()

    params = _parse_params(args.param)
    strategy = build(args.strategy, params)

    print(f"Running {args.strategy} {params or ''} on {args.tickers} ({args.start} -> {args.end}) ...")

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
            benchmark=args.benchmark,
            execution_lag=args.execution_lag,
            rebalance=not args.no_rebalance,
            max_weight=args.max_weight,
            risk_free_rate=args.risk_free_rate,
            significance=not args.no_significance,
            n_samples=args.n_samples,
        )
        .run()
        .evaluate()
        .report(output=args.output)
    )

    report = p.get_report()
    m = report.metrics
    ts = report.trade_stats
    print("\n-- Results -------------------------------------------")
    print(f"  Total Return:  {m.get('total_return', 0):.2%}")
    print(f"  CAGR:          {m.get('cagr', 0):.2%}")
    print(f"  Sharpe:        {m.get('sharpe', 0):.2f}   Sortino: {m.get('sortino', 0):.2f}   Calmar: {m.get('calmar', 0):.2f}")
    print(f"  Max Drawdown:  {m.get('max_drawdown', 0):.2%}")
    print(f"  Volatility:    {m.get('annualised_volatility', 0):.2%}")
    if "beta" in m:
        print(f"  Alpha / Beta:  {m['alpha']:.2%} / {m['beta']:.2f}")
    print(f"  Round trips:   {ts.get('n_trades', 0)}  (win rate {ts.get('win_rate', 0):.0%}, "
          f"profit factor {ts.get('profit_factor', 0):.2f})")
    if report.significance is not None:
        s = report.significance
        lo, hi = s.sharpe_ci_95
        print(f"  Sharpe 95% CI: [{lo:.2f}, {hi:.2f}]   PSR: {s.prob_sharpe_ratio:.1%}   "
              f"sign-flip p: {s.p_value_sharpe:.4f}")
    out = Path(args.output)
    print(f"\nReport saved to: {out / 'report.md'}  and  {out / 'report.html'}")


if __name__ == "__main__":
    main()
