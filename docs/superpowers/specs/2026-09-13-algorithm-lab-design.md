# Algorithm Lab — Design Spec
**Date:** 2026-09-13
**Status:** Decided autonomously under the `/goal` directive. Assumptions listed explicitly.

## Goal
Test hundreds of trading algorithms simultaneously on the same market data and
decide, with explicit multiple-testing mathematics, which of them have a genuine
edge. Ship a library of 100+ distinct algorithms (different data types, optional
stop-loss), a batch runner, an overfitting-aware evaluation, a CLI, and a web view.

## The overfitting problem, stated
If N algorithms are backtested and the best is reported, its Sharpe is inflated by
selection: even pure noise yields an expected maximum Sharpe that grows like
`sqrt(2 ln N)`. Any single-strategy p-value is meaningless after selection. The lab
therefore never reports a strategy's statistics in isolation; every number is
conditioned on how many trials were run and on out-of-sample confirmation.

## Assumptions
- **Parameters are fixed a priori** in the library. Nothing is optimised on the data.
  All statistics derive from one full-period backtest per algorithm, i.e. a
  `T x N` matrix of daily strategy returns `R`. Selection bias (choosing the best of
  N) is the only overfitting channel and is what the mathematics addresses.
- **Data:** yfinance daily OHLCV (open, high, low, close, volume), adjusted. Cached in
  `data/cache/`. When only closes exist, `MarketData.from_close()` synthesises the
  other fields so all strategies still run (degraded, flagged).
- **Costs are always on** (commission 0.1 %, slippage 5 bps, next-bar execution).
  Costs are the first line of defence against noise-fitting.
- **Stops are close-to-close:** a stop-loss / take-profit / trailing-stop is checked
  against the bar close and filled at that close with slippage. Intraday lows are
  not used (conservative on gaps, optimistic within the bar; documented).
- **In-sample / out-of-sample:** the first 60 % of trading days is IS, the last 40 %
  OOS. Selection happens on IS only; OOS is reported untouched.
- **Parallelism:** `concurrent.futures.ProcessPoolExecutor`; `n_jobs=1` in tests.

## Mathematics used to decide edge (`research/edge.py`)
All on the daily return matrix `R` (T days x N algorithms), annualised with 252.

1. **Per-algorithm evidence** — t-statistic of mean daily return, sign-flip p-value,
   Probabilistic Sharpe Ratio (from `evaluation/significance.py`), on IS, OOS, and full.
2. **False-discovery control** — Benjamini–Hochberg adjusted p-values (`p_fdr`) and
   Holm step-down (`p_holm`) over the N full-sample p-values.
3. **Deflated Sharpe Ratio (Bailey & López de Prado 2014)** — expected maximum Sharpe
   under the null for N independent trials,
   `E[max SR] = sqrt(V[SR]) * ((1-γ) Φ⁻¹(1-1/N) + γ Φ⁻¹(1-1/(N e)))`, γ = 0.5772,
   with `V[SR]` the cross-sectional variance of the N (per-period) Sharpes. DSR is the
   PSR of each strategy evaluated against `E[max SR]` instead of 0.
4. **White's Reality Check (2000)** — stationary bootstrap of time indices applied
   jointly to all N series (preserving cross-strategy dependence). For each sample,
   the max over N of the centred mean return gives the null distribution of the best
   strategy's performance. `p_rc = P(max_boot >= max_observed)`. Also reported per
   strategy as `p_rc_i = P(max_boot >= observed_i)` (step-down not implemented).
5. **Probability of Backtest Overfitting via CSCV (Bailey, Borwein, López de Prado,
   Zhu 2017)** — split T into S=16 contiguous blocks; for every combination of S/2
   blocks as IS (12 870 combos), pick the IS-best algorithm, find its OOS rank among N,
   compute logit `λ = ln(rank/(N-rank))`. `PBO = P(λ <= 0)`. Vectorised via per-block
   sums of `r` and `r²`.
6. **Block stability** — Sharpe on K=5 contiguous blocks; `stability = share of blocks
   with positive mean return`; `worst_block_sharpe`.
7. **Minimum track record length** (Bailey & López de Prado 2012) — days needed for
   PSR ≥ 0.95 given observed skew/kurtosis: `MinTRL`.

**Edge verdict** (`edge` column, one of `strong`, `candidate`, `none`):
- `strong`: `p_fdr < 0.05` AND `DSR > 0.95` AND `OOS Sharpe > 0` AND `stability >= 0.6`
  AND `n_trades >= 20`.
- `candidate`: `p_fdr < 0.10` AND `OOS Sharpe > 0` AND `n_trades >= 20`.
- `none`: otherwise.
The batch also carries a global verdict: `reality_check_p`, `pbo`, and
`expected_max_sharpe` — if `PBO > 0.5` or `p_rc > 0.05` the batch as a whole is
flagged as "best result is consistent with luck".

