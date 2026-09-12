# Norwegian Top-Dividend Strategy -- Backtest 2010-2020

**Date generated:** August 01, 2026  
**Data source:** LSEG Workspaces API (lseg-data library, desktop session)  
**Universe:** 42 major Norwegian-listed stocks (OBX / OSEBX components)  
**Strategy:** Equal-weight top 10 stocks by *trailing 12M dividend yield* on first trading day.  
**Return calculation:** Price return + dividend return (trailing yield at year-end x sell price / buy price).  
**Benchmark:** OSEBX price-return index (dividends not included in index return).  

---

## Executive Summary

Over 11 years (2010-2020), the top-10 expected-dividend strategy delivered an average annual return of **+16.2%**, compared to OSEBX price return of **+8.8%/year**.

The strategy **outperformed OSEBX by an average of +7.3 percentage points per year**, beating the index in **8 out of 11 years**.

**Cumulative 2010-2020:** The strategy returned **+371.2%** cumulatively vs. OSEBX **+142.1%** (price only).

> **Important caveat:** The OSEBX benchmark is a *price-return* index -- it excludes
> dividends paid by its constituents. OSEBX historically yields 3-5% in dividends per year,
> meaning the total-return OSEBX would be materially higher. The strategy's inclusion of
> dividends therefore creates an inherent advantage in this comparison.

---

## Year-by-Year Results

### 2010

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Equinor ASA | `EQNR.OL` | 4.9% | 147.70 | 138.60 | 4.3% | -6.2% | +4.1% | **-2.1%** |
| Veidekke ASA | `VEI.OL` | 4.8% | 43.89 | 44.52 | 4.8% | +1.4% | +4.8% | **+6.3%** |
| Orkla ASA | `ORK.OL` | 3.9% | 57.95 | 56.70 | 4.0% | -2.2% | +3.9% | **+1.7%** |
| Sparebank 1 SMN | `MING.OL` | 3.6% | 45.13 | 49.48 | 4.6% | +9.6% | +5.1% | **+14.7%** |
| Aker ASA | `AKER.OL` | 3.0% | 167.50 | 140.00 | 5.7% | -16.4% | +4.8% | **-11.6%** |
| Leroy Seafood Group ASA | `LSG.OL` | 2.8% | 10.15 | 19.85 | 3.5% | +95.6% | +6.9% | **+102.5%** |
| Solstad Offshore ASA | `SOFF.OL` | 1.9% | 10650.87 | 11655.67 | 2.2% | +9.4% | +2.4% | **+11.8%** |
| Nordic Semiconductor ASA | `NOD.OL` | 1.9% | 10.80 | 24.80 | 1.6% | +129.6% | +3.7% | **+133.3%** |
| Yara International ASA | `YAR.OL` | 1.7% | 259.40 | 321.63 | 1.3% | +24.0% | +1.7% | **+25.6%** |
| Kongsberg Gruppen ASA | `KOG.OL` | 1.5% | 11.73 | 17.10 | 1.5% | +45.8% | +2.2% | **+47.9%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+33.0%** |
| OSEBX return (price only) | +15.7% |
| Excess return vs OSEBX | **+17.3%** |

*Strong outperformance: strategy beat OSEBX by 17.3 pp.*

