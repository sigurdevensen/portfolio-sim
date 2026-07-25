# portfolio-sim

Investment portfolio simulation system covering data ingestion, backtesting, risk analysis, and strategy testing.

## Tech Stack

| Library | Purpose |
|---|---|
| Python 3.11+ | Primary language |
| pandas / numpy | Data manipulation and numerical computation |
| scipy | Statistical calculations |
| lseg | Market data fetching |
| matplotlib | Visualisation |
| pytest | Testing |

## Project Layout

```
portfolio-sim/
├── data/
│   ├── raw/                    # unmodified downloaded data
│   ├── processed/              # cleaned, normalised data
│   ├── cache/                  # cached API responses (gitignored)
│   ├── loader.py               # fetch_prices(), load_csv()
│   └── cleaner.py              # fill_na_values() and normalisation
├── backtesting/
│   ├── engine.py               # BacktestEngine + BacktestConfig
│   ├── portfolio.py            # portfolio state (positions, cash, NAV)
│   └── metrics.py              # Sharpe, CAGR, drawdown, alpha, beta
├── risk/
│   ├── var.py                  # Value at Risk (historical, parametric, Monte Carlo)
│   ├── drawdown.py             # drawdown series, max drawdown, recovery time
│   └── correlation.py          # rolling correlations, heatmaps
├── strategies/
│   ├── base.py                 # abstract Strategy class
│   ├── buy_and_hold.py
│   ├── momentum.py
│   ├── mean_reversion.py
│   ├── equal_weight.py
│   └── index_buy_sell_randomly.py  # random-entry Monte Carlo strategy
├── optimization/
│   ├── efficient_frontier.py
│   └── rebalancing.py
├── visualization/
│   ├── performance.py          # NAV curves, benchmark comparison
│   ├── risk.py                 # VaR cones, drawdown plots
│   ├── comparison.py           # multi-strategy comparison
│   └── buy_sell_index_montecarlo.py  # Monte Carlo fan chart
├── scripts/
│   ├── fetch_data.py           # download prices via yfinance
│   ├── run_backtest.py         # run a named strategy and print metrics
│   ├── run_analysis.py         # risk analysis on a portfolio JSON
│   ├── download_osebx.py       # Oslo Stock Exchange index download
│   ├── download_osebx_lseg.py  # OSEBX via LSEG Workspace
│   └── download_stock_price.py # single-ticker price download
└── tests/
    ├── test_metrics.py
    ├── test_risk.py
    └── test_strategies.py
```

## Installation

```bash
git clone https://github.com/sigurev/portfolio-sim.git
cd portfolio-sim
pip install -r requirements.txt
```

## Usage

### Fetch market data

```bash
python scripts/fetch_data.py --tickers AAPL MSFT SPY --start 2015-01-01
```


### Monte Carlo simulation (random buy/sell on an index)

```bash
python visualization/buy_sell_index_montecarlo.py
# Reads data/raw/EQNR_OL_monthly.csv and plots a percentile fan chart over 10 000 runs
```

### Run tests

```bash
pytest tests/
```