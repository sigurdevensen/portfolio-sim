"""Documented cross-sectional anomalies, long leg only (the engine is long/flat).

Each family has a published rationale that predates this project, so the parameter
sets in the library are a priori rather than fitted:

* Dividend yield  — value/income tilt (Fama & French 1988; Litzenberger & Ramaswamy 1979)
* Low beta        — betting against beta (Frazzini & Pedersen 2014)
* Long-term reversal — 3-5 year losers outperform (De Bondt & Thaler 1985)
* Relative volatility regime — volatility-managed exposure (Moreira & Muir 2017)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.market import MarketData

from ._util import state_signals
from .base import Strategy


class DividendYieldRank(Strategy):
    """Hold the ``top_n`` stocks with the highest trailing-``window`` dividend yield."""

    name = "dividend_yield_rank"

    def __init__(self, window: int = 252, top_n: int = 8) -> None:
        self.window, self.top_n = window, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.dividends")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        if market.dividends is None:
            raise KeyError(f"{self.name} needs MarketData.dividends")
        div = market.dividends.reindex(index=market.index, columns=market.close.columns).fillna(0.0)
        trailing = div.rolling(self.window, min_periods=self.window).sum()
        yld = trailing / market.close
        payers = yld > 0
        rank = yld.where(payers).rank(axis=1, ascending=False, method="first")
        return state_signals(rank <= self.top_n, valid=trailing.notna() & market.close.notna())


class LowBetaRank(Strategy):
    """Hold the ``top_n`` stocks with the lowest rolling beta to the index series (``direction=-1`` for high beta)."""

    name = "low_beta_rank"

    def __init__(self, series: str = "obx", window: int = 252, top_n: int = 8, direction: int = 1) -> None:
        self.series, self.window, self.top_n, self.direction = series, window, top_n, direction

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        market.require_extra(self.series)
        idx_ret = market.extra[self.series].astype(float).pct_change()
        rets = market.close.pct_change(fill_method=None)
        cov = rets.rolling(self.window, min_periods=self.window).cov(idx_ret)
        var = idx_ret.rolling(self.window, min_periods=self.window).var()
        beta = cov.div(var.replace(0, np.nan), axis=0)
        score = -beta if self.direction >= 0 else beta          # low beta first by default
        rank = score.rank(axis=1, ascending=False, method="first")
        return state_signals(rank <= self.top_n, valid=beta.notna())


class LongTermReversal(Strategy):
    """Hold the ``top_n`` worst performers over a long ``lookback`` (3-5 years), skipping the last ``skip`` days."""

    name = "long_term_reversal"

    def __init__(self, lookback: int = 756, skip: int = 21, top_n: int = 5) -> None:
        self.lookback, self.skip, self.top_n = lookback, skip, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.shift(self.skip) / data.shift(self.lookback) - 1
        rank = ret.rank(axis=1, ascending=True, method="first")     # 1 = biggest long-run loser
        return state_signals(rank <= self.top_n, valid=ret.notna())


class RelativeVolRegime(Strategy):
    """Long a stock while its short-window realised vol is below its own rolling ``ref_window`` median."""

    name = "relative_vol_regime"

    def __init__(self, window: int = 20, ref_window: int = 252) -> None:
        self.window, self.ref_window = window, ref_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        vol = data.pct_change(fill_method=None).rolling(self.window, min_periods=self.window).std()
        ref = vol.rolling(self.ref_window, min_periods=self.ref_window // 2).median()
        return state_signals(vol < ref, valid=vol.notna() & ref.notna())


class SectorMomentum(Strategy):
    """Industry momentum (Moskowitz & Grinblatt 1999): hold every stock in the ``top_k`` sectors
    by trailing ``lookback`` equal-weight sector return. Needs ``market.meta['sectors']``."""

    name = "sector_momentum"

    def __init__(self, lookback: int = 126, top_k: int = 2, skip: int = 21) -> None:
        self.lookback, self.top_k, self.skip = lookback, top_k, skip

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.meta['sectors']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        sectors = market.meta.get("sectors")
        if not sectors:
            raise KeyError(f"{self.name} needs MarketData.meta['sectors'] (a ticker -> sector map)")
        close = market.close
        ret = close.shift(self.skip) / close.shift(self.lookback) - 1
        labels = pd.Series({t: sectors.get(t, "other") for t in close.columns})
        sector_ret = ret.T.groupby(labels).mean().T                   # date x sector
        rank = sector_ret.rank(axis=1, ascending=False, method="first")
        top = rank <= self.top_k                                       # date x sector bool
        long = pd.DataFrame({t: top[labels[t]] if labels[t] in top else False for t in close.columns}, index=close.index)
        return state_signals(long, valid=ret.notna())


class IlliquidityRank(Strategy):
    """Illiquidity premium (Amihud 2002): hold the ``top_n`` least liquid names by
    mean |return| / traded value over ``window`` days. Needs volume."""

    name = "illiquidity_rank"
    requires = {"close", "volume"}

    def __init__(self, window: int = 252, top_n: int = 8) -> None:
        self.window, self.top_n = window, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        ret = market.close.pct_change(fill_method=None).abs()
        value = (market.close * market.volume).replace(0, np.nan)
        amihud = (ret / value).rolling(self.window, min_periods=self.window // 2).mean()
        rank = amihud.rank(axis=1, ascending=False, method="first")   # 1 = most illiquid
        return state_signals(rank <= self.top_n, valid=amihud.notna())


class SameMonthSeasonality(Strategy):
    """Heston & Sadka (2008): hold the ``top_n`` stocks with the highest average return in the
    same calendar month over the previous ``years`` years."""

    name = "same_month_seasonality"

    def __init__(self, years: int = 3, top_n: int = 5) -> None:
        self.years, self.top_n = years, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        monthly = data.resample("M").last().pct_change(fill_method=None)      # month-end returns
        # Average of the same calendar month's return in each of the previous `years` years.
        # NaN-aware: the first year of data has no prior-month return, so use the mean
        # of whatever prior observations exist (at least one).
        stacked = np.stack([monthly.shift(12 * k).to_numpy() for k in range(1, self.years + 1)])
        with np.errstate(invalid="ignore"):
            score = pd.DataFrame(np.nanmean(stacked, axis=0), index=monthly.index, columns=monthly.columns)
        # The score for month m uses only earlier years, so it is known at the start of month m.
        naive_idx = monthly.index.tz_convert(None) if monthly.index.tz is not None else monthly.index
        score.index = naive_idx.to_period("M")
        per = (data.index.tz_convert(None) if data.index.tz is not None else data.index).to_period("M")
        daily = pd.DataFrame(score.reindex(per).to_numpy(), index=data.index, columns=data.columns)
        rank = daily.rank(axis=1, ascending=False, method="first")
        return state_signals(rank <= self.top_n, valid=daily.notna())


class LowMaxReturn(Strategy):
    """Lottery / MAX effect (Bali, Cakici & Whitelaw 2011): hold the ``top_n`` stocks with the
    lowest maximum daily return over the past ``window`` days."""

    name = "low_max_return"

    def __init__(self, window: int = 21, top_n: int = 8) -> None:
        self.window, self.top_n = window, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        mx = data.pct_change(fill_method=None).rolling(self.window, min_periods=self.window).max()
        rank = mx.rank(axis=1, ascending=True, method="first")     # 1 = smallest max return
        return state_signals(rank <= self.top_n, valid=mx.notna())


class LowIdioVol(Strategy):
    """Ang, Hodrick, Xing & Zhang (2006): hold the ``top_n`` stocks with the lowest idiosyncratic
    volatility (residual vol after regressing on the index series) over ``window`` days."""

    name = "low_idio_vol"

    def __init__(self, series: str = "obx", window: int = 63, top_n: int = 8) -> None:
        self.series, self.window, self.top_n = series, window, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        market.require_extra(self.series)
        idx_ret = market.extra[self.series].astype(float).pct_change()
        rets = market.close.pct_change(fill_method=None)
        cov = rets.rolling(self.window, min_periods=self.window).cov(idx_ret)
        var = idx_ret.rolling(self.window, min_periods=self.window).var()
        beta = cov.div(var.replace(0, np.nan), axis=0)
        total_var = rets.rolling(self.window, min_periods=self.window).var()
        idio = np.sqrt(np.clip(total_var - beta**2 * var.to_numpy()[:, None], 0, None))
        rank = idio.rank(axis=1, ascending=True, method="first")
        return state_signals(rank <= self.top_n, valid=idio.notna())


class HighVolumePremium(Strategy):
    """Gervais, Kaniel & Mingelgrin (2001): buy stocks whose volume today is in the top
    ``quantile`` of their own past ``window`` days; hold ``hold`` days."""

    name = "high_volume_premium"
    requires = {"close", "volume"}

    def __init__(self, window: int = 50, quantile: float = 0.9, hold: int = 20) -> None:
        self.window, self.quantile, self.hold = window, quantile, hold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.generate_signals_market(MarketData.from_close(data))

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        from ._util import enter_exit_signals
        vol = market.volume
        thresh = vol.shift(1).rolling(self.window, min_periods=self.window).quantile(self.quantile)
        spike = vol > thresh
        exit_ = spike.shift(self.hold).fillna(False).astype(bool) & ~spike
        return enter_exit_signals(spike, exit_)


ANOMALY_FAMILIES = [DividendYieldRank, LowBetaRank, LongTermReversal, RelativeVolRegime, SectorMomentum, IlliquidityRank,
                    SameMonthSeasonality, LowMaxReturn, LowIdioVol, HighVolumePremium]
