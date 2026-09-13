# portfolio-sim

Quantitative trading research platform: OHLCV data ingestion, backtesting with stops,
simulated execution, risk analysis, significance testing, an algorithm lab that
mass-tests 100+ algorithms with multiple-testing corrections, parameter sweeps, and a
local web platform with interactive reports.

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
├── data/                # loader.py (closes), market.py (MarketData OHLCV), lseg.py, cache/ (gitignored)
├── backtesting/         # engine.py (lag, rebalance, stops), portfolio.py, metrics.py, trades.py
├── execution/           # order.py, fill.py
├── evaluation/          # evaluator.py, significance.py, serialize.py, reporter.py, html_reporter.py
├── strategies/          # base.py, _util.py, technical/volume/cross_sectional/calendar/regime/macro/events/anomalies/random_control.py
├── research/            # library.py (116 + 92 AlgoSpecs), universes.py, edge.py (FDR/DSR/RC/PBO/alpha), batch.py, report.py
├── optimization/        # sweep.py, efficient_frontier.py, rebalancing.py
├── pipeline/            # pipeline.py — Pipeline.run().evaluate().report(); to_dict()
├── risk/                # var.py, drawdown.py, correlation.py
├── web/                 # app.py (FastAPI), store.py (JsonStore/RunStore), registry.py, static/
├── scripts/             # serve.py, run_batch.py, run_pipeline.py, run_sweep.py, fetch_data.py, ...
├── reports/             # generated; reports/runs/ and reports/batches/ are gitignored
└── tests/
```

## Common Commands

```bash
pip install -r requirements.txt
python scripts/serve.py                      # platform at http://127.0.0.1:8000
python scripts/run_batch.py --universe oslo --n-jobs 0 --sizing active --rebalance-band 0.25 --output reports/batches/oslo
python scripts/run_batch.py --tickers AAPL MSFT NVDA --start 2015-01-01 --n-jobs 0 --output reports/batches/demo
python scripts/run_pipeline.py --strategy momentum --param lookback=120 --tickers AAPL MSFT --benchmark SPY
python scripts/run_sweep.py --strategy momentum --tickers AAPL MSFT --grid lookback=20,60,120
pytest tests/                                # ~1 minute; batch tests use n_jobs=1 and tiny n_boot
```

## Conventions

- Strategies subclass `strategies/base.py:Strategy`, set `name`, and implement
  `generate_signals(close) -> DataFrame` of `{-1, 0, 1}`. Strategies needing OHLCV
  override `generate_signals_market(market)` and set `requires`. Constructor kwargs
  must be typed with defaults; `web/registry.py` introspects them for the UI and API.
  Register new families in the module's `*_FAMILIES` list (feeds `strategies.ALL_FAMILIES`).
- Use `strategies/_util.py` helpers: `state_signals(long_mask)` for "in/out" strategies,
  `enter_exit_signals(enter, exit)` for event strategies. Never emit NaN signals.
- Engine semantics: fresh `1` opens or (with `rebalance=True`) resizes to target weight;
  fresh `-1` closes; unchanged signal does nothing. `execution_lag=1` default. Stops
  are evaluated on the close before signals; fills carry a `reason`.
- **Algorithm lab rules (anti-overfitting):** parameters in `research/library.py` are
  fixed a priori — never tune them on data and add them back. Every edge statistic in
  `research/edge.py` runs on returns *in excess of equal-weight buy-and-hold* of the
  same universe with the same costs; the Jensen-alpha view is reported alongside, never
  instead. When a search runs several rounds, pass `prior_trials` so N keeps counting
  everything tried. Universes in `research/universes.py` are fixed before testing; do
  not edit a ticker list after seeing results. Random-control algorithms must never come
  out `strong`; if they do, the framework is broken, not the market. Keep `n_boot`
  small in tests.
- **Sizing:** use `sizing="active"` with `rebalance_band=0.25` for cross-sectional
  comparisons (fixed sizing leaves top-N strategies mostly in cash).
- **Known result (Sept 2026):** on the Oslo search universe no algorithm passes the strong
  gate after 796 trials. The Amihud illiquidity ranking (`illiquidity_rank_252_5`) was
  then confirmed by a pre-registered single-hypothesis test on the disjoint
  `oslo_holdout` universe (t 2.46, p 0.007). Treat it as a small-account edge with a
  survivorship caveat; never re-tune it. `oslo_holdout` is reserved for pre-registered
  confirmations only — do not search on it. See README "What the lab found".
- Backtest results are `BacktestResult`; evaluated results are `BacktestReport`;
  batches are `BatchResult`. Never pass raw dicts between stages.
- `evaluation/serialize.py:report_to_dict` and `research/report.py:batch_to_dict` are
  the JSON contracts consumed by `web/static/report.js` / `batch.js`, the stores and the
  HTML reporters. Add fields there and render them in the JS; do not fork schemas.
- Charts read colours from CSS custom properties in `style.css` (light + dark tokens);
  never hardcode chart colours in JS.
- Data paths are resolved relative to the project root with `pathlib`. Dates are UTC
  internally. Monetary values are `float`.

## Testing notes

- Web tests patch `pipeline.pipeline.fetch_prices` and `web.app.fetch_market_data`.
- `tests/test_families.py` runs every family on synthetic OHLCV; `tests/test_library.py`
  runs every one of the 116 algorithms through the engine.
- `tests/test_edge.py` calibrates the mathematics on planted-edge vs pure-noise and
  bull-market-beta matrices; keep those invariants when changing `edge.py`.
- Chrome headless (`chrome.exe --headless=new --screenshot`) is a quick way to eyeball
  a generated `report.html` / `batch.html`.

## Not In Scope (yet)

- Live trading / brokerage API integration
- Options / derivatives pricing
- Machine learning signal generation
- Multi-currency portfolios
- Parameter optimisation inside the lab (by design), authentication / multi-user
