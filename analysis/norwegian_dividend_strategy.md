# Norwegian Top-Dividend Strategy -- Backtest 2020-2025

**Date generated:** August 01, 2026  
**Data source:** LSEG Workspaces API (lseg-data library, desktop session)  
**Universe:** 36 major Norwegian-listed stocks (OBX / OSEBX components)  
**Strategy:** Equal-weight top 3 stocks by *trailing 12M dividend yield* on first trading day.  
**Return calculation:** Price return + dividend return (trailing yield at year-end x sell price / buy price).  
**Benchmark:** OSEBX price-return index (dividends not included in index return).  

---

## Executive Summary

Over 6 years (2020-2025), the top-3 expected-dividend strategy delivered an average annual return of **+17.1%**, compared to OSEBX price return of **+10.0%/year**.

The strategy **outperformed OSEBX by an average of +7.1 percentage points per year**, beating the index in **3 out of 6 years**.

**Cumulative 2020-2025:** The strategy returned **+126.8%** cumulatively vs. OSEBX **+74.0%** (price only).

> **Important caveat:** The OSEBX benchmark is a *price-return* index -- it excludes
> dividends paid by its constituents. OSEBX historically yields 3-5% in dividends per year,
> meaning the total-return OSEBX would be materially higher. The strategy's inclusion of
> dividends therefore creates an inherent advantage in this comparison.

---

## Year-by-Year Results

### 2020

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Sparebanken Ost | `SPOG.OL` | 8.2% | 56.40 | 51.40 | 7.0% | -8.9% | +6.4% | **-2.5%** |
| Aker BP ASA | `AKRBP.OL` | 6.6% | 289.00 | 216.20 | 5.2% | -25.2% | +3.9% | **-21.3%** |
| Equinor ASA | `EQNR.OL` | 5.3% | 177.95 | 144.95 | 3.7% | -18.5% | +3.0% | **-15.5%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **-13.1%** |
| OSEBX return (price only) | +3.5% |
| Excess return vs OSEBX | **-16.6%** |

*Significant underperformance: strategy trailed OSEBX by 16.6 pp.*

### 2021

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| BW LPG Ltd | `BWLPG.OL` | 13.4% | 61.49 | 49.80 | 12.8% | -19.0% | +10.4% | **-8.6%** |
| Hafnia Ltd | `HAFNI.OL` | 13.4% | 15.92 | 17.38 | 5.1% | +9.2% | +5.5% | **+14.7%** |
| Sparebanken Ost | `SPOG.OL` | 7.0% | 51.60 | 57.20 | 7.9% | +10.9% | +8.7% | **+19.6%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+8.5%** |
| OSEBX return (price only) | +24.4% |
| Excess return vs OSEBX | **-15.8%** |

*Significant underperformance: strategy trailed OSEBX by 15.8 pp.*

### 2022

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| BW LPG Ltd | `BWLPG.OL` | 12.7% | 50.25 | 75.42 | 12.7% | +50.1% | +19.1% | **+69.2%** |
| Yara International ASA | `YAR.OL` | 8.5% | 468.00 | 430.60 | 9.3% | -8.0% | +8.5% | **+0.6%** |
| Sparebanken Ost | `SPOG.OL` | 7.9% | 57.20 | 47.00 | 8.2% | -17.8% | +6.7% | **-11.1%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+19.5%** |
| OSEBX return (price only) | -1.8% |
| Excess return vs OSEBX | **+21.4%** |

*Strong outperformance: strategy beat OSEBX by 21.4 pp.*

### 2023

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| MPC Container Ships ASA | `MPCC.OL` | 21.9% | 16.70 | 13.32 | 47.9% | -20.2% | +38.2% | **+18.0%** |
| BW LPG Ltd | `BWLPG.OL` | 12.6% | 76.02 | 150.54 | 22.0% | +98.0% | +43.5% | **+141.6%** |
| Telenor ASA | `TEL.OL` | 10.0% | 92.60 | 116.60 | 8.1% | +25.9% | +10.2% | **+36.1%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+65.2%** |
| OSEBX return (price only) | +9.1% |
| Excess return vs OSEBX | **+56.1%** |

*Strong outperformance: strategy beat OSEBX by 56.1 pp.*

### 2024

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| MPC Container Ships ASA | `MPCC.OL` | 47.1% | 13.57 | 20.73 | 24.8% | +52.8% | +37.8% | **+90.6%** |
| BW LPG Ltd | `BWLPG.OL` | 21.1% | 156.51 | 124.67 | 25.8% | -20.3% | +20.5% | **+0.2%** |
| Yara International ASA | `YAR.OL` | 17.9% | 364.00 | 300.80 | 1.7% | -17.4% | +1.4% | **-16.0%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+24.9%** |
| OSEBX return (price only) | +9.0% |
| Excess return vs OSEBX | **+15.9%** |

*Strong outperformance: strategy beat OSEBX by 15.9 pp.*

### 2025

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| BW LPG Ltd | `BWLPG.OL` | 24.2% | 133.03 | 131.34 | 10.1% | -1.3% | +9.9% | **+8.7%** |
| MPC Container Ships ASA | `MPCC.OL` | 23.5% | 21.80 | 17.64 | 15.4% | -19.1% | +12.5% | **-6.6%** |
| Hafnia Ltd | `HAFNI.OL` | 23.4% | 64.75 | 54.40 | 7.4% | -16.0% | +6.2% | **-9.7%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **-2.6%** |
| OSEBX return (price only) | +15.7% |
| Excess return vs OSEBX | **-18.3%** |

