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

    def __post_init__(self) -> None:
        ref = self.close
        for name in FIELDS:
            df = getattr(self, name)
            if df.shape != ref.shape or not df.index.equals(ref.index) or list(df.columns) != list(ref.columns):
                raise ValueError(f"MarketData field '{name}' is not aligned with close (shape/index/columns)")

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
        return MarketData(
            **{f: getattr(self, f).loc[start_ts:end_ts] for f in FIELDS},
            synthetic=self.synthetic,
            meta=dict(self.meta),
        )

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
    key = "ohlcv_" + "_".join(sorted(tickers)) + f"_{start}_{end}"
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
