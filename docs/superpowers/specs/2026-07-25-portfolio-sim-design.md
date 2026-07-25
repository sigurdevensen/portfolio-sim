# Portfolio Simulation System — Design Spec

**Date:** 2026-07-25
**Status:** Approved

## Overview

A Python toolkit for simulating investment portfolios. The system covers four concerns as independent, composable layers: data ingestion, strategy signal generation, backtesting, and risk analysis. A lightweight visualization layer sits on top for inspection and comparison. Entry points are CLI scripts for scripted use; modules can also be imported directly for notebook or REPL use.

## Architecture

```
Data Layer        → data/loader.py          (fetch, cache, normalise)
Strategy Layer    → strategies/             (signal generation, one class per strategy)
Backtest Layer    → backtesting/            (simulation loop, portfolio state, metrics)
Risk Layer        → risk/                   (VaR, drawdown, correlation)
Optimisation      → optimization/           (efficient frontier, rebalancing schedule)
Visualisation     → visualization/          (matplotlib charts, no interactivity required)
Entry Points      → scripts/               (CLI wrappers around the above layers)
```

Each layer depends only on layers below it. The strategy layer does not import from the backtest layer. The visualisation layer does not import from the scripts layer.

## Components

### Data (`data/loader.py`)

- `fetch_prices(tickers, start, end, use_cache)` — downloads adjusted-close prices via yfinance, persists to `data/cache/` as Parquet for subsequent runs.
- `load_csv(path, ticker)` — loads a price CSV from `data/raw/`.
- All date indexes are `DatetimeIndex` with UTC timezone.
- Cache is keyed on sorted tickers + date range; invalidated by deleting the cache file.

### Strategies (`strategies/`)

- Abstract base: `Strategy.generate_signals(data: DataFrame) → DataFrame` — same shape as input, values in `{-1, 0, 1}`.
- Implementations: `BuyAndHold`, `EqualWeight` (monthly rebalance), `Momentum` (cross-sectional, configurable lookback + top-N), `MeanReversion` (Z-score threshold).
- Adding a strategy: subclass `Strategy`, implement `generate_signals`, register in `__init__.py`.

### Backtesting (`backtesting/`)

- `BacktestEngine.run(strategy, prices)` — iterates daily, calls `strategy.generate_signals`, executes trades via `Portfolio`, records NAV.
- `Portfolio` — tracks cash, positions (with average cost), computes market value given a price snapshot.
- `BacktestResult` — dataclass holding NAV series, trades DataFrame, and computed metrics dict.
- `BacktestConfig` — start/end dates, initial capital, commission rate, slippage.
- Metrics: CAGR, Sharpe ratio, max drawdown, annualised volatility, total return, alpha, beta, information ratio (last three require benchmark).

### Risk (`risk/`)

- `value_at_risk(returns, confidence, method)` — supports `historical`, `parametric`, `montecarlo`.
- `conditional_var(returns, confidence)` — Expected Shortfall.
- `drawdown_series(nav)`, `max_drawdown(nav)`, `recovery_periods(nav, threshold)`.
- `rolling_correlation(returns, window)`, `correlation_heatmap_data(returns)`.
- All functions operate on return series (not price series) except drawdown helpers which take NAV.

### Optimisation (`optimization/`)

- `EfficientFrontier(returns, n_portfolios)` — Monte Carlo simulation of random weight vectors; exposes `max_sharpe_portfolio()` and `min_volatility_portfolio()`.
- `RebalanceSchedule(frequency)` — generates rebalance date lists; supports D/W/M/Q/Y.

### Visualisation (`visualization/`)

- `plot_nav(nav, benchmark)` — indexed NAV curve.
- `plot_returns_distribution(returns)` — histogram with mean line.
- `plot_drawdown(nav)` — filled drawdown chart.
- `plot_var_cone(returns, horizon, confidence_levels)` — forward VaR projection.
- `plot_correlation_heatmap(corr)` — labelled heatmap.
- `plot_strategy_comparison(nav_dict)` — overlaid normalised NAV curves.
- All functions return `matplotlib.Figure`; caller handles display or file save.

## Data Flow

```
yfinance / CSV
    ↓
data/loader.py  (normalise → UTC DatetimeIndex, adjusted close, Parquet cache)
    ↓
Strategy.generate_signals(prices) → signal DataFrame
    ↓
BacktestEngine.run(strategy, prices) → BacktestResult
    ↓
risk/* functions(result.nav)   → risk metrics
    ↓
visualization/* functions      → matplotlib Figures
```

## Error Handling

- Invalid tickers surface as empty columns (yfinance behaviour); callers should drop NaN columns before passing to strategies.
- Insufficient cash during a backtest raises `ValueError` immediately — no silent partial fills.
- Unknown VaR method raises `ValueError` with a descriptive message.
- No network retry logic in the data layer; failures propagate as yfinance exceptions.

## Testing

- Unit tests in `tests/` using pytest.
- `test_metrics.py` — Sharpe, drawdown, and `compute_metrics` key coverage.
- `test_risk.py` — VaR methods, CVaR > VaR invariant, drawdown bounds.
- `test_strategies.py` — signal shape, value domain `{-1, 0, 1}`.
- Engine integration tests (with synthetic data, no network) to be added when `BacktestEngine.run` is implemented.

## Out of Scope

- Live trading or brokerage API integration
- Options / derivatives pricing
- ML-based signal generation
- Multi-currency support
- Interactive web dashboard (plots are static matplotlib only)