*Significant underperformance: strategy trailed OSEBX by 18.3 pp.*

---

## Summary Table

| Year | Top 3 Stocks Selected | Portfolio Return | OSEBX Return | Excess |
|------|----------------------|:-:|:-:|:-:|
| 2020 | SPOG, AKRBP, EQNR | -13.1% | +3.5% | -16.6% |
| 2021 | BWLPG, HAFNI, SPOG | +8.5% | +24.4% | -15.8% |
| 2022 | BWLPG, YAR, SPOG | +19.5% | -1.8% | +21.4% |
| 2023 | MPCC, BWLPG, TEL | +65.2% | +9.1% | +56.1% |
| 2024 | MPCC, BWLPG, YAR | +24.9% | +9.0% | +15.9% |
| 2025 | BWLPG, MPCC, HAFNI | -2.6% | +15.7% | -18.3% |
| **2020-2025** | *(cumulative)* | **+126.8%** | **+74.0%** | **+30.3%** |

---

## Findings: Does Buying High Expected-Dividend Stocks Pay Off?

### Key Takeaways

**1. Raw numbers:** The strategy beat OSEBX price-return in 3/6 years with an average excess return of +7.1 pp/year.

**2. The benchmark caveat is critical.** OSEBX is a *price-return* index -- it does not include dividends. The Norwegian market historically yields 3-5% per year in dividends. A fair comparison against the OSEBX total return index would reduce the strategy's apparent average advantage by roughly 3-5 pp/year, making the edge much smaller.

**3. Shipping sector dominated the top-yield list.** BW LPG (`BWLPG.OL`) appeared in the top 3 in *five out of six years* (2021-2025). MPC Container Ships (`MPCC.OL`) appeared in 2023 and 2024. Hafnia (`HAFNI.OL`) appeared in 2021 and 2025. These shipping companies paid enormous special dividends during the post-COVID freight rate supercycle (2021-2023). The strategy effectively became a bet on international shipping -- a highly cyclical, volatile sector. When freight rates fell in 2024-2025, the strategy's performance deteriorated sharply.

**4. 2023 was an extraordinary outlier (+65.2%).** BW LPG returned +141.6% total in 2023 alone -- driven by both a massive 22% year-end dividend yield (actual dividends collected) and a +98% stock price gain as tanker rates surged. This one position nearly doubled in a single year. Outliers like this can significantly skew backtests: without 2023, the strategy's average excess return would be much lower.

**5. 2020 -- the COVID dividend trap.** The top picks at start of 2020 were SpareBank 1 SR/Ost (8.2%), Aker BP (6.6%), and Equinor (5.3%) -- all based on high 2019 dividends. The strategy lost -13.1% while OSEBX gained +3.5%. COVID caused oil majors to cut dividends (Equinor cut its quarterly to $0.09 from $0.26) and Finanstilsynet required Norwegian banks to cancel dividend payments. High trailing yield provided no protection against fundamental dividend cuts.

**6. Yara 2024 -- the value trap in action.** Yara International appeared with 17.9% expected yield at start of 2024, based on exceptionally high 2022-2023 fertilizer-market dividends. In 2024, Yara slashed its dividend as nitrogen prices normalized, resulting in only 1.7% actual yield at year-end. The stock also fell -17.4%. Total return: -16.0%. This is the textbook 'yield trap': a temporarily high yield reflects extraordinary past profits that cannot be sustained.

**7. The signal works *when it works* -- but fails during sector downturns.** Years 2022-2024 showed strong outperformance because shipping/tanker stocks paid AND appreciated simultaneously. Years 2020, 2021, and 2025 showed underperformance because the strategy rotated into sectors (oil in 2020, shipping in 2021 before the supercycle, shipping again in 2025 after it peaked) at the wrong time. Dividend yield alone cannot predict the timing of sector cycles.

### Bottom Line

On a price-return comparison, the strategy shows promise -- averaging 7.1 pp/year above OSEBX price return. However, once OSEBX dividends are included in the benchmark, the advantage likely disappears or narrows substantially. The strategy is not obviously superior to simply holding the market, but it does generate meaningful income through dividend collection.

---

## Methodology

### Signal: Trailing Dividend Yield

Each year, stocks are ranked by `TR.DividendYield` (LSEG field) as of the first trading day of January. This is the **trailing 12-month dividend yield** -- the sum of all dividends paid in the previous year, divided by the current stock price.

Note: LSEG's forward consensus dividend yield (`TR.DividendYieldFwd`) does not support historical date queries via the desktop API, so trailing yield is used as the best available proxy for investor expectations at the start of each year.

### Dividend Return Calculation

Dividend return = `TR.DividendYield(Dec31) * sell_price / buy_price`

This formula converts the year-end trailing yield into an actual per-share dividend amount (yield% * sell price = NOK dividends equivalent), then divides by the buy price to express it as a return relative to the purchase price. This approach handles currency differences automatically: Equinor pays USD dividends, but LSEG's yield computation already normalizes against the NOK-denominated stock price.

### Price Return

Price return = `(last_close_Dec - first_close_Jan) / first_close_Jan`  using `OFF_CLOSE` (Oslo official close) from `ld.get_history()`.

### Benchmark

OSEBX (`.OSEBX` RIC) price return for the same calendar year. The OSEBX is a cap-weighted index of all Norwegian listed companies, rebalanced semi-annually.

---

*Generated: August 01, 2026. Data: LSEG Workspaces API. Script: `scripts/analyze_norwegian_dividends.py`.*  
*Not investment advice. For research and educational purposes only.*