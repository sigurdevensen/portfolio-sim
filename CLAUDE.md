# portfolio-sim

Investment portfolio simulation system covering data ingestion, backtesting, risk analysis, and strategy testing.

## Tech Stack

- **Python 3.11+** — primary language
- **pandas / numpy** — data manipulation and numerical computation
- **yfinance** — market data fetching
- **matplotlib / plotly** — visualization
- **pytest** — testing

## Project Layout

```
portfolio-sim/
├── data/
│   ├── raw/            # unmodified downloaded data
│   ├── processed/      # cleaned, normalised data
│   └── cache/          # cached API responses (gitignored)
├── backtesting/        # core simulation engine
│   ├── engine.py       # main backtest loop
│   ├── portfolio.py    # portfolio state (positions, cash, NAV)
│   └── metrics.py      # Sharpe, CAGR, drawdown, alpha, beta
├── risk/               # risk analysis
│   ├── var.py          # Value at Risk (historical, parametric, Monte Carlo)
│   ├── drawdown.py     # drawdown series, max drawdown, recovery time
│   └── correlation.py  # rolling correlations, heatmaps
├── strategies/         # strategy implementations
│   ├── base.py         # abstract Strategy class with generate_signals()
│   ├── buy_and_hold.py
│   ├── momentum.py
│   ├── mean_reversion.py
│   └── equal_weight.py
├── optimization/       # portfolio optimisation
│   ├── efficient_frontier.py
│   └── rebalancing.py
├── visualization/      # chart builders
│   ├── performance.py  # NAV curves, benchmark comparison
│   ├── risk.py         # VaR cones, drawdown plots
│   └── comparison.py   # multi-strategy comparison
├── scripts/            # runnable entry points
│   ├── fetch_data.py
│   ├── run_backtest.py
│   └── run_analysis.py
└── tests/              # pytest test suite
```

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Fetch market data for a ticker list
python scripts/fetch_data.py --tickers AAPL MSFT SPY --start 2015-01-01

# Run a backtest
python scripts/run_backtest.py --strategy momentum --start 2018-01-01 --end 2024-12-31

# Run risk analysis on a portfolio
python scripts/run_analysis.py --portfolio examples/sample_portfolio.json

# Run tests
pytest tests/
```

## Conventions

- All strategy classes inherit from `strategies/base.py:Strategy` and implement `generate_signals(data) -> pd.Series`.
- Backtest results are returned as `BacktestResult` dataclasses — never raw dicts.
- Data paths are resolved relative to the project root using `pathlib`. Never hardcode absolute paths.
- Risk metrics always operate on return series (not price series) as input.
- Dates are always timezone-aware (`UTC`) internally; localise only at the output layer.
- Monetary values are stored as `float` (USD); no currency conversion layer at this time.

## Adding a New Strategy

1. Create `strategies/<name>.py` subclassing `Strategy`.
2. Implement `generate_signals(data)` returning a `pd.Series` of `{-1, 0, 1}`.
3. Register it in `strategies/__init__.py`.
4. Add at least one test in `tests/test_strategies.py`.

## Data Sources

- **yfinance** — equities, ETFs, crypto (default)
- CSV drops go in `data/raw/` and are loaded via `data/loader.py`.

## Not In Scope (yet)

- Live trading / brokerage API integration
- Options / derivatives pricing
- Machine learning signal generation
- Multi-currency portfolios
