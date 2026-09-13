# Trading Algorithm Testing System — Design Spec
**Date:** 2026-09-13

## Goal
A full, importable system for testing trading algorithms comprising four subsystems:
1. **LSEG DataFeed** — historical OHLCV, fundamentals, index constituents via LSEG Workspace API
2. **BacktestEngine** — simulated trading loop over historical data
3. **Execution Layer** — order/fill simulation with slippage and commission
4. **Evaluation & Reporting** — risk-adjusted metrics + markdown report output

Entry point: a `Pipeline` class composable in Python notebooks or scripts.

---

## Architecture

```
portfolio-sim/
├── data/
│   └── lseg.py              # LSEGDataFeed class
├── backtesting/
│   └── engine.py            # BacktestEngine.run() — implement stub
├── execution/
│   ├── __init__.py
│   ├── order.py             # Order + Fill dataclasses
│   └── fill.py              # FillSimulator (slippage + commission)
├── evaluation/
│   ├── __init__.py
│   ├── evaluator.py         # Evaluator → BacktestReport
│   └── reporter.py          # MarkdownReporter → .md + .png files
├── pipeline/
│   ├── __init__.py
│   └── pipeline.py          # Pipeline class (public API)
└── scripts/
    └── run_pipeline.py      # CLI wrapper
```

**Data flow:**
```
Pipeline.run()
  1. LSEGDataFeed.fetch_prices() + fetch_fundamentals() → DataBundle
  2. Strategy.generate_signals(prices) → signal Series per date
  3. BacktestEngine.run(signals, prices, portfolio, fill_simulator)
       → FillSimulator.execute(order, price) → Fill
       → Portfolio.buy()/sell()
       → portfolio.record_nav()
  4. Evaluator.evaluate(BacktestResult) → BacktestReport
  5. MarkdownReporter.write(report, output_path) → report.md + charts
```

---

## Subsystem Specs

### 1. LSEG DataFeed (`data/lseg.py`)

```python
class LSEGDataFeed:
    def fetch_prices(tickers, start, end, frequency="daily") -> pd.DataFrame
    def fetch_fundamentals(tickers) -> dict[str, dict]
    def fetch_index_constituents(index_ric) -> list[str]
```

- Uses `lseg.data` (`ld`) library; `ld.open_session()` called lazily on first use
- Close price: tries `TRDPRC_1` first, falls back to `OFF_CLOSE` (known LSEG quirk for Norwegian listings)
- Results cached to `data/cache/lseg/` as parquet (same pattern as yfinance loader)
- Falls back to yfinance if LSEG session unavailable (`data_source="yfinance"` in Pipeline)
- Fundamentals fields: `P/E`, `EPS`, `BV/SH`, `MKT_CAP`, `DPS_CURR_YR`

### 2. BacktestEngine (`backtesting/engine.py`)

Implements the stub `run()` method. Iterates date-by-date over the trading calendar:

```
for date in dates:
    signals = strategy.generate_signals(prices.loc[:date])
    for ticker, signal in signals.items():
        if signal changes from prior:
            order = Order(ticker, signal, date, quantity)
            fill = fill_simulator.execute(order, prices.loc[date])
            portfolio.buy() or sell()
    portfolio.record_nav(date, prices.loc[date])
```

- Position sizing: equal-weight by default (configurable)
- Quantity: `floor(available_cash * weight / fill_price)`
- Returns `BacktestResult` (existing dataclass in `metrics.py`)

### 3. Execution Layer (`execution/`)

**`Order`** dataclass: `ticker`, `direction: int {-1,0,1}`, `quantity: float`, `timestamp: pd.Timestamp`

**`Fill`** dataclass: `order: Order`, `fill_price: float`, `commission: float`, `net_cost: float`

**`FillSimulator`**:
- Slippage: `fill_price = close * (1 + direction * slippage_bps / 10_000)`
- Commission: `max(min_commission, fill_price * quantity * commission_rate)`
- Stateless — pure function `execute(order, close_price) -> Fill`

### 4. Evaluation (`evaluation/`)

**`BacktestReport`** dataclass:
- `result: BacktestResult`
- `metrics: dict` — from `backtesting/metrics.compute_metrics()`
- `var_95: float`, `var_99: float`, `cvar_95: float`
- `drawdown_series: pd.Series`
- `recovery_periods: list[RecoveryPeriod]`
- `correlation_matrix: pd.DataFrame | None`

**`Evaluator.evaluate(result, benchmark=None) -> BacktestReport`**
- Calls `compute_metrics()`, `value_at_risk()`, `conditional_var()`, `drawdown_series()`, `recovery_periods()`

**`MarkdownReporter.write(report, output_dir) -> Path`**
- Writes `report.md` with sections: Strategy Summary, Performance, Risk, Drawdown, Trade Log
- Saves `nav_curve.png`, `drawdown.png`, `returns_dist.png` alongside using existing `visualization/`

### 5. Pipeline API (`pipeline/pipeline.py`)

```python
p = Pipeline(
    strategy=MomentumStrategy(lookback=60, top_n=5),
    tickers=["EQNR.OL", "DNB.OL"],
    start="2018-01-01",
    end="2024-12-31",
    data_source="lseg",        # or "yfinance"
    initial_capital=1_000_000,
    commission=0.001,
    slippage_bps=5,
)
result = p.run()               # → BacktestResult
report = p.evaluate()          # → BacktestReport
p.report(output="reports/")   # → writes files, returns Pipeline (chainable)
```

---

## Testing
- `tests/test_lseg_feed.py` — mock LSEG session, test price normalisation and caching
- `tests/test_engine.py` — synthetic prices, verify NAV evolves correctly, trades fire at right dates
- `tests/test_execution.py` — verify slippage math, commission floor
- `tests/test_evaluator.py` — known return series → verify VaR and Sharpe values
- `tests/test_pipeline.py` — end-to-end with yfinance + mock strategy

## Constraints
- LSEG Workspace must be running; `LSEGDataFeed` raises `RuntimeError` with clear message if session fails
- All dates UTC internally; display layer localises to Europe/Oslo
- Monetary values float (NOK or USD per existing convention)
- Signals remain `{-1, 0, 1}` per existing strategy contract
