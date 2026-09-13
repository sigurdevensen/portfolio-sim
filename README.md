# portfolio-sim

A quantitative trading research platform: market data ingestion, a bias-aware
backtest engine with stops, simulated execution, risk analysis, statistical
significance testing, an **algorithm lab** that tests 100+ algorithms at once with
multiple-testing corrections, parameter sweeps, and a local website with
interactive reports.

## Quick start

```bash
pip install -r requirements.txt

# 1. Start the platform and open http://127.0.0.1:8000  (tabs: Backtest, Algorithm lab)
python scripts/serve.py

# 2. Test the whole algorithm library on a universe (parallel) and rank by edge
python scripts/run_batch.py --tickers AAPL MSFT NVDA AMZN GOOGL META JPM XOM JNJ PG \
    --start 2015-01-01 --end 2024-12-31 --n-jobs 0 --output reports/batches/us10

# 3. Backtest one strategy and open reports/momentum/report.html
python scripts/run_pipeline.py --strategy momentum --param lookback=120 --param top_n=2 \
    --tickers AAPL MSFT NVDA --benchmark SPY --start 2018-01-01 --end 2024-12-31 \
    --output reports/momentum

# 4. Grid-search one family's parameters
python scripts/run_sweep.py --strategy momentum --tickers AAPL MSFT NVDA \
    --grid lookback=20,60,120,252 --grid top_n=1,2 --objective sharpe

# 5. Tests
pytest tests/
```

## The algorithm lab (mass testing without fooling yourself)

`research/library.py` holds **116 algorithms** from 29 families, all with parameters
fixed a priori from textbook defaults (nothing is tuned on the data). Families span
five data types: price (moving-average crosses, MACD, RSI, Bollinger, momentum, mean
reversion, volatility regime, dip buying, streak reversal), OHLC (Donchian, Keltner,
ATR breakouts, stochastic, gap reversal), volume (volume-confirmed breakout, OBV,
volume-z capitulation), calendar (turn-of-month, day-of-week, sell-in-May) and
cross-sectional (relative strength, low volatility, dual momentum, 52-week high).
Some variants add a 10 % stop-loss or a 15 % trailing stop. Five **random-signal
controls** are included so the framework can be seen to reject noise.

`research/batch.py` backtests every algorithm on the same OHLCV data (process pool),
producing a `T x N` matrix of daily returns. `research/edge.py` then decides which
algorithms have an edge, **in excess of equal-weight buy-and-hold of the same
universe with the same costs** (market beta is not skill):

| Statistic | Question it answers |
|---|---|
| In-sample / out-of-sample split (60/40) | Does the ranking survive data the selection never saw? |
| Benjamini–Hochberg `p_fdr`, Holm `p_holm` | Which per-algorithm p-values survive N comparisons? |
| Deflated Sharpe Ratio (Bailey & López de Prado) | Is the Sharpe above what the best of N noise trials would reach? |
| White's Reality Check | Joint bootstrap null for the *best* algorithm's performance. |
| Probability of Backtest Overfitting (CSCV) | How often is the in-sample winner below median out of sample? |
| Block stability, MinTRL | Is the edge consistent across time, and how much history would confirm it? |

Verdict per algorithm: **strong** (`p_fdr < 0.05`, DSR > 0.95, OOS excess Sharpe > 0,
stability ≥ 60 %, ≥ 20 trades), **candidate** (`p_fdr < 0.10`, OOS excess Sharpe > 0,
≥ 20 trades) or **none**. The batch also reports whether the best result is
consistent with luck given the number of trials.

The lab tab of the website shows the verdict, an IS-vs-OOS excess-Sharpe scatter (the
overfitting picture), the distribution of Sharpes against `E[max SR]`, the Reality
Check null, the PBO logit distribution, top equity curves against the benchmark, and a
sortable leaderboard; clicking a row loads that algorithm into the backtest form.

## Single-strategy reports

Every backtest produces one JSON run (`run.json`) which drives three views: the
website, a self-contained `report.html`, and a Markdown report with PNG charts:
prices with ▲/▼ order fills, equity curve vs benchmark, drawdown, monthly heatmap,
daily-return histogram with VaR, correlation, significance panel (bootstrap Sharpe
CI, sign-flip null, PSR, t-test), statistics, round trips, fills, drawdown episodes.

## Tech stack

| Library | Purpose |
|---|---|
| Python 3.11+ | Primary language |
| pandas / numpy / scipy | Data handling, statistics |
| yfinance, lseg-data | Market data (yfinance default; LSEG Workspace optional) |
| FastAPI + uvicorn | Web platform backend |
| Plotly.js (CDN), vanilla JS | Interactive charts in the browser |
| matplotlib | PNG charts for the Markdown report |
| pytest | Tests |