### 2011

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Sparebanken Ost | `SPOG.OL` | 9.8% | 41.00 | 33.00 | 15.2% | -19.5% | +12.2% | **-7.3%** |
| Mowi ASA | `MOWI.OL` | 6.5% | 61.25 | 25.86 | 30.9% | -57.8% | +13.1% | **-44.7%** |
| Aker ASA | `AKER.OL` | 5.5% | 144.50 | 155.00 | 6.5% | +7.3% | +6.9% | **+14.2%** |
| Veidekke ASA | `VEI.OL` | 4.9% | 43.25 | 32.82 | 6.5% | -24.1% | +4.9% | **-19.2%** |
| Sparebank 1 SMN | `MING.OL` | 4.6% | 49.48 | 36.01 | 7.6% | -27.2% | +5.6% | **-21.7%** |
| Equinor ASA | `EQNR.OL` | 4.3% | 140.30 | 153.50 | 4.1% | +9.4% | +4.5% | **+13.9%** |
| Orkla ASA | `ORK.OL` | 3.9% | 57.00 | 44.65 | 16.8% | -21.7% | +13.2% | **-8.5%** |
| SalMar ASA | `SALM.OL` | 3.6% | 61.50 | 30.00 | 13.3% | -51.2% | +6.5% | **-44.7%** |
| Leroy Seafood Group ASA | `LSG.OL` | 3.6% | 19.70 | 8.40 | 11.9% | -57.4% | +5.1% | **-52.3%** |
| TGS ASA | `TGS.OL` | 3.0% | 131.50 | 132.50 | 3.8% | +0.8% | +3.8% | **+4.6%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **-16.6%** |
| OSEBX return (price only) | -13.1% |
| Excess return vs OSEBX | **-3.4%** |

*Slight underperformance: strategy trailed OSEBX by 3.4 pp.*

### 2012

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Mowi ASA | `MOWI.OL` | 30.6% | 26.12 | 51.20 | 0.0% | +96.0% | 0.0% | **+96.0%** |
| Orkla ASA | `ORK.OL` | 16.7% | 44.90 | 48.50 | 5.2% | +8.0% | +5.6% | **+13.6%** |
| Sparebanken Ost | `SPOG.OL` | 14.7% | 33.90 | 32.50 | 6.2% | -4.1% | +5.9% | **+1.8%** |
| SalMar ASA | `SALM.OL` | 14.0% | 28.60 | 44.70 | 0.0% | +56.3% | 0.0% | **+56.3%** |
| Leroy Seafood Group ASA | `LSG.OL` | 12.1% | 8.28 | 12.95 | 5.4% | +56.5% | +8.5% | **+65.0%** |
| P/F Bakkafrost | `BAKKA.OL` | 11.3% | 35.96 | 60.44 | 1.7% | +68.1% | +2.8% | **+70.9%** |
| Sparebank 1 SMN | `MING.OL` | 7.7% | 35.92 | 34.80 | 5.7% | -3.1% | +5.6% | **+2.5%** |
| Austevoll Seafood ASA | `AUSS.OL` | 6.9% | 21.60 | 28.50 | 3.5% | +31.9% | +4.6% | **+36.6%** |
| DNB Bank ASA | `DNB.OL` | 6.8% | 58.95 | 70.40 | 2.8% | +19.4% | +3.4% | **+22.8%** |
| Veidekke ASA | `VEI.OL` | 6.4% | 32.90 | 37.31 | 6.2% | +13.4% | +7.1% | **+20.5%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+38.6%** |
| OSEBX return (price only) | +14.0% |
| Excess return vs OSEBX | **+24.6%** |

*Strong outperformance: strategy beat OSEBX by 24.6 pp.*

### 2013

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Veidekke ASA | `VEI.OL` | 6.2% | 37.91 | 41.38 | 5.1% | +9.2% | +5.6% | **+14.8%** |
| Sparebanken Ost | `SPOG.OL` | 6.0% | 33.50 | 43.00 | 7.0% | +28.4% | +9.0% | **+37.3%** |
| Sparebank 1 SMN | `MING.OL` | 5.6% | 35.40 | 55.00 | 2.7% | +55.4% | +4.2% | **+59.6%** |
| Strongpoint ASA | `STRO.OL` | 5.6% | 4.50 | 5.62 | 4.4% | +24.9% | +5.6% | **+30.4%** |
| Leroy Seafood Group ASA | `LSG.OL` | 5.2% | 13.40 | 17.70 | 4.0% | +32.1% | +5.2% | **+37.3%** |
| Aker ASA | `AKER.OL` | 5.0% | 218.50 | 222.00 | 5.4% | +1.6% | +5.5% | **+7.1%** |
| Orkla ASA | `ORK.OL` | 5.0% | 49.68 | 47.32 | 5.3% | -4.8% | +5.0% | **+0.3%** |
| Equinor ASA | `EQNR.OL` | 4.6% | 141.90 | 147.00 | 4.6% | +3.6% | +4.8% | **+8.4%** |
| Telenor ASA | `TEL.OL` | 4.4% | 110.26 | 140.73 | 4.1% | +27.6% | +5.3% | **+32.9%** |
| Austevoll Seafood ASA | `AUSS.OL` | 3.4% | 29.30 | 35.50 | 3.4% | +21.2% | +4.1% | **+25.3%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+25.3%** |
| OSEBX return (price only) | +20.8% |
| Excess return vs OSEBX | **+4.6%** |

*Modest outperformance: strategy edged OSEBX by 4.6 pp.*

### 2014

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Sparebanken Ost | `SPOG.OL` | 6.9% | 43.50 | 51.00 | 5.9% | +17.2% | +6.9% | **+24.1%** |
| Aker ASA | `AKER.OL` | 5.6% | 214.00 | 164.50 | 7.9% | -23.1% | +6.1% | **-17.1%** |
| Orkla ASA | `ORK.OL` | 5.4% | 46.64 | 51.15 | 4.9% | +9.7% | +5.4% | **+15.0%** |
| TGS ASA | `TGS.OL` | 5.3% | 151.80 | 161.70 | 5.3% | +6.5% | +5.6% | **+12.1%** |
| Veidekke ASA | `VEI.OL` | 5.1% | 41.64 | 62.54 | 4.1% | +50.2% | +6.1% | **+56.3%** |
| Yara International ASA | `YAR.OL` | 5.0% | 246.73 | 318.11 | 3.0% | +28.9% | +3.9% | **+32.8%** |
| Equinor ASA | `EQNR.OL` | 4.6% | 146.90 | 131.20 | 5.4% | -10.7% | +4.8% | **-5.9%** |
| Strongpoint ASA | `STRO.OL` | 4.3% | 5.79 | 7.25 | 4.1% | +25.2% | +5.2% | **+30.4%** |
| Telenor ASA | `TEL.OL` | 4.2% | 139.56 | 147.44 | 4.6% | +5.6% | +4.9% | **+10.5%** |
| Leroy Seafood Group ASA | `LSG.OL` | 4.0% | 17.50 | 27.30 | 3.7% | +56.0% | +5.7% | **+61.7%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+22.0%** |
| OSEBX return (price only) | +5.3% |
| Excess return vs OSEBX | **+16.7%** |

*Strong outperformance: strategy beat OSEBX by 16.7 pp.*

### 2015

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| BW LPG Ltd | `BWLPG.OL` | 9.9% | 51.99 | 72.63 | 21.9% | +39.7% | +30.6% | **+70.3%** |
| Aker ASA | `AKER.OL` | 7.9% | 165.00 | 164.00 | 6.1% | -0.6% | +6.1% | **+5.5%** |
| Mowi ASA | `MOWI.OL` | 6.9% | 105.00 | 119.60 | 4.3% | +13.9% | +5.0% | **+18.9%** |
| Solstad Offshore ASA | `SOFF.OL` | 6.3% | 7937.92 | 2059.84 | 17.1% | -74.1% | +4.4% | **-69.6%** |
| SalMar ASA | `SALM.OL` | 6.2% | 130.00 | 155.00 | 6.5% | +19.2% | +7.7% | **+26.9%** |
| Sparebanken Ost | `SPOG.OL` | 5.8% | 52.00 | 47.60 | 10.5% | -8.5% | +9.6% | **+1.2%** |
| Equinor ASA | `EQNR.OL` | 5.5% | 130.10 | 123.70 | 6.3% | -4.9% | +6.0% | **+1.1%** |
| TGS ASA | `TGS.OL` | 5.3% | 161.20 | 141.40 | 6.0% | -12.3% | +5.3% | **-7.0%** |
| Orkla ASA | `ORK.OL` | 4.9% | 51.15 | 70.10 | 3.6% | +37.0% | +4.9% | **+41.9%** |
| Subsea 7 SA | `SUBC.OL` | 4.7% | 77.25 | 63.05 | 0.0% | -18.4% | 0.0% | **-18.4%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+7.1%** |
| OSEBX return (price only) | +5.3% |
| Excess return vs OSEBX | **+1.7%** |

