# Algorithm Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Batch-test 100+ fixed-parameter algorithms on shared OHLCV data and rank them with multiple-testing-aware edge statistics (FDR, Deflated Sharpe, Reality Check, PBO), exposed via CLI and the web platform.

**Architecture:** `MarketData` carries OHLCV; strategies opt into extra fields via `generate_signals_market()`; the engine handles stops. `research/library.py` enumerates algorithms, `research/batch.py` runs them (process pool) into a T×N return matrix, `research/edge.py` computes the statistics, `research/report.py` serialises. Web gets a lab tab.

**Tech Stack:** Python 3.11, pandas, numpy, scipy, FastAPI, Plotly.js, pytest.

Spec: `docs/superpowers/specs/2026-09-13-algorithm-lab-design.md`

---

### Task 1: MarketData
- [ ] Tests `tests/test_market.py`: `from_close` fields aligned, volume NaN-free; `slice`; `fetch_market_data` with patched `yf.download` MultiIndex → correct fields; cache round trip.
- [ ] Implement `data/market.py`. Commit.

### Task 2: Strategy base + engine stops
- [ ] Tests `tests/test_engine.py`: stop-loss exits with reason at first breach bar; take-profit; trailing stop; no re-entry while signal stays 1; market-aware strategy gets volume; `reason` column present.
- [ ] Implement `strategies/base.py` (attrs + `generate_signals_market`), engine stop logic, `reason` logging. Commit.

### Task 3: Strategy families
- [ ] Tests `tests/test_families.py`: parametrised over every family: output in {-1,0,1}, shape matches; behavioural checks for SMA cross, RSI, Donchian, volume breakout, turn-of-month, random control.
- [ ] Implement `strategies/technical.py`, `volume.py`, `cross_sectional.py`, `calendar.py`, `regime.py`, `random_control.py`; vectorise `Momentum`; export in `strategies/__init__.py`; register in `web/registry.py`. Commit.

### Task 4: Algorithm library
- [ ] Tests `tests/test_library.py`: `len(ALGORITHMS) >= 100`; unique names; every spec builds; every spec runs on 300-day synthetic market without error.
- [ ] Implement `research/library.py`. Commit.

### Task 5: Edge mathematics
- [ ] Tests `tests/test_edge.py`: BH/Holm on known p; `expected_max_sharpe` increasing in N; DSR of noise < 0.95 for most; `reality_check` p > 0.05 on noise, < 0.05 with planted edge; `pbo_cscv` on noise in (0.3, 0.7), dominated batch < 0.2; `block_stability`; `min_track_record_length` sanity; `assess` returns leaderboard columns and verdicts.
- [ ] Implement `research/edge.py`. Commit.

### Task 6: Batch runner + serialisation
- [ ] Tests `tests/test_batch.py`: 6 specs on synthetic market, n_jobs=1 → `BatchResult.returns` shape (T,6), leaderboard rows 6, columns present, globals present; failing spec recorded with error; n_jobs=2 smoke; `batch_to_dict` JSON-safe; `BatchStore` save/load/list.
- [ ] Implement `research/batch.py`, `research/report.py`. Commit.

### Task 7: CLI
- [ ] `scripts/run_batch.py` with `--tickers --start --end --families --limit --n-jobs --output`; smoke on cached data. Commit.

### Task 8: Web lab
- [ ] Tests `tests/test_web.py`: POST `/api/batch` (patched market fetch, limit 6, n_jobs 1) → batch dict; GET list / get / 404; `/batches/{id}/report.html`.
- [ ] Implement API, `batch.js`, `batch_html`, tabs in `index.html`, wiring in `app.js`. Screenshot check. Commit.

### Task 9: Docs
- [ ] README + CLAUDE.md sections: lab usage, the mathematics, how to add a family. Full test run. Commit.