## Project layout

```
portfolio-sim/
├── data/
│   ├── loader.py               # fetch_prices() (closes) with parquet cache, load_csv()
│   ├── market.py               # MarketData OHLCV bundle, fetch_market_data(), from_close()
│   └── lseg.py                 # LSEGDataFeed
├── backtesting/
│   ├── engine.py               # BacktestEngine: execution lag, rebalance, stops, sizing
│   ├── portfolio.py, metrics.py, trades.py
├── execution/                  # Order / Fill, FillSimulator (slippage + commission)
├── evaluation/
│   ├── evaluator.py            # BacktestReport
│   ├── significance.py         # single-strategy bootstrap / sign-flip / PSR
│   ├── serialize.py            # run JSON contract
│   ├── reporter.py             # Markdown + PNG
│   └── html_reporter.py        # HTMLReporter, BatchHTMLReporter
├── strategies/
│   ├── base.py                 # Strategy (+ stop_loss / take_profit / trailing_stop, requires)
│   ├── _util.py                # indicators and signal shaping
│   ├── technical.py, volume.py, cross_sectional.py, calendar.py, regime.py, random_control.py
│   └── buy_and_hold.py, equal_weight.py, momentum.py, mean_reversion.py
├── research/
│   ├── library.py              # AlgoSpec, ALGORITHMS (116), build_algorithm(), filter_algorithms()
│   ├── edge.py                 # FDR/Holm, DSR, Reality Check, PBO (CSCV), stability, assess()
│   ├── batch.py                # run_batch() -> BatchResult (parallel)
│   └── report.py               # batch_to_dict(), BatchStore
├── optimization/               # sweep.py (grid_search), efficient_frontier.py, rebalancing.py
├── pipeline/pipeline.py        # Pipeline: run() -> evaluate() -> report(); to_dict()
├── risk/                       # VaR / CVaR, drawdown episodes, correlations
├── web/
│   ├── app.py                  # FastAPI: /api/strategies, /api/runs, /api/backtest, /api/algorithms, /api/batch(es)
│   ├── store.py                # JsonStore, RunStore
│   ├── registry.py             # strategy name -> class + parameter schema
│   └── static/                 # index.html, app.js, report.js, batch.js, style.css
├── scripts/                    # serve.py, run_batch.py, run_pipeline.py, run_sweep.py, ...
└── tests/
```

## Engine semantics

- Signals are `{-1, 0, 1}` per ticker per bar. A fresh `1` opens (or, with
  `rebalance=True`, resizes) a position at target weight `1 / n_tickers` capped by
  `max_weight`; a fresh `-1` closes it; `0` or an unchanged signal does nothing.
- `execution_lag=1` (default) fills at the next bar's close, removing same-close
  look-ahead. Use `execution_lag=0` for same-bar fills.
- Stops (`stop_loss`, `take_profit`, `trailing_stop` on the strategy) are checked
  on each close before signals; after a stop, re-entry needs the signal to leave `1`
  and return. Fills record a `reason` (`signal`, `rebalance`, `stop_loss`, ...).
- Strategies that need open/high/low/volume override `generate_signals_market(market)`;
  close-only strategies keep implementing `generate_signals(close)`.
- Fills apply directional slippage and proportional commission; orders that exceed
  available cash are sized down.

## Web API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/strategies` | registered strategies with typed parameters |
| POST | `/api/backtest` | run + evaluate + save one strategy |
| GET / DELETE | `/api/runs`, `/api/runs/{id}` | saved runs |
| GET | `/api/algorithms` | the algorithm library |
| POST | `/api/batch` | test many algorithms with overfitting controls |
| GET / DELETE | `/api/batches`, `/api/batches/{id}` | saved batches |
| GET | `/runs/{id}/report.html`, `/batches/{id}/report.html` | standalone reports |

## Adding a strategy family

1. Create the class in the matching `strategies/*.py` module, subclassing `Strategy`
   with typed keyword arguments and defaults; set `name`, and `requires` if it reads
   more than closes. Add it to that module's `*_FAMILIES` list (it then appears in
   `strategies.ALL_FAMILIES`, the registry and the web form).
2. Add its a-priori parameter sets to `research/library.py` and a `DATA_TYPES` entry.
3. Add a behavioural test in `tests/test_families.py`.

## Data sources

- **yfinance** (default) — OHLCV for equities, ETFs, crypto; cached as parquet.
- **LSEG Workspace** — `--data-source lseg`; requires the Workspace app and
  `pip install lseg-data` (closes only; OHLC is synthesised and flagged).

## Not in scope (yet)

Live trading, options pricing, ML signal generation, multi-currency portfolios,
parameter optimisation inside the lab (by design), authentication.
