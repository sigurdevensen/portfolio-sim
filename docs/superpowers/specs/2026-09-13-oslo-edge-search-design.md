# Oslo Edge Search — Design Spec
**Date:** 2026-09-13
**Status:** Decided autonomously under the `/goal` directive.

## Goal
Search for a trading algorithm with a genuine edge on Oslo Stock Exchange common
stocks, using several data types beyond price. "Genuine" means it passes the lab's
benchmark-relative, multiple-testing-corrected verdict (`research/edge.py`), where the
trial count N includes **every** algorithm tried in the search, not just the last round.

## Method (the anti-data-mining contract)
1. One universe, fixed before any test: 28 OSE large/mid caps with yfinance history
   (`research/universes.py:OSLO`). Start 2010-01-01, end 2024-12-31.
2. One growing library: base 116 algorithms + Oslo/macro/event variants. All are run in
   one batch. A round that adds ideas re-runs the whole batch so DSR / Reality Check /
   FDR see the full N.
3. Benchmark: equal-weight buy-and-hold of the universe, same costs.
4. Costs: 0.1 % commission, 5 bps slippage, next-close execution.
5. Random controls stay in the library.

## New data (`data/market.py`, `research/universes.py`)
- `MarketData.extra: dict[str, pd.Series | pd.DataFrame]` — external series aligned to
  the trading index (reindex + forward-fill), e.g. `brent`, `wti`, `usdnok`, `eurnok`,
  `vix`, `spx`, `us10y`, `gold`, `copper`, `natgas`, `obx`, `stoxx50`.
- `MarketData.dividends: pd.DataFrame | None` — per-ticker dividend per share on the
  ex-date, aligned to the index (0 elsewhere).
- `fetch_external(symbols: dict[str, str], start, end)` and `fetch_dividends(tickers)`
  with parquet caching; `load_universe("oslo", start, end)` assembles everything.
- `slice()` slices extras and dividends too; `from_close()` yields empty extras.

## New strategy families
`strategies/macro.py` (read `market.extra`; raise `KeyError` naming the missing series):
- `MacroTrendFilter(series, window, direction)` — long all when the series' trailing
  return times `direction` is positive (oil up -> long OSE; VIX up -> flat).
- `MacroLevelRegime(series, threshold, below)` — long all when level is below/above.
- `MacroBetaRotation(series, beta_window, mom_window, top_n)` — cross-sectional: when
  the macro series has positive momentum, hold the top-N highest-beta names to it,
  otherwise the top-N lowest-beta names.
- `CrossAssetAgreement(mom_window, series_a, series_b)` — long a stock when its own
  momentum and both macro series' momentum are positive.
- `RelativeToIndex(series="obx", window)` — long stocks outperforming the index.
- `IndexDipBuy(series="obx", drawdown, window, exit_dd)` — buy all when the index is
  in a drawdown, exit on recovery.
- `VIXSpikeReversal(spike, window)` — buy all after a VIX spike, exit when VIX is back
  below its moving average.
- `USLeadLag(lookback)` — long when the S&P 500's last `lookback`-day return is positive.

`strategies/events.py` (read `market.dividends`):
- `DividendCapture(days_before, days_after)` — long from N days before an ex-date to M
  days after.
- `PostDividendReversal(hold)` — buy on the ex-date, hold `hold` days.
- `WeeklyReversal(lookback, top_n)` — cross-sectional short-term reversal (price only,
  but new to the library).

Calendar additions via existing families: Norwegian dividend season (Mar–May) and
earnings months (Feb, May, Aug, Nov) as `sell_in_may` variants.

## Library
`research/library.py` gains `OSLO_ALGORITHMS` (~50 specs, data types `macro`,
`events`) and `library_for(universe)` returning base + universe-specific specs.
`filter_algorithms` gains an `include_universe` parameter.

## Runner / CLI / web
- `run_batch.py --universe oslo` loads the universe with extras and tests the full
  library; `--rounds` is not needed: rounds are re-runs of the whole batch.
- `/api/batch` accepts `universe` (optional) and uses the universe's library.

## Success criterion
At least one non-control algorithm with verdict `strong` (p_fdr < 0.05, DSR > 0.95,
OOS excess Sharpe > 0, stability >= 0.6, >= 20 trades) on the full Oslo batch. If no
round achieves it, the honest output is the ranked leaderboard and the statement that
the search found nothing that survives correction — that result is reported, not hidden.


## Results log (all rounds re-run the full library; N accumulates)

| Round | Added | Config | N counted | Excess verdict | Alpha view | Note |
|---|---|---|---|---|---|---|
| 1 | base 116 + 60 macro/event | fixed sizing | 176 | none (RC p 0.91) | – | best: monthly equal-weight, excess Sharpe 0.22 |
| 2 | +13 anomalies (yield, low beta, LT reversal, rel. vol) | fixed | 189 | none (RC p 0.93) | – | no new entrant in top 25 |
| 3 | +7 (sector momentum, illiquidity) + alpha view | fixed | 196 | none (RC p 0.91) | 3 "strong" | flagged low-beta & illiquidity; diagnostics: 86 % cash, low-beta alpha absent 2020-24 |
| 4 | active sizing | active, no band | 392 | none (RC p 0.26) | 0 strong | trend strategies churned (28k fills); IS winner +0.76 -> OOS -0.22 |
| 5 | rebalance band 0.25 | active, band | 588 | none (RC p 0.26) | 2 candidates (p_fdr 0.09) | illiquidity: alpha 12 %/yr, t 3.1, robust to leave-one-out and sub-periods |
| 6 | +12 (seasonality, MAX, idio vol, volume premium) | active, band | 796 | none (RC p 0.25) | 2 candidates (p_fdr 0.095) | search stopped |

**Conclusion.** No algorithm meets the pre-registered `strong` gate on the Oslo
universe. The Amihud illiquidity ranking is the only economically meaningful
candidate; it cannot be separated from survivorship bias with the available data
(LSEG point-in-time constituents unavailable in this licence) and has very small
capacity. Reported as a candidate, not as a found edge.
