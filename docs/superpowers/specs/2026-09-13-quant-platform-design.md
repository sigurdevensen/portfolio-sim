# Quant Trading Platform — Design Spec
**Date:** 2026-09-13
**Status:** Decided autonomously under the `/goal` directive; assumptions are listed explicitly so they can be revisited.

## Goal
Turn `portfolio-sim` from a script-driven backtester into a small but complete
quantitative trading platform:

1. **Better trading engine** — remove look-ahead bias, support rebalancing,
   richer metrics, trade-level analytics, benchmark comparison.
2. **Statistical significance** — quantify whether a strategy's performance is
   distinguishable from luck, and expose the full distribution, not a single p-value.
3. **Web platform** — a local website to launch backtests and browse results with
   interactive charts (buy/sell markers on price and NAV), summary statistics,
   trade tables, and the significance distribution.
4. **Portable reports** — every run also produces a self-contained `report.html`
   that renders the same interactive charts without a server.

## Assumptions (made without user input)
- **Backend:** FastAPI + uvicorn. Both are lightweight, testable via `TestClient`,
  and fit the existing Python-only toolchain. Added to `requirements.txt`.
- **Frontend:** vanilla JavaScript + Plotly.js loaded from the Plotly CDN. No Node
  toolchain. Plotly is already a declared dependency (Python side) so the choice is
  consistent with the repo.
- **Persistence:** runs are stored as JSON files under `reports/runs/<run_id>/`.
  No database. Sufficient for a single-user local platform.
- **Significance methods:** stationary bootstrap of daily returns (block length 20)
  for Sharpe / CAGR confidence intervals, permutation test (shuffled returns) for a
  one-sided p-value on Sharpe, and Probabilistic Sharpe Ratio (Bailey & Lopez de
  Prado 2012) versus a benchmark Sharpe of 0. Sample count defaults to 1000.
- **Execution timing:** default becomes next-bar execution (`execution_lag=1`):
  a signal computed on day *t* is filled at the close of day *t+1*. `execution_lag=0`
  preserves the old same-close behaviour for comparison.
- **Signals contract unchanged:** strategies keep returning `{-1, 0, 1}` DataFrames.

## Architecture

```
portfolio-sim/
├── backtesting/
│   ├── engine.py          # BacktestEngine: execution_lag, rebalance-to-target, sizing
│   ├── metrics.py         # + sortino, calmar, skew, kurtosis, win/loss days, rf rate
│   └── trades.py          # NEW: round-trip pairing + trade statistics
├── evaluation/
│   ├── evaluator.py       # BacktestReport gains trade_stats, significance, monthly returns
│   ├── significance.py    # NEW: bootstrap / permutation / PSR -> SignificanceResult
│   ├── serialize.py       # NEW: BacktestReport -> JSON-safe dict (single source for web + html)
│   ├── reporter.py        # MarkdownReporter (unchanged API, adds new sections)
│   └── html_reporter.py   # NEW: HTMLReporter -> self-contained report.html
├── pipeline/pipeline.py   # + benchmark ticker, execution_lag, to_dict()
├── web/                   # NEW
│   ├── app.py             # FastAPI app factory: create_app(store)
│   ├── store.py           # RunStore: save/load/list runs as JSON under reports/runs/
│   ├── registry.py        # Strategy registry: name -> class + param schema (for the UI form)
│   └── static/
│       ├── index.html     # platform shell: run form, run list, report view
│       ├── app.js         # API client + page wiring
│       ├── report.js      # renderReport(container, data) — shared with HTMLReporter
│       └── style.css
├── scripts/
│   ├── run_pipeline.py    # + --benchmark, --execution-lag, --no-significance
│   └── serve.py           # NEW: `python scripts/serve.py` -> uvicorn on :8000
└── tests/
    ├── test_trades.py, test_significance.py, test_serialize.py,
    ├── test_web.py, test_html_reporter.py, test_registry.py
    └── (existing tests updated where behaviour changed)
```

### Data flow
```
UI form --POST /api/backtest--> web.app --> Pipeline.run().evaluate()
                                            |
                                            v
                                   serialize.report_to_dict()
                                            |
                     +----------------------+----------------------+
                     v                      v                      v
             RunStore.save()       HTMLReporter.write()    MarkdownReporter.write()
         reports/runs/<id>/run.json   report.html            report.md + png
                     |
        GET /api/runs/<id> --> report.js renderReport()
```

## Component specs

### 1. Engine (`backtesting/engine.py`)
`BacktestConfig` gains:
- `execution_lag: int = 1` — bars between signal and fill.
- `rebalance: bool = True` — when a *held* ticker receives a fresh `1` signal
  (prior signal was not `1`), resize the position to its target weight instead of
  ignoring it. This makes `EqualWeight` and periodic strategies meaningful.
- `max_weight: float | None = None` — cap on per-ticker target weight
  (default `1 / n_tickers` equal weight; if `max_weight` is set the target is
  `min(1/n_tickers, max_weight)`).

Trade log columns: `date, ticker, direction, quantity, fill_price, commission, value, cash_after`.
Signals for day *t* are read at bar *t + execution_lag*; if that bar does not exist the
signal is dropped. NAV is still recorded every bar.

### 2. Trade analytics (`backtesting/trades.py`)
- `round_trips(trades: DataFrame) -> DataFrame` pairs buys with subsequent sells
  per ticker (FIFO). Columns: `ticker, entry_date, exit_date, quantity, entry_price,
  exit_price, pnl, return_pct, holding_days, commission`. Open positions at end
  are excluded from round trips.
