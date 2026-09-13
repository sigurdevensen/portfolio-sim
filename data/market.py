"""OHLCV market data container and loader.

``MarketData`` holds one wide DataFrame per field (columns = tickers, UTC index)
so strategies can use open, high, low, close or volume. ``from_close`` synthesises
the other fields from closes alone, so strategies still run when only closes are
available (the result is flagged ``synthetic``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

FIELDS = ("open", "high", "low", "close", "volume")
_MAX_KEY_LEN = 80


def cache_key(prefix: str, *parts: str) -> str:
    """Filesystem-safe cache file stem; long keys are hashed to dodge Windows path limits."""
    import hashlib
    raw = "_".join(str(x) for x in parts)
    raw = raw.replace("/", "-").replace("\\", "-").replace(":", "-").replace("^", "").replace("=", "")
    if len(raw) > _MAX_KEY_LEN:
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        raw = raw[:40] + "_" + digest
    return f"{prefix}_{raw}"
_YF_FIELDS = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
CACHE_DIR = Path(__file__).parent / "cache"


@dataclass
class MarketData:
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    synthetic: bool = False
    meta: dict = field(default_factory=dict)
    extra: dict[str, pd.Series | pd.DataFrame] = field(default_factory=dict)
    dividends: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        ref = self.close
        for name in FIELDS:
            df = getattr(self, name)
            if df.shape != ref.shape or not df.index.equals(ref.index) or list(df.columns) != list(ref.columns):
                raise ValueError(f"MarketData field '{name}' is not aligned with close (shape/index/columns)")

    # ── external data ─────────────────────────────────────────────────────

    def attach_extra(self, name: str, data: pd.Series | pd.DataFrame) -> None:
        """Attach an external series/frame, aligned to the trading index and forward-filled."""
        idx = self.close.index
        data = data.copy()
        data.index = pd.to_datetime(data.index, utc=True)
        data = data[~data.index.duplicated(keep="last")].sort_index()
        # union-reindex first so values published on non-trading days carry forward
        aligned = data.reindex(data.index.union(idx)).ffill().reindex(idx)
        if isinstance(aligned, pd.Series):
            aligned.name = name
        self.extra[name] = aligned

    def require_extra(self, *names: str) -> None:
        missing = [n for n in names if n not in self.extra]
        if missing:
            raise KeyError(
                f"MarketData is missing external series {missing}; available: {sorted(self.extra)}. "
                "Load the universe with research.universes.load_universe() or attach_extra()."
            )

    # ── convenience ────────────────────────────────────────────────────────

    @property
    def tickers(self) -> list[str]:
        return [str(c) for c in self.close.columns]

    @property
    def index(self) -> pd.DatetimeIndex:
        return self.close.index

    def field(self, name: str) -> pd.DataFrame:
        if name not in FIELDS:
            raise KeyError(name)
        return getattr(self, name)

    def slice(self, start: str | pd.Timestamp | None = None, end: str | pd.Timestamp | None = None) -> "MarketData":
        start_ts = pd.Timestamp(start, tz="UTC") if start is not None and pd.Timestamp(start).tzinfo is None else start
        end_ts = pd.Timestamp(end, tz="UTC") if end is not None and pd.Timestamp(end).tzinfo is None else end
        out = MarketData(
            **{f: getattr(self, f).loc[start_ts:end_ts] for f in FIELDS},
            synthetic=self.synthetic,
            meta=dict(self.meta),
        )
        out.extra = {k: v.loc[start_ts:end_ts] for k, v in self.extra.items()}
        if self.dividends is not None:
            out.dividends = self.dividends.loc[start_ts:end_ts]
        return out

    @classmethod
    def from_close(cls, close: pd.DataFrame) -> "MarketData":
        """Build a full OHLCV bundle from closes only.

        open = previous close (first bar = close), high/low = max/min of open and
        close widened by 0.5 %, volume = constant 1.0. Marked ``synthetic``.
        """
        close = close.astype(float)
        open_ = close.shift(1).fillna(close)
        spread = close.abs() * 0.005
        high = np.maximum(open_, close) + spread
        low = np.minimum(open_, close) - spread
        volume = pd.DataFrame(1.0, index=close.index, columns=close.columns)
        return cls(open=open_, high=high, low=low, close=close, volume=volume, synthetic=True)


def fetch_market_data(
    tickers: list[str],
    start: str,
    end: str,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> MarketData:
    """Download adjusted daily OHLCV for ``tickers`` via yfinance with a parquet cache.

    The cache stores a single wide frame with columns ``"<field>|<ticker>"``.
    """
    cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key("ohlcv", "_".join(sorted(tickers)), start, end)
    cache_path = cache_dir / f"{key}.parquet"

    if use_cache and cache_path.exists():
        wide = pd.read_parquet(cache_path)
        return _from_wide(wide, tickers)

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"No market data returned for {tickers} between {start} and {end}")

    frames: dict[str, pd.DataFrame] = {}
    for fld, yf_name in _YF_FIELDS.items():
        if isinstance(raw.columns, pd.MultiIndex):
            part = raw[yf_name].copy()
            part.columns = [str(c) for c in part.columns]
            part = part.reindex(columns=tickers)
        else:  # single ticker, flat columns
            part = raw[[yf_name]].rename(columns={yf_name: tickers[0]})
        part.index = pd.to_datetime(part.index, utc=True)
        frames[fld] = part.astype(float)

    wide = pd.concat({f: frames[f] for f in FIELDS}, axis=1)
    wide.columns = [f"{f}|{t}" for f, t in wide.columns]
    if use_cache:
        wide.to_parquet(cache_path)
    return _from_wide(wide, tickers)


def _from_wide(wide: pd.DataFrame, tickers: list[str]) -> MarketData:
    frames = {}
    for f in FIELDS:
        cols = [f"{f}|{t}" for t in tickers]
        df = wide.reindex(columns=cols).copy()
        df.columns = tickers
        frames[f] = df
    idx = pd.to_datetime(frames["close"].index, utc=True)
    for df in frames.values():
        df.index = idx
    return MarketData(**frames, synthetic=False)


# ── external series and dividends ─────────────────────────────────────────

def fetch_external(
    symbols: dict[str, str],
    start: str,
    end: str,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Download closes for named external symbols, e.g. ``{"brent": "BZ=F"}``.

    Returns a UTC-indexed DataFrame with one column per name (not per raw symbol).
    """
    cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    names = list(symbols)
    key = cache_key("external", "_".join(sorted(names)), start, end)
    cache_path = cache_dir / f"{key}.parquet"
    if use_cache and cache_path.exists():
        return pd.read_parquet(cache_path)

    raw_symbols = [symbols[n] for n in names]
    raw = yf.download(raw_symbols, start=start, end=end, auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"No external data returned for {raw_symbols}")
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
        close.columns = [str(c) for c in close.columns]
    else:
        close = raw[["Close"]].rename(columns={"Close": raw_symbols[0]})
    out = pd.DataFrame({n: close.get(symbols[n]) for n in names})
    out.index = pd.to_datetime(out.index, utc=True)
    out = out.astype(float)
    if use_cache:
        out.to_parquet(cache_path)
    return out


