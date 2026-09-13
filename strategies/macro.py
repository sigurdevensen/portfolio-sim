"""Macro-driven strategy families: signals from external series in ``market.extra``.

Every family names the series it needs; a missing series raises ``KeyError`` with
the available names so a batch records a clear per-algorithm error instead of
silently trading on nothing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.market import MarketData

from ._util import enter_exit_signals, state_signals
from .base import Strategy


def _broadcast(mask: pd.Series, market: MarketData, valid: pd.Series | None = None) -> pd.DataFrame:
    """Turn a per-date boolean into a full signal frame: 1 / -1 / 0 (warm-up)."""
    if valid is None:
        valid = mask.notna()
    long = pd.DataFrame(np.repeat(mask.fillna(False).astype(bool).to_numpy()[:, None], market.close.shape[1], axis=1),
                        index=market.index, columns=market.close.columns)
    valid_df = pd.DataFrame(np.repeat(valid.to_numpy()[:, None], market.close.shape[1], axis=1),
                            index=market.index, columns=market.close.columns)
    return state_signals(long, valid=valid_df)


def _series(market: MarketData, name: str) -> pd.Series:
    market.require_extra(name)
    s = market.extra[name]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.astype(float)


class MacroTrendFilter(Strategy):
    """Long every stock while the macro series' trailing return (times ``direction``) is positive."""

    name = "macro_trend"

    def __init__(self, series: str = "brent", window: int = 60, direction: int = 1) -> None:
        self.series, self.window, self.direction = series, window, direction

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        s = _series(market, self.series)
        ret = s.pct_change(self.window) * self.direction
        return _broadcast(ret > 0, market, valid=ret.notna())


class MacroLevelRegime(Strategy):
    """Long every stock while the macro series is below (or above) a fixed level."""

    name = "macro_level"

    def __init__(self, series: str = "vix", threshold: float = 25.0, below: bool = True) -> None:
        self.series, self.threshold, self.below = series, threshold, below

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        s = _series(market, self.series)
        cond = (s < self.threshold) if self.below else (s > self.threshold)
        return _broadcast(cond, market, valid=s.notna())


class MacroBetaRotation(Strategy):
    """Rotate on macro momentum: hold the top-N highest-beta stocks to the series when it
    is rising, the top-N lowest-beta stocks when it is falling."""

    name = "macro_beta_rotation"

    def __init__(self, series: str = "brent", beta_window: int = 120, mom_window: int = 60, top_n: int = 5) -> None:
        self.series, self.beta_window, self.mom_window, self.top_n = series, beta_window, mom_window, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        s = _series(market, self.series)
        sr = s.pct_change()
        rets = market.close.pct_change()
        cov = rets.rolling(self.beta_window, min_periods=self.beta_window).cov(sr)
        var = sr.rolling(self.beta_window, min_periods=self.beta_window).var()
        beta = cov.div(var.replace(0, np.nan), axis=0)
        rising = s.pct_change(self.mom_window) > 0
        score = beta.mul(np.where(rising, 1.0, -1.0), axis=0)   # high beta when rising, low beta when falling
        rank = score.rank(axis=1, ascending=False, method="first")
        return state_signals(rank <= self.top_n, valid=beta.notna())


class CrossAssetAgreement(Strategy):
    """Long a stock only when its own momentum and two macro series' momentum all agree (positive)."""

    name = "cross_asset_agreement"

    def __init__(self, mom_window: int = 60, series_a: str = "brent", series_b: str = "spx") -> None:
        self.mom_window, self.series_a, self.series_b = mom_window, series_a, series_b

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series_a}', '{self.series_b}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        a = _series(market, self.series_a).pct_change(self.mom_window)
        b = _series(market, self.series_b).pct_change(self.mom_window)
        own = market.close.pct_change(self.mom_window)
        macro_ok = (a > 0) & (b > 0)
        long = own.gt(0) & pd.DataFrame(np.repeat(macro_ok.to_numpy()[:, None], own.shape[1], axis=1),
                                        index=own.index, columns=own.columns)
        return state_signals(long, valid=own.notna() & a.notna().to_numpy()[:, None] & b.notna().to_numpy()[:, None])


class RelativeToIndex(Strategy):
    """Long stocks whose trailing return beats the index series' trailing return."""

    name = "relative_to_index"

    def __init__(self, series: str = "obx", window: int = 63) -> None:
        self.series, self.window = series, window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        idx_ret = _series(market, self.series).pct_change(self.window)
        own = market.close.pct_change(self.window)
        long = own.gt(idx_ret, axis=0)
        return state_signals(long, valid=own.notna() & idx_ret.notna().to_numpy()[:, None])


class IndexDipBuy(Strategy):
    """Buy every stock when the index is ``drawdown`` below its rolling high; exit once it recovers."""

    name = "index_dip_buy"

    def __init__(self, series: str = "obx", drawdown: float = 0.08, window: int = 126, exit_dd: float = 0.01) -> None:
        self.series, self.drawdown, self.window, self.exit_dd = series, drawdown, window, exit_dd

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        s = _series(market, self.series)
        hi = s.rolling(self.window, min_periods=self.window // 2).max()
        dd = s / hi - 1
        enter = dd <= -self.drawdown
        exit_ = dd >= -self.exit_dd
        k = market.close.shape[1]
        rep = lambda x: pd.DataFrame(np.repeat(x.to_numpy()[:, None], k, axis=1), index=market.index, columns=market.close.columns)  # noqa: E731
        return enter_exit_signals(rep(enter), rep(exit_))


class VIXSpikeReversal(Strategy):
    """Buy every stock after VIX jumps ``spike`` (fraction) within 5 days; exit when VIX is back under its SMA."""

    name = "vix_spike_reversal"

    def __init__(self, spike: float = 0.30, window: int = 20, series: str = "vix") -> None:
        self.spike, self.window, self.series = spike, window, series

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        v = _series(market, self.series)
        spike = v / v.shift(5) - 1 >= self.spike
        calm = v < v.rolling(self.window, min_periods=self.window).mean()
        k = market.close.shape[1]
        rep = lambda x: pd.DataFrame(np.repeat(x.fillna(False).to_numpy()[:, None], k, axis=1), index=market.index, columns=market.close.columns)  # noqa: E731
        return enter_exit_signals(rep(spike), rep(calm & ~spike))


class USLeadLag(Strategy):
    """Long every stock when the S&P 500's last ``lookback``-day return is positive (US-to-Europe lead-lag)."""

    name = "us_lead_lag"

    def __init__(self, lookback: int = 1, series: str = "spx") -> None:
        self.lookback, self.series = lookback, series

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.extra['{self.series}']")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        ret = _series(market, self.series).pct_change(self.lookback)
        return _broadcast(ret > 0, market, valid=ret.notna())


MACRO_FAMILIES = [
    MacroTrendFilter, MacroLevelRegime, MacroBetaRotation, CrossAssetAgreement,
    RelativeToIndex, IndexDipBuy, VIXSpikeReversal, USLeadLag,
]
