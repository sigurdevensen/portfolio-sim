# Quant Trading Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the backtest engine, add statistical-significance analysis, and ship a FastAPI + Plotly.js website (plus self-contained HTML reports) for viewing backtest performance.

**Architecture:** The engine gains next-bar execution and rebalancing; a new `trades.py` derives round-trip statistics; `evaluation/significance.py` produces bootstrap / permutation distributions; `evaluation/serialize.py` turns a `BacktestReport` into one JSON contract consumed by both the web UI (`web/static/report.js`) and the standalone `HTMLReporter`. `web/app.py` (FastAPI) exposes runs stored as JSON by `RunStore`.

**Tech Stack:** Python 3.11, pandas, numpy, scipy, FastAPI, uvicorn, Plotly.js (CDN), pytest.

Spec: `docs/superpowers/specs/2026-09-13-quant-platform-design.md`

---

## File Map

**Create**
- `backtesting/trades.py` — `round_trips()`, `trade_statistics()`
- `evaluation/significance.py` — `SignificanceResult`, `analyse()`
- `evaluation/serialize.py` — `report_to_dict()`, `_clean()` (NaN -> None)
- `evaluation/html_reporter.py` — `HTMLReporter`
- `web/__init__.py`, `web/app.py`, `web/store.py`, `web/registry.py`
- `web/static/index.html`, `web/static/app.js`, `web/static/report.js`, `web/static/style.css`
- `scripts/serve.py`
- `tests/test_trades.py`, `tests/test_significance.py`, `tests/test_serialize.py`, `tests/test_web.py`, `tests/test_html_reporter.py`, `tests/test_registry.py`

**Modify**
- `backtesting/engine.py` — `execution_lag`, `rebalance`, `max_weight`, richer trade log
- `backtesting/metrics.py` — extra metrics, `risk_free_rate`
- `evaluation/evaluator.py` — new report fields
- `evaluation/reporter.py` — trade stats + significance sections
- `pipeline/pipeline.py` — benchmark, lag, `to_dict()`, HTML output
- `scripts/run_pipeline.py` — new flags
- `requirements.txt`, `pyproject.toml`, `README.md`, `CLAUDE.md`
- `tests/test_engine.py`, `tests/test_metrics.py`, `tests/test_pipeline.py`

---

### Task 1: Richer metrics
**Files:** Modify `backtesting/metrics.py`; Test `tests/test_metrics.py`

- [x] Tests: `sortino` > 0 for positive drift; `calmar` = cagr / |max_dd|; `positive_days_pct` in [0,1]; `n_days` equals len(returns); `skew`/`kurtosis` present; `risk_free_rate` lowers Sharpe.
- [x] Implement `_sortino`, `_calmar`, add keys; thread `risk_free_rate` through `compute_metrics` and `BacktestResult` (new field `risk_free_rate: float = 0.0`).
- [x] Run `pytest tests/test_metrics.py -q`, commit `feat(metrics): add sortino, calmar, distribution stats`.

### Task 2: Trade analytics
**Files:** Create `backtesting/trades.py`; Test `tests/test_trades.py`

- [x] Tests: hand-built log (buy 10 @100, sell 10 @110 => pnl 100 minus commission, return 10%, holding days); partial sells split FIFO; open position excluded; empty log => empty frame and zero stats; statistics on 3 known trades (2 wins 1 loss) check win_rate 2/3, profit_factor, expectancy, consecutive counts.
- [x] Implement `round_trips(trades)` (FIFO deque per ticker) and `trade_statistics(rt)`.
- [x] Commit `feat(trades): round-trip pairing and trade statistics`.

### Task 3: Engine — execution lag, rebalance, trade log
**Files:** Modify `backtesting/engine.py`; Test `tests/test_engine.py`

- [x] Tests: with `execution_lag=1` first fill date is second bar; `execution_lag=0` first fill on first bar; rebalance test: strategy emits 1 on bar 0, 0 on bar 1, 1 on bar 2 with rising price for ticker AAA and flat BBB => AAA shares reduced on rebalance; `rebalance=False` leaves shares unchanged; trade log has `value` and `cash_after` columns; existing tests still pass (update `_config` to use `execution_lag=0` where they rely on same-bar fills).
- [x] Implement: shift signal frame by `execution_lag` (`signals_df.shift(lag)` filled with 0), target weight `min(1/n, max_weight)`, rebalance branch (buy/sell delta shares), extended fill log.
- [x] Commit `feat(engine): next-bar execution, rebalance-to-target, richer trade log`.

### Task 4: Significance analysis
**Files:** Create `evaluation/significance.py`; Test `tests/test_significance.py`

- [x] Tests: deterministic (same seed => same arrays); lengths == n_samples; CI lower <= observed <= upper for iid normal returns with n=1000 bootstrap 300; strongly positive drift => p_value_sharpe < 0.05 and PSR > 0.95; zero-mean noise => PSR near 0.5 (0.2..0.8); `analyse` raises `ValueError` for < 30 obs; `to_dict()` json-serialisable with histogram bins.
- [x] Implement stationary bootstrap (geometric block lengths, mean `block`), permutation via `rng.permutation`, PSR formula: `Phi( (SR - SR*) * sqrt(n-1) / sqrt(1 - g3*SR + (g4-1)/4 * SR^2) )` using per-period SR; t-test via `scipy.stats.ttest_1samp`.
- [x] Commit `feat(evaluation): bootstrap/permutation significance analysis`.

