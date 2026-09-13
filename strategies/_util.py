"""Shared indicator and signal-shaping helpers for strategy families."""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── signal shaping ─────────────────────────────────────────────────────────

def state_signals(long: pd.DataFrame, valid: pd.DataFrame | None = None) -> pd.DataFrame:
    """1 where ``long`` is True, -1 where False and data is valid, 0 during warm-up.

    ``valid`` marks rows/cells where the indicator is defined; defaults to the
    non-NaN cells of ``long`` before it is filled.
    """
    if valid is None:
        valid = long.notna()
    long_bool = long.fillna(False).astype(bool)
    out = np.where(long_bool, 1, np.where(valid, -1, 0))
    return pd.DataFrame(out, index=long.index, columns=long.columns).astype(int)


def enter_exit_signals(enter: pd.DataFrame, exit_: pd.DataFrame) -> pd.DataFrame:
    """1 on entry conditions, -1 on exit conditions, 0 otherwise (exit wins ties)."""
    enter_b = enter.fillna(False).astype(bool)
    exit_b = exit_.fillna(False).astype(bool)
    out = np.where(exit_b, -1, np.where(enter_b, 1, 0))
    return pd.DataFrame(out, index=enter.index, columns=enter.columns).astype(int)


# ── indicators ─────────────────────────────────────────────────────────────

def sma(x: pd.DataFrame, window: int) -> pd.DataFrame:
    return x.rolling(window, min_periods=window).mean()


def ema(x: pd.DataFrame, span: int) -> pd.DataFrame:
    out = x.ewm(span=span, adjust=False, min_periods=span).mean()
    return out


def rsi(close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(loss > 0, 100.0)  # no losses at all -> RSI 100
    return out.where(gain.notna())


def true_range(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    prev_close = close.shift(1)
    a = high - low
    b = (high - prev_close).abs()
    c = (low - prev_close).abs()
    tr = np.maximum(np.maximum(a.to_numpy(), b.to_numpy()), c.to_numpy())
    return pd.DataFrame(tr, index=close.index, columns=close.columns)


def atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    tr = true_range(high, low, close)
    return tr.rolling(window, min_periods=window).mean()


def rolling_vol(close: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    return close.pct_change().rolling(window, min_periods=window).std() * np.sqrt(252)


def zscore(x: pd.DataFrame, window: int) -> pd.DataFrame:
    mu = x.rolling(window, min_periods=window).mean()
    sd = x.rolling(window, min_periods=window).std()
    return (x - mu) / sd.replace(0, np.nan)


def last_trading_day_of_period(index: pd.DatetimeIndex, freq: str = "M") -> np.ndarray:
    """Boolean mask: True on the last trading day of each period (freq 'W','M','Q','Y')."""
    freq = {"ME": "M", "QE": "Q", "YE": "Y", "A": "Y"}.get(freq, freq)
    naive = index.tz_convert(None) if index.tz is not None else index
    per = naive.to_period(freq)
    nxt = np.append(per[1:], [per[-1]]) if len(per) else per
    mask = np.array(per != nxt)
    if len(mask):
        mask[-1] = True
    return mask