- `trade_statistics(round_trips) -> dict`: `n_trades, n_wins, n_losses, win_rate,
  avg_win, avg_loss, profit_factor, expectancy, avg_holding_days, best_trade,
  worst_trade, total_pnl, total_commission, max_consecutive_wins, max_consecutive_losses`.

### 3. Metrics (`backtesting/metrics.py`)
`compute_metrics(nav, benchmark=None, risk_free_rate=0.0)` adds:
`sortino, calmar, skew, kurtosis, best_day, worst_day, positive_days_pct, n_days`.
Existing keys are kept.

### 4. Significance (`evaluation/significance.py`)
```python
@dataclass
class SignificanceResult:
    observed_sharpe: float
    observed_cagr: float
    bootstrap_sharpe: np.ndarray     # distribution
    bootstrap_cagr: np.ndarray
    sharpe_ci_95: tuple[float, float]
    cagr_ci_95: tuple[float, float]
    permutation_sharpe: np.ndarray   # Sharpe of shuffled-return series
    p_value_sharpe: float            # P(perm_sharpe >= observed)
    prob_sharpe_ratio: float         # PSR vs. benchmark Sharpe 0
    t_stat: float                    # mean daily return / se
    p_value_t: float                 # two-sided
    n_samples: int

def analyse(returns: pd.Series, n_samples=1000, block=20, seed=0) -> SignificanceResult
```
Deterministic via `numpy.random.default_rng(seed)`. The permutation test shuffles
daily returns, which destroys the timing information of the strategy while keeping
the marginal distribution; a positive Sharpe that survives is due to sequencing,
not to the return distribution alone. Bootstrap CI answers "how uncertain is the
estimate"; PSR answers "how likely is the true Sharpe > 0 given skew and kurtosis".

### 5. Serialization (`evaluation/serialize.py`)
`report_to_dict(report: BacktestReport, prices: DataFrame | None, meta: dict) -> dict`
with keys: `meta` (run_id, strategy, params, tickers, start, end, config, created_at),
`metrics`, `risk` (var/cvar), `trade_stats`, `significance`, `series`
(`dates`, `nav`, `benchmark`, `drawdown`, `returns`), `prices`
(`{ticker: [..]}` aligned to `dates`), `trades` (list of dicts, dates ISO),
`round_trips`, `monthly_returns` (list of `{year, month, ret}`), `recovery_periods`.
All numbers are plain floats; NaN -> `null`. This dict is the single contract
consumed by `report.js`, `RunStore`, and `HTMLReporter`.

### 6. Web (`web/`)
- `create_app(store: RunStore) -> FastAPI` with routes:
  - `GET /` -> `index.html`; `/static/*` served by StaticFiles.
  - `GET /api/strategies` -> `[{name, params: [{name, type, default}]}]` from the registry.
  - `GET /api/runs` -> list of `meta` blocks, newest first.
  - `GET /api/runs/{run_id}` -> full run dict; 404 if missing.
  - `DELETE /api/runs/{run_id}`.
  - `POST /api/backtest` body: `{strategy, params, tickers, start, end, initial_capital,
    commission, slippage_bps, data_source, benchmark, execution_lag, significance}` ->
    runs synchronously, saves, returns full run dict. Errors -> 400 with message.
- `RunStore(root)` — `save(run_dict) -> run_id`, `load(run_id)`, `list()`, `delete(run_id)`.
  `run_id = <YYYYMMDD-HHMMSS>-<strategy>-<6 hex>`.
- `registry.py` — `strategy_specs()` built by introspecting each strategy's
  `__init__` signature (name, type, default); `build(name, params)`.
- Frontend (`report.js`) renders: metric tiles; price chart per ticker with buy /
  sell markers; NAV vs benchmark with trade markers; drawdown area; monthly-returns
  heatmap; daily-return histogram; significance panel (bootstrap Sharpe histogram
  with observed line and 95% CI band, permutation histogram, p-value, PSR, t-stat);
  trade statistics table; round-trip table; recovery periods table. Charts use one
  consistent palette and work in light and dark themes.

### 7. HTML report (`evaluation/html_reporter.py`)
`HTMLReporter().write(run_dict, output_dir) -> Path` inlines `report.js`, `style.css`
and the JSON payload into one `report.html`; Plotly from CDN. `Pipeline.report()`
writes both markdown and HTML.

### 8. Pipeline (`pipeline/pipeline.py`)
New constructor args: `benchmark: str | None`, `execution_lag: int = 1`,
`significance: bool = True`, `risk_free_rate: float = 0.0`, `rebalance: bool = True`.
Benchmark prices are fetched with the same data source and passed to `BacktestResult`.
`to_dict()` returns the serialized run. `report()` writes markdown + HTML.

## Error handling
- Unknown strategy / bad params -> `ValueError` in registry -> HTTP 400.
- Data fetch failure (network, LSEG) -> `RuntimeError` -> HTTP 502 with message.
- Empty trades -> trade stats all zero / null; significance still computed on NAV returns.
- Fewer than 30 return observations -> significance skipped, `significance: null`.

## Testing
- Engine: execution lag shifts fill date by one bar; rebalance resizes position;
  legacy `execution_lag=0` still passes existing tests.
- Trades: FIFO pairing on a hand-built log; statistics on known values.
- Significance: deterministic seed; constant-positive returns -> p-value 0; shuffled
  distributions have the right length; CI contains observed for iid normal returns.
- Serialize: output is `json.dumps`-able; NaN handling; dates ISO.
- Web: TestClient for every route, with a stub strategy and patched `fetch_prices`.
- HTML reporter: file exists, contains payload, contains `renderReport`.

## Out of scope
Live trading, authentication, multi-user, databases, options, ML signals.
