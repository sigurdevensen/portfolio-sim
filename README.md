# portfolio-sim

A quantitative trading research platform: market data ingestion, a bias-aware
backtest engine, simulated execution, risk analysis, statistical significance
testing, parameter sweeps, and a local website with interactive reports.

## Quick start

```bash
pip install -r requirements.txt

# 1. Start the platform and open http://127.0.0.1:8000
python scripts/serve.py

# 2. Or run a backtest from the CLI and open reports/momentum/report.html
python scripts/run_pipeline.py --strategy momentum --param lookback=120 --param top_n=2 \
    --tickers AAPL MSFT NVDA --benchmark SPY --start 2018-01-01 --end 2024-12-31 \
    --output reports/momentum

# 3. Grid-search strategy parameters
python scripts/run_sweep.py --strategy momentum --tickers AAPL MSFT NVDA \
    --grid lookback=20,60,120,252 --grid top_n=1,2 --objective sharpe

# 4. Tests
pytest tests/
```

## What the platform shows

Every backtest produces one JSON run (`run.json`) which drives three views: the
website, a self-contained `report.html`, and a Markdown report with PNG charts.

- **Prices with executed orders** — one panel per ticker, ▲ buy and ▼ sell fills with
  quantity, price and fee on hover.
- **Equity curve** vs. benchmark, indexed to 100, with order markers.
- **Drawdown**, **monthly return heatmap**, **daily return distribution** with VaR lines,
  **asset correlation**.
- **Statistical significance** — bootstrap distribution of Sharpe and CAGR with 95%
  confidence intervals, a sign-flip null distribution with its p-value, the
  Probabilistic Sharpe Ratio, and a t-test on mean daily return, summarised in a
  plain-language verdict.
- **Statistics** — CAGR, Sharpe, Sortino, Calmar, volatility, skew/kurtosis, VaR/CVaR,
  alpha/beta/information ratio, win rate, profit factor, expectancy, holding periods.
- **Tables** — FIFO round trips, every order fill, drawdown episodes.

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
│   ├── loader.py               # fetch_prices() via yfinance with parquet cache, load_csv()
│   ├── lseg.py                 # LSEGDataFeed (prices, fundamentals, index constituents)
│   └── cache/                  # cached API responses (gitignored)
├── backtesting/
│   ├── engine.py               # BacktestEngine: execution lag, rebalance-to-target, sizing
│   ├── portfolio.py            # positions, cash, NAV
│   ├── metrics.py              # CAGR, Sharpe, Sortino, Calmar, drawdown, alpha/beta, ...
│   └── trades.py               # FIFO round trips + trade statistics
├── execution/
│   ├── order.py                # Order / Fill dataclasses
│   └── fill.py                 # FillSimulator (slippage + commission)
├── evaluation/
│   ├── evaluator.py            # BacktestReport: metrics, VaR, drawdowns, trades, significance
│   ├── significance.py         # bootstrap CI, sign-flip test, Probabilistic Sharpe Ratio
│   ├── serialize.py            # BacktestReport -> JSON run dict (the shared contract)
│   ├── reporter.py             # Markdown + PNG report
│   └── html_reporter.py        # self-contained interactive report.html
├── pipeline/pipeline.py        # Pipeline: run() -> evaluate() -> report(); to_dict()
├── risk/                       # VaR / CVaR, drawdown episodes, correlations
├── strategies/                 # Strategy base class + buy_and_hold, equal_weight, momentum, mean_reversion
├── optimization/
│   ├── sweep.py                # grid_search() over strategy parameters
│   ├── efficient_frontier.py
│   └── rebalancing.py
├── web/
│   ├── app.py                  # FastAPI app: /api/strategies, /api/runs, /api/backtest
│   ├── store.py                # RunStore: reports/runs/<run_id>/run.json
│   ├── registry.py             # strategy name -> class + parameter schema for the UI
│   └── static/                 # index.html, app.js, report.js (shared renderer), style.css
├── scripts/
│   ├── serve.py                # start the platform
│   ├── run_pipeline.py         # CLI backtest -> report.md / report.html / run.json
│   ├── run_sweep.py            # CLI parameter grid search
│   └── ...                     # data download + ad-hoc analysis scripts
└── tests/
```

## Using the Python API

```python
from pipeline.pipeline import Pipeline
from strategies import Momentum

p = (
    Pipeline(
        strategy=Momentum(lookback=120, top_n=2),
        tickers=["AAPL", "MSFT", "NVDA"],
        benchmark="SPY",
        start="2018-01-01",
        end="2024-12-31",
        initial_capital=1_000_000,
        commission=0.001,        # 0.1 %
        slippage_bps=5,
        execution_lag=1,         # signal on day t fills at close of t+1
        rebalance=True,          # fresh long signal on a held ticker resizes to target weight
        n_samples=1000,          # bootstrap samples for the significance tests
    )
    .run()
    .evaluate()
    .report(output="reports/momentum")
)
report = p.get_report()          # BacktestReport (metrics, trade_stats, significance, ...)
run = p.to_dict()                # JSON-safe dict used by the website
```

### Web API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/strategies` | registered strategies with typed parameters |
| POST | `/api/backtest` | run + evaluate + save; returns the full run dict |
| GET | `/api/runs` | run summaries, newest first |
| GET | `/api/runs/{id}` | full run dict |
| DELETE | `/api/runs/{id}` | remove a saved run |
| GET | `/runs/{id}/report.html` | standalone report for a saved run |

## Engine semantics

- Signals are `{-1, 0, 1}` per ticker per bar. A fresh `1` opens (or, with
  `rebalance=True`, resizes) a position at the target weight `1 / n_tickers`
  capped by `max_weight`; a fresh `-1` closes it; `0` or an unchanged signal does nothing.
- `execution_lag=1` (default) fills at the next bar's close, removing same-close
  look-ahead. Use `execution_lag=0` to reproduce the older same-bar behaviour.
- Fills apply directional slippage and proportional commission; orders that exceed
  available cash are sized down.

## Significance methodology

- **Stationary bootstrap** of daily returns (mean block 20 days) gives the sampling
  distribution of Sharpe and CAGR and their 95% confidence intervals.
- **Sign-flip randomisation** builds the null distribution of Sharpe under
  "returns are symmetric around zero" and reports a one-sided p-value. (Shuffling
  order alone would not work: Sharpe is order-invariant.)
- **Probabilistic Sharpe Ratio** (Bailey & Lopez de Prado, 2012) adjusts for skew,
  kurtosis and sample length.

## Adding a strategy

1. Create `strategies/<name>.py` subclassing `Strategy`, set `name`, implement
   `generate_signals(data) -> pd.DataFrame` of `{-1, 0, 1}`. Give `__init__`
   typed keyword arguments with defaults; the web form is generated from them.
2. Register it in `strategies/__init__.py` and in `web/registry.py:STRATEGY_CLASSES`.
3. Add a test in `tests/test_strategies.py`.

## Data sources

- **yfinance** (default) — equities, ETFs, crypto. Cached as parquet in `data/cache/`.
- **LSEG Workspace** — `--data-source lseg`; requires the Workspace app running and
  `pip install lseg-data`.
- CSV drops in `data/raw/` via `data/loader.py:load_csv`.

## Not in scope (yet)

Live trading / brokerage integration, options pricing, ML signal generation,
multi-currency portfolios, authentication or multi-user deployment.
