"""LSEG Workspace API data feed for historical prices, fundamentals, and index constituents."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import lseg.data as ld
except ImportError:
    ld = None  # type: ignore[assignment]

_LSEG_CACHE = Path(__file__).parent / "cache" / "lseg"

_FUNDAMENTAL_FIELD_MAP = {
    "TR.PE": "P/E",
    "TR.EPS": "EPS",
    "TR.BookValuePerShare": "BV/SH",
    "TR.CompanyMarketCap": "MKT_CAP",
    "TR.DPS": "DPS",
}


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
        cache_key = "|".join(sorted(tickers)) + f"_{start}_{end}_{frequency}"
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
            Nested dict: {ticker: {label: value}} with human-readable field labels.

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
                fields=list(_FUNDAMENTAL_FIELD_MAP.keys()),
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        df = df.rename(columns=_FUNDAMENTAL_FIELD_MAP)
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
        """Extract close prices from ld.get_history() response.

        Expects columns named by ticker (TRDPRC_1 or OFF_CLOSE as fallback for single-ticker).
        Raises ValueError if multi-ticker response doesn't have per-ticker columns.
        """
        raw.index = pd.to_datetime(raw.index, utc=True)

        if set(tickers).issubset(set(raw.columns)):
            # Standard shape: one column per ticker
            return raw[tickers].copy()

        if len(tickers) == 1:
            # Single ticker with field columns: pick TRDPRC_1 or OFF_CLOSE
            ticker = tickers[0]
            for col in ("TRDPRC_1", "OFF_CLOSE"):
                if col in raw.columns:
                    return pd.DataFrame({ticker: raw[col]}, index=raw.index)
            raise ValueError(
                f"Cannot find close price column for {ticker}. "
                f"Available columns: {list(raw.columns)}"
            )

        raise ValueError(
            f"LSEG returned field-per-column response for {tickers}, "
            f"expected one column per ticker. Columns: {list(raw.columns)}"
        )