*Modest outperformance: strategy edged OSEBX by 1.7 pp.*

### 2016

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| BW LPG Ltd | `BWLPG.OL` | 22.3% | 71.39 | 36.15 | 17.5% | -49.4% | +8.9% | **-40.5%** |
| Solstad Offshore ASA | `SOFF.OL` | 17.1% | 2059.84 | 1163.87 | 0.0% | -43.5% | 0.0% | **-43.5%** |
| Sparebanken Ost | `SPOG.OL` | 10.7% | 46.90 | 52.00 | 6.3% | +10.9% | +7.0% | **+17.9%** |
| SalMar ASA | `SALM.OL` | 6.6% | 152.00 | 258.10 | 3.9% | +69.8% | +6.6% | **+76.4%** |
| Kongsberg Gruppen ASA | `KOG.OL` | 6.5% | 18.38 | 16.00 | 3.4% | -12.9% | +3.0% | **-10.0%** |
| Equinor ASA | `EQNR.OL` | 6.4% | 123.50 | 158.40 | 4.6% | +28.3% | +5.9% | **+34.2%** |
| Aker ASA | `AKER.OL` | 6.1% | 163.00 | 323.00 | 3.1% | +98.2% | +6.1% | **+104.3%** |
| TGS ASA | `TGS.OL` | 6.0% | 142.10 | 191.70 | 2.6% | +34.9% | +3.5% | **+38.4%** |
| Telenor ASA | `TEL.OL` | 5.0% | 141.31 | 125.54 | 5.8% | -11.2% | +5.2% | **-6.0%** |
| Sparebank 1 SMN | `MING.OL` | 4.5% | 50.00 | 64.75 | 3.5% | +29.5% | +4.5% | **+34.0%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+20.5%** |
| OSEBX return (price only) | +13.9% |
| Excess return vs OSEBX | **+6.7%** |

*Modest outperformance: strategy edged OSEBX by 6.7 pp.*

### 2017

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| BW LPG Ltd | `BWLPG.OL` | 17.2% | 36.95 | 38.45 | 1.9% | +4.0% | +2.0% | **+6.1%** |
| Strongpoint ASA | `STRO.OL` | 8.6% | 16.90 | 11.10 | 4.5% | -34.3% | +3.0% | **-31.4%** |
| Austevoll Seafood ASA | `AUSS.OL` | 8.3% | 84.25 | 68.25 | 3.7% | -19.0% | +3.0% | **-16.0%** |
| Sparebanken Ost | `SPOG.OL` | 6.2% | 53.00 | 55.25 | 7.2% | +4.2% | +7.5% | **+11.8%** |
| Telenor ASA | `TEL.OL` | 5.7% | 128.95 | 171.19 | 4.4% | +32.8% | +5.9% | **+38.6%** |
| Mowi ASA | `MOWI.OL` | 5.5% | 156.50 | 139.00 | 8.9% | -11.2% | +7.9% | **-3.3%** |
| Equinor ASA | `EQNR.OL` | 4.5% | 160.00 | 175.20 | 4.1% | +9.5% | +4.5% | **+14.0%** |
| Yara International ASA | `YAR.OL` | 4.4% | 327.64 | 358.99 | 2.7% | +9.6% | +2.9% | **+12.5%** |
| SalMar ASA | `SALM.OL` | 3.9% | 257.80 | 246.80 | 4.9% | -4.3% | +4.7% | **+0.4%** |
| Sparebank 1 SMN | `MING.OL` | 3.5% | 64.50 | 82.25 | 3.6% | +27.5% | +4.7% | **+32.2%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+6.5%** |
| OSEBX return (price only) | +17.8% |
| Excess return vs OSEBX | **-11.3%** |

