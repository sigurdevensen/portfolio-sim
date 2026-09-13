"""Event-driven and short-horizon families: dividends and short-term reversal."""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.market import MarketData

from ._util import enter_exit_signals, state_signals
from .base import Strategy


def _dividends(market: MarketData) -> pd.DataFrame:
    if market.dividends is None:
        raise KeyError("Strategy needs MarketData.dividends (load the universe with dividends=True)")
    return market.dividends.reindex(index=market.index, columns=market.close.columns).fillna(0.0)


def _shift_flags(flags: pd.DataFrame, k: int) -> pd.DataFrame:
    """Boolean frame shifted by k rows (positive = later), False where undefined."""
    return flags.shift(k).fillna(False).astype(bool)


class DividendCapture(Strategy):
    """Enter ``days_before`` trading days before an ex-dividend date, exit ``days_after`` days after it."""

    name = "dividend_capture"

    def __init__(self, days_before: int = 5, days_after: int = 1) -> None:
        self.days_before, self.days_after = days_before, days_after

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.dividends")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        ex = _dividends(market) > 0
        enter = _shift_flags(ex, -self.days_before)   # ex-date is `days_before` rows ahead
        exit_ = _shift_flags(ex, self.days_after)
        return enter_exit_signals(enter, exit_)


class PostDividendReversal(Strategy):
    """Buy on the ex-dividend date (after the price drop) and hold ``hold`` trading days."""

    name = "post_dividend_reversal"

    def __init__(self, hold: int = 5) -> None:
        self.hold = hold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        raise KeyError(f"{self.name} needs MarketData.dividends")

    def generate_signals_market(self, market: MarketData) -> pd.DataFrame:
        ex = _dividends(market) > 0
        return enter_exit_signals(ex, _shift_flags(ex, self.hold))


class WeeklyReversal(Strategy):
    """Short-term reversal: hold the ``top_n`` worst performers over the last ``lookback`` days."""

    name = "weekly_reversal"

    def __init__(self, lookback: int = 5, top_n: int = 5) -> None:
        self.lookback, self.top_n = lookback, top_n

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        ret = data.pct_change(self.lookback)
        rank = ret.rank(axis=1, ascending=True, method="first")   # 1 = biggest loser
        return state_signals(rank <= self.top_n, valid=ret.notna())


EVENT_FAMILIES = [DividendCapture, PostDividendReversal, WeeklyReversal]