def fetch_dividends(
    tickers: list[str],
    index: pd.DatetimeIndex,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Dividend per share on the ex-date for each ticker, aligned to ``index`` (0 elsewhere).

    Ex-dates falling on non-trading days are moved to the next trading day.
    """
    cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key("dividends", "_".join(sorted(tickers)), str(index[0].date()), str(index[-1].date()))
    cache_path = cache_dir / f"{key}.parquet"
    if use_cache and cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached.index = pd.to_datetime(cached.index, utc=True)
        return cached.reindex(index).fillna(0.0)[tickers]

    out = pd.DataFrame(0.0, index=index, columns=tickers)
    positions = index.tz_convert(None).normalize() if index.tz is not None else index.normalize()
    for t in tickers:
        try:
            dv = yf.Ticker(t).dividends
        except Exception:
            continue
        if dv is None or len(dv) == 0:
            continue
        dates = pd.to_datetime(dv.index)
        dates = (dates.tz_localize(None) if dates.tz is not None else dates).normalize()  # keep wall-clock date
        for d, amount in zip(dates, dv.to_numpy(dtype=float)):
            pos = positions.searchsorted(d)  # first trading day >= ex-date
            if 0 <= pos < len(index):
                out.iloc[pos, out.columns.get_loc(t)] += float(amount)
    if use_cache:
        out.to_parquet(cache_path)
    return out