*Significant underperformance: strategy trailed OSEBX by 11.3 pp.*

### 2018

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Mowi ASA | `MOWI.OL` | 9.0% | 137.10 | 182.70 | 5.7% | +33.3% | +7.6% | **+40.8%** |
| Sparebanken Ost | `SPOG.OL` | 7.3% | 55.00 | 55.60 | 9.0% | +1.1% | +9.1% | **+10.2%** |
| SalMar ASA | `SALM.OL` | 5.0% | 240.80 | 428.00 | 4.4% | +77.7% | +7.9% | **+85.6%** |
| Veidekke ASA | `VEI.OL` | 5.0% | 77.09 | 82.17 | 5.2% | +6.6% | +5.5% | **+12.1%** |
| Strongpoint ASA | `STRO.OL` | 4.6% | 10.85 | 8.90 | 5.6% | -18.0% | +4.6% | **-13.4%** |
| Telenor ASA | `TEL.OL` | 4.4% | 171.87 | 167.50 | 4.8% | -2.5% | +4.7% | **+2.2%** |
| Equinor ASA | `EQNR.OL` | 4.1% | 177.45 | 183.75 | 4.2% | +3.6% | +4.3% | **+7.9%** |
| Subsea 7 SA | `SUBC.OL` | 4.0% | 124.50 | 84.28 | 5.9% | -32.3% | +4.0% | **-28.3%** |
| Aker ASA | `AKER.OL` | 3.9% | 408.00 | 462.00 | 3.9% | +13.2% | +4.4% | **+17.6%** |
| Austevoll Seafood ASA | `AUSS.OL` | 3.8% | 66.30 | 106.80 | 2.6% | +61.1% | +4.2% | **+65.3%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+20.0%** |
| OSEBX return (price only) | -1.9% |
| Excess return vs OSEBX | **+21.9%** |

*Strong outperformance: strategy beat OSEBX by 21.9 pp.*

### 2019

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Sparebanken Ost | `SPOG.OL` | 9.1% | 55.20 | 54.60 | 8.4% | -1.1% | +8.3% | **+7.2%** |
| Subsea 7 SA | `SUBC.OL` | 6.0% | 83.98 | 104.95 | 1.4% | +25.0% | +1.8% | **+26.8%** |
| Mowi ASA | `MOWI.OL` | 5.6% | 184.90 | 228.20 | 4.6% | +23.4% | +5.6% | **+29.0%** |
| Strongpoint ASA | `STRO.OL` | 5.6% | 9.00 | 12.00 | 4.6% | +33.3% | +6.1% | **+39.4%** |
| Sparebank 1 SMN | `MING.OL` | 5.2% | 85.20 | 100.20 | 5.1% | +17.6% | +6.0% | **+23.6%** |
| DNB Bank ASA | `DNB.OL` | 5.1% | 138.85 | 164.00 | 5.0% | +18.1% | +5.9% | **+24.1%** |
| Veidekke ASA | `VEI.OL` | 5.1% | 83.78 | 101.34 | 4.2% | +21.0% | +5.1% | **+26.0%** |
| Telenor ASA | `TEL.OL` | 4.8% | 169.35 | 157.45 | 5.3% | -7.0% | +5.0% | **-2.1%** |
| Aker BP ASA | `AKRBP.OL` | 4.7% | 222.80 | 288.00 | 6.6% | +29.3% | +8.6% | **+37.9%** |
| Norsk Hydro ASA | `NHY.OL` | 4.6% | 38.45 | 32.64 | 3.8% | -15.1% | +3.3% | **-11.9%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+20.0%** |
| OSEBX return (price only) | +15.9% |
| Excess return vs OSEBX | **+4.1%** |

