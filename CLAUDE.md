# portfolio-sim

Quantitative trading research platform: data ingestion, backtesting, simulated
execution, risk analysis, significance testing, parameter sweeps, and a local web
platform with interactive reports.

## Tech Stack

- **Python 3.11+** — primary language
- **pandas / numpy / scipy** — data manipulation, statistics
- **yfinance** (default) / **lseg-data** (optional) — market data
- **FastAPI + uvicorn** — web backend; **Plotly.js via CDN + vanilla JS** — frontend
- **matplotlib** — PNG charts for the Markdown report
- **pytest** — testing (`fastapi.testclient` for the web app)

## Project Layout

```
portfolio-sim/
├── data/                # loader.py (yfinance + parquet cache), lseg.py, cache/ (gitignored)
├── backtesting/         # engine.py, portfolio.py, metrics.py, trades.py (round trips)
├── execution/           # order.py, fill.py (slippage + commission)
├── evaluation/          # evaluator.py, significance.py, serialize.py, reporter.py, html_reporter.py
├── pipeline/            # pipeline.py — Pipeline.run().evaluate().report(); to_dict()
├── risk/                # var.py, drawdown.py, correlation.py
├── strategies/          # base.py + buy_and_hold, equal_weight, momentum, mean_reversion
├── optimization/        # sweep.py (grid_search), efficient_frontier.py, rebalancing.py
├── web/                 # app.py (FastAPI), store.py (RunStore), registry.py, static/
├── scripts/             # serve.py, run_pipeline.py, run_sweep.py, fetch_data.py, ...
├── reports/             # generated output; reports/runs/ holds platform runs (gitignored)
└── tests/
```

## Common Commands

```bash
pip install -r requirements.txt
python scripts/serve.py                      # platform at http://127.0.0.1:8000
python scripts/run_pipeline.py --strategy momentum --param lookback=120 --param top_n=2 \
    --tickers AAPL MSFT --benchmark SPY --start 2018-01-01 --end 2024-12-31 --output reports/momentum
python scripts/run_sweep.py --strategy momentum --tickers AAPL MSFT --grid lookback=20,60,120 --grid top_n=1,2
pytest tests/
```

## Conventions

- Strategies subclass `strategies/base.py:Strategy`, set `name`, and implement
  `generate_signals(data) -> pd.DataFrame` of `{-1, 0, 1}` aligned to `data`.
  Constructor kwargs must be typed with defaults — `web/registry.py` introspects them
  to build the UI form and to coerce API parameters.
- Engine semantics: fresh `1` opens or (with `rebalance=True`) resizes to target weight;
  fresh `-1` closes; unchanged signal does nothing. `execution_lag=1` is the default
  (fill at next close). Tests that need same-bar fills set `execution_lag=0`.
- Backtest results are `BacktestResult` dataclasses; evaluated results are
  `BacktestReport`. Never pass raw dicts between stages.
- `evaluation/serialize.py:report_to_dict` is the single JSON contract consumed by
  `web/static/report.js`, `RunStore` and `HTMLReporter`. Add new fields there and
  render them in `report.js`; do not fork the schema.
- `web/static/report.js` is shared by the platform page and the standalone
  `report.html`. Charts read colours from CSS custom properties in `style.css`
  (light + dark tokens). Never hardcode chart colours in JS.
- Data paths are resolved relative to the project root with `pathlib`. Never hardcode absolute paths.
- Risk metrics operate on return series, not prices.
- Dates are timezone-aware UTC internally; localise only at the output layer.
- Monetary values are `float`; no currency conversion.
- Significance analysis is deterministic (`seed`); tests use small `n_samples`.

## Adding a New Strategy

1. Create `strategies/<name>.py` subclassing `Strategy` with typed `__init__` kwargs.
2. Register it in `strategies/__init__.py` and `web/registry.py:STRATEGY_CLASSES`.
3. Add at least one test in `tests/test_strategies.py`.

## Testing notes

- Web tests patch `pipeline.pipeline.fetch_prices` (imported at module level in the
  pipeline) to avoid network access.
- Chrome headless (`chrome.exe --headless=new --screenshot`) is a quick way to eyeball
  a generated `report.html`.

## Not In Scope (yet)

- Live trading / brokerage API integration
- Options / derivatives pricing
- Machine learning signal generation
- Multi-currency portfolios
- Authentication / multi-user deployment