### Task 5: Evaluator + serializer
**Files:** Modify `evaluation/evaluator.py`; Create `evaluation/serialize.py`; Test `tests/test_evaluator.py`, `tests/test_serialize.py`

- [x] Tests (evaluator): report has `round_trips`, `trade_stats`, `significance` (None when disabled), `monthly_returns` DataFrame.
- [x] Tests (serialize): `json.dumps(report_to_dict(...))` works; NaN -> None; `series.dates` ISO strings same length as `nav`; `prices` aligned; `trades` dates ISO; `meta` passthrough.
- [x] Implement `Evaluator.evaluate(..., significance=True, n_samples=1000)`; `report_to_dict(report, prices, meta)`.
- [x] Commit `feat(evaluation): trade stats, significance and JSON serialisation in reports`.

### Task 6: Markdown reporter sections
**Files:** Modify `evaluation/reporter.py`; Test `tests/test_evaluator.py`

- [x] Test: report.md contains "Trade Statistics" and "Statistical Significance" headings when data present.
- [x] Implement sections (win rate, profit factor, expectancy; Sharpe CI, p-value, PSR).
- [x] Commit `feat(reporter): trade statistics and significance sections`.

### Task 7: Frontend renderer + HTML reporter
**Files:** Create `web/static/report.js`, `web/static/style.css`, `evaluation/html_reporter.py`; Test `tests/test_html_reporter.py`

- [x] Test: `HTMLReporter().write(run_dict, tmp_path)` returns `report.html` that exists, contains `renderReport`, contains `"nav"` payload key and Plotly CDN script tag.
- [x] Implement `report.js` (`window.renderReport(el, data)`): tiles, price+markers, NAV+markers, drawdown, monthly heatmap, returns histogram, significance panel, tables. `style.css` with light/dark tokens. `HTMLReporter` reads the two static files and inlines JSON via `<script id="run-data" type="application/json">`.
- [x] Commit `feat(report): interactive self-contained HTML report`.

### Task 8: Registry + RunStore
**Files:** Create `web/__init__.py`, `web/registry.py`, `web/store.py`; Test `tests/test_registry.py`, `tests/test_web.py`

- [x] Tests: `strategy_specs()` includes momentum with params lookback(int,252) and top_n(int,3); `build("momentum", {"lookback": 20})` returns Momentum with lookback 20; unknown name raises ValueError; bad param raises ValueError. RunStore: save returns id, load round-trips, list newest first, delete removes, load missing raises `KeyError`.
- [x] Implement.
- [x] Commit `feat(web): strategy registry and JSON run store`.

### Task 9: Pipeline upgrades
**Files:** Modify `pipeline/pipeline.py`, `scripts/run_pipeline.py`; Test `tests/test_pipeline.py`

- [x] Tests: `benchmark="SPY"` fetches SPY and metrics contain `beta`; `to_dict()` json-serialisable with `meta.strategy`; `report()` writes `report.html`; `execution_lag` passed to config.
- [x] Implement; add CLI flags `--benchmark`, `--execution-lag`, `--no-significance`, `--rebalance/--no-rebalance`.
- [x] Commit `feat(pipeline): benchmark, execution lag, HTML report, to_dict`.

### Task 10: FastAPI app + index page
**Files:** Create `web/app.py`, `web/static/index.html`, `web/static/app.js`, `scripts/serve.py`; Test `tests/test_web.py`

- [x] Tests (TestClient, patched `data.loader.fetch_prices`): `GET /` 200 html; `GET /api/strategies` lists momentum; `POST /api/backtest` with buy_and_hold returns 200 with `meta.run_id` and `series.nav`; `GET /api/runs` lists it; `GET /api/runs/{id}` returns it; `GET /api/runs/nope` 404; `DELETE` then 404; bad strategy 400.
- [x] Implement app factory, pydantic `BacktestRequest`, routes; `index.html` with form (populated from `/api/strategies`), run list sidebar, report container; `app.js` wiring; `scripts/serve.py` calling `uvicorn.run`.
- [x] Commit `feat(web): FastAPI platform with run form and report viewer`.

### Task 11: Docs, deps, smoke run
**Files:** Modify `requirements.txt`, `pyproject.toml`, `README.md`, `CLAUDE.md`

- [x] Add fastapi, uvicorn; document `python scripts/serve.py`; update layout tree and conventions (execution lag default, run JSON contract).
- [x] Smoke: run `python scripts/run_pipeline.py --strategy momentum --tickers AAPL MSFT --start 2022-01-01 --end 2023-12-31 --output reports/smoke` using cached data if available; open `report.html` exists.
- [x] Full `pytest tests/ -q` green; commit `docs: platform usage and architecture`.