*Modest outperformance: strategy edged OSEBX by 4.1 pp.*

### 2020

**Selected stocks** (top 3 by trailing dividend yield at start of year):

| Stock | RIC | Expected Yield | Buy Price | Sell Price | Actual Div Yield | Price Return | Div Return | Total Return |
|-------|-----|:-:|--:|--:|:-:|:-:|:-:|:-:|
| Sparebanken Ost | `SPOG.OL` | 8.2% | 56.40 | 51.40 | 7.0% | -8.9% | +6.4% | **-2.5%** |
| Aker BP ASA | `AKRBP.OL` | 6.6% | 289.00 | 216.20 | 5.2% | -25.2% | +3.9% | **-21.3%** |
| Equinor ASA | `EQNR.OL` | 5.3% | 177.95 | 144.95 | 3.7% | -18.5% | +3.0% | **-15.5%** |
| Telenor ASA | `TEL.OL` | 5.3% | 157.65 | 145.90 | 6.0% | -7.5% | +5.5% | **-1.9%** |
| SalMar ASA | `SALM.OL` | 5.1% | 454.00 | 503.60 | 2.6% | +10.9% | +2.9% | **+13.8%** |
| BW LPG Ltd | `BWLPG.OL` | 5.0% | 77.76 | 58.70 | 14.1% | -24.5% | +10.6% | **-13.9%** |
| DNB Bank ASA | `DNB.OL` | 5.0% | 165.80 | 168.00 | 0.0% | +1.3% | 0.0% | **+1.3%** |
| Sparebank 1 SMN | `MING.OL` | 5.0% | 102.60 | 97.60 | 5.1% | -4.9% | +4.9% | **-0.0%** |
| Strongpoint ASA | `STRO.OL` | 4.6% | 11.95 | 19.50 | 3.1% | +63.2% | +5.0% | **+68.2%** |
| Mowi ASA | `MOWI.OL` | 4.5% | 229.50 | 191.00 | 1.4% | -16.8% | +1.1% | **-15.6%** |

| Metric | Value |
|--------|-------|
| Portfolio return (equal-weight) | **+1.3%** |
| OSEBX return (price only) | +3.5% |
| Excess return vs OSEBX | **-2.2%** |

*Slight underperformance: strategy trailed OSEBX by 2.2 pp.*

---

## Summary Table

| Year | Top 3 Stocks Selected | Portfolio Return | OSEBX Return | Excess |
|------|----------------------|:-:|:-:|:-:|
| 2010 | EQNR, VEI, ORK, MING, AKER, LSG, SOFF, NOD, YAR, KOG | +33.0% | +15.7% | +17.3% |
| 2011 | SPOG, MOWI, AKER, VEI, MING, EQNR, ORK, SALM, LSG, TGS | -16.6% | -13.1% | -3.4% |
| 2012 | MOWI, ORK, SPOG, SALM, LSG, BAKKA, MING, AUSS, DNB, VEI | +38.6% | +14.0% | +24.6% |
| 2013 | VEI, SPOG, MING, STRO, LSG, AKER, ORK, EQNR, TEL, AUSS | +25.3% | +20.8% | +4.6% |
| 2014 | SPOG, AKER, ORK, TGS, VEI, YAR, EQNR, STRO, TEL, LSG | +22.0% | +5.3% | +16.7% |
| 2015 | BWLPG, AKER, MOWI, SOFF, SALM, SPOG, EQNR, TGS, ORK, SUBC | +7.1% | +5.3% | +1.7% |
| 2016 | BWLPG, SOFF, SPOG, SALM, KOG, EQNR, AKER, TGS, TEL, MING | +20.5% | +13.9% | +6.7% |
| 2017 | BWLPG, STRO, AUSS, SPOG, TEL, MOWI, EQNR, YAR, SALM, MING | +6.5% | +17.8% | -11.3% |
| 2018 | MOWI, SPOG, SALM, VEI, STRO, TEL, EQNR, SUBC, AKER, AUSS | +20.0% | -1.9% | +21.9% |
| 2019 | SPOG, SUBC, MOWI, STRO, MING, DNB, VEI, TEL, AKRBP, NHY | +20.0% | +15.9% | +4.1% |
| 2020 | SPOG, AKRBP, EQNR, TEL, SALM, BWLPG, DNB, MING, STRO, MOWI | +1.3% | +3.5% | -2.2% |
| **2010-2020** | *(cumulative)* | **+371.2%** | **+142.1%** | **+94.6%** |

