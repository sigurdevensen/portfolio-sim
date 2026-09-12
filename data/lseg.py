"""LSEG Workspace API data feed for historical prices, fundamentals, and index constituents."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import lseg.data as ld
except ImportError:
    ld = None  # type: ignore[assignment]

_LSEG_CACHE = Path(__file__).parent / "cache" / "lseg"
_LSEG_CACHE.mkdir(parents=True, exist_ok=True)

_FUNDAMENTAL_FIELDS = ["TR.PE", "TR.EPS", "TR.BookValuePerShare", "TR.CompanyMarketCap", "TR.DPS"]
_FUNDAMENTAL_FIELD_LABELS = ["P/E", "EPS", "BV/SH", "MKT_CAP", "DPS"]


class LSEGDataFeed:
    """Fetches market data from the LSEG Workspace API with local parquet caching.

    Requires the LSEG Workspace desktop application to be running.
    Falls back gracefully: raises RuntimeError with a clear message on session failure.
    """

    def __init__(self, use_cache: bool = True, cache_dir: Path | None = None) -> None:
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir) if cache_dir else _LSEG_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_prices(
        self,
        tickers: list[str],
        start: str,
        end: str,
        frequency: str = "daily",
    ) -> pd.DataFrame:
        """Fetch OHLCV close prices for the given tickers.

        Args:
            tickers: LSEG RIC codes (e.g. ["EQNR.OL", "DNB.OL"]).
            start: Start date string (YYYY-MM-DD).
            end: End date string (YYYY-MM-DD).
            frequency: "daily", "weekly", or "monthly".

        Returns:
            DataFrame with UTC DatetimeIndex and one column per ticker (close price).

        Raises:
            RuntimeError: If the LSEG Workspace session is unavailable.
        """
        cache_key = "_".join(sorted(tickers)) + f"_{start}_{end}_{frequency}"
        cache_path = self.cache_dir / f"prices_{cache_key}.parquet"

        if self.use_cache and cache_path.exists():
            return pd.read_parquet(cache_path)

        if ld is None:
            raise RuntimeError(
                "LSEG Workspace API not installed. Run: pip install lseg-data"
            )

        try:
            raw = ld.get_history(
                universe=tickers,
                fields=["TRDPRC_1", "OFF_CLOSE"],
                interval=frequency,
                start=start,
                end=end,
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        prices = self._normalise_price_df(raw, tickers)

        if self.use_cache:
            prices.to_parquet(cache_path)

        return prices

    def fetch_fundamentals(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch key fundamental data for each ticker.

        Args:
            tickers: LSEG RIC codes.

        Returns:
            Nested dict: {ticker: {field: value}}.

        Raises:
            RuntimeError: If the LSEG Workspace session is unavailable.
        """
        if ld is None:
            raise RuntimeError(
                "LSEG Workspace API not installed. Run: pip install lseg-data"
            )

        try:
            df = ld.get_data(
                universe=tickers,
                fields=_FUNDAMENTAL_FIELDS,
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        df.columns = _FUNDAMENTAL_FIELD_LABELS[: len(df.columns)]
        return {idx: row.to_dict() for idx, row in df.iterrows()}

    def fetch_index_constituents(self, index_ric: str) -> list[str]:
        """Fetch current constituent RICs for an index.

        Args:
            index_ric: LSEG index RIC (e.g. ".OSEBX").

        Returns:
            List of constituent RIC strings.

        Raises:
            RuntimeError: If the LSEG Workspace session is unavailable.
        """
        if ld is None:
            raise RuntimeError(
                "LSEG Workspace API not installed. Run: pip install lseg-data"
            )

        try:
            df = ld.get_data(
                universe=index_ric,
                fields=["TR.IndexConstituentRIC"],
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        col = "TR.IndexConstituentRIC"
        if col not in df.columns:
            return []
        return df[col].dropna().tolist()

    @staticmethod
    def _normalise_price_df(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
        """Extract close prices, handling both TRDPRC_1 and OFF_CLOSE column names."""
        raw.index = pd.to_datetime(raw.index, utc=True)

        if set(tickers).issubset(set(raw.columns)):
            # ld.get_history returned a column per ticker directly
            prices = raw[tickers].copy()
        else:
            # Multi-level or single-ticker with field columns
            prices = pd.DataFrame(index=raw.index)
            for ticker in tickers:
                if ticker in raw.columns:
                    prices[ticker] = raw[ticker]
                elif "TRDPRC_1" in raw.columns:
                    prices[ticker] = raw["TRDPRC_1"]
                elif "OFF_CLOSE" in raw.columns:
                    prices[ticker] = raw["OFF_CLOSE"]

        return prices