## Architecture

```
data/market.py            MarketData(open, high, low, close, volume) + fetch_market_data(), from_close()
strategies/base.py        Strategy gains stop_loss/take_profit/trailing_stop, requires, generate_signals_market()
strategies/technical.py   SMA/EMA cross, price-vs-SMA, MACD, RSI, Bollinger, Keltner, Stochastic, ROC, Donchian, ATR breakout
strategies/volume.py      volume-confirmed breakout, OBV trend, volume z-score reversal
strategies/cross_sectional.py  low-volatility, dual momentum, relative strength vs universe, 52-week high, TS momentum
strategies/calendar.py    turn-of-month, day-of-week, sell-in-May
strategies/regime.py      volatility regime, buy-the-dip, streak reversal, gap reversal
strategies/random_control.py  RandomSignal(seed, p) — noise controls
backtesting/engine.py     market-aware signals, stop handling, `reason` column in trade log
research/library.py       AlgoSpec + ALGORITHMS (>= 100, unique names), build_algorithm()
research/edge.py          the mathematics above
research/batch.py         run_batch(specs, market, config, n_jobs) -> BatchResult (returns, leaderboard, edge summary)
research/report.py        batch_to_dict() JSON contract + BatchStore under reports/batches/
scripts/run_batch.py      CLI
web/app.py                POST /api/batch, GET /api/batches, GET /api/batches/{id}
web/static/batch.js       leaderboard, IS-vs-OOS scatter, Sharpe histogram vs E[max SR], PBO tile
web/static/index.html     "Backtest" / "Algorithm lab" tabs
```

### Data flow
```
fetch_market_data() -> MarketData
   for spec in ALGORITHMS (parallel):  engine.run(build(spec), market) -> nav, trades
R = daily returns (T x N)  ->  edge.assess(R, is_mask, n_trades) -> leaderboard + globals
batch_to_dict() -> reports/batches/<id>/batch.json (+ batch.html) -> web
```

### Engine changes
- `run(strategy, prices, benchmark=None, market=None)`: if `market` is given, signals
  come from `strategy.generate_signals_market(market)`; base implementation delegates
  to `generate_signals(market.close)`.
- Stops: per held position track `entry_price` (avg cost) and `peak_price`. On each bar,
  before signal processing: exit if `close <= entry*(1-stop_loss)`, or
  `close >= entry*(1+take_profit)`, or `close <= peak*(1-trailing_stop)`. Log with
  `reason`. Re-entry requires the signal to leave `1` and return to `1`.
- Trade log gains `reason` in {`signal`, `rebalance`, `stop_loss`, `take_profit`, `trailing_stop`}.

### Library composition (target ≥ 100 distinct algorithms)
About 25 families, each instantiated with 3–6 a-priori parameter sets chosen from
textbook defaults (e.g. SMA 20/50, 50/200; RSI 14 with 30/70; Bollinger 20, 2σ),
and a subset repeated with a 10 % stop-loss or 15 % trailing stop. Plus 5 random
controls (different seeds) and buy-and-hold / equal-weight baselines. Names are
deterministic, e.g. `sma_cross_20_50`, `sma_cross_20_50_sl10`, `random_seed3`.

## Web
- Tabs: **Backtest** (existing) and **Algorithm lab**.
- Lab form: tickers, dates, universe presets, n_samples, family filter, run.
- Lab view: global verdict tiles (N tested, E[max SR], Reality Check p, PBO, # strong,
  # candidates); scatter IS Sharpe vs OOS Sharpe coloured by verdict (the overfitting
  picture); histogram of full-sample Sharpes with `E[max SR]` line; sortable
  leaderboard; click a row to run/open that algorithm's full single report.

## Testing
- Market data: `from_close()` shapes; cache round trip with patched yfinance.
- Engine: stop-loss fires at the right bar with reason; trailing stop; take profit;
  no immediate re-entry; market-aware strategy receives volume.
- Each family: signals in {-1,0,1}, aligned shape, and at least one deterministic
  behavioural check (e.g. SMA cross goes long after fast > slow).
- Library: >= 100 specs, unique names, all buildable, all run on synthetic data.
- Edge math: BH on known p-values; E[max SR] grows with N; DSR of noise < 0.95; Reality
  Check p on pure-noise batch > 0.05 and on a planted-edge batch < 0.05; PBO of noise
  ≈ 0.5 (0.3–0.7), PBO of a batch where one strategy dominates < 0.2; MinTRL formula.
- Batch: synthetic market, 6 specs, n_jobs=1, leaderboard columns and verdict present;
  n_jobs=2 smoke.
- Web: POST /api/batch on synthetic data (patched fetch), list, get, 404.

## Out of scope
Parameter optimisation, walk-forward re-fitting, intraday data, portfolio-of-strategies
construction, live trading.