---

## Findings: Does Buying High Expected-Dividend Stocks Pay Off?

### Key Takeaways

**1. Raw numbers:** The strategy beat OSEBX price-return in 8/11 years with an average excess return of +7.3 pp/year.

**2. The benchmark caveat is critical.** OSEBX is a *price-return* index -- it does not include dividends. The Norwegian market historically yields 3-5% per year in dividends. A fair comparison against the OSEBX total return index would reduce the strategy's apparent average advantage by roughly 3-5 pp/year, making the edge much smaller.

**3. The strategy showed robust excess returns in 2010-2020.** 8 of 11 years beat OSEBX price return, with three strong outperformance years (2012: +24.6 pp, 2014: +16.7 pp, 2018: +21.9 pp). The 2010-2020 period was generally favourable for dividend investing because Norwegian companies maintained or grew dividends through most of the decade, unlike the post-COVID period where special dividends inflated and then collapsed.

**4. 2012 -- the salmon bounce.** After a catastrophic 2011 for aquaculture stocks (salmon prices collapsed, Mowi fell -58%, SalMar -51%, Lerøy -57%), the strategy entered 2012 holding these stocks at apparent trailing yields of 14-31% (high because both prices were depressed AND 2010 dividends were large). In 2012, all three recovered strongly (Mowi +96%, Bakkafrost +68%, SalMar +56%, Lerøy +57%). High yield after a sector crash can signal recovery, not just a trap.

**5. Savings banks were the reliable anchors.** Sparebanken Øst (`SPOG.OL`) and SpareBank 1 SMN (`MING.OL`) appeared in the top 10 in nearly every year. They offered 5-10% yields and typically delivered stable price performance. Unlike cyclical stocks, savings banks provided consistent dividend income without dramatic boom-bust swings in the underlying business.

**6. Three bad years had clear causes.** 2011: broad market selloff (-13.1% OSEBX) hit high-yield cyclicals harder. 2017: BW LPG (17% yield at start) paid almost nothing (tanker rates collapsed, only 1.9% actual yield) while STRO.OL fell -34%. The trailing yield was a pure trap. 2020: COVID caused Finanstilsynet to ban bank dividends and oil companies to slash payments. OSEBX still gained +3.5% while the high-yield picks lost -2.2% in total.

**7. 2010 was notable for unexpected capital gains.** The top 10 by yield (max 4.9%) also included Nordic Semiconductor (+130%), Lerøy Seafood (+96%), and Kongsberg (+46%). These stocks had relatively modest expected yields but delivered massive price returns. With 10 holdings, the portfolio captured these winners even though they weren't selected for yield -- they just happened to be yield leaders after subdued 2009 prices.

### Bottom Line

On a price-return comparison, the strategy shows promise -- averaging 7.3 pp/year above OSEBX price return. However, once OSEBX dividends are included in the benchmark, the advantage likely disappears or narrows substantially. The strategy is not obviously superior to simply holding the market, but it does generate meaningful income through dividend collection.

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