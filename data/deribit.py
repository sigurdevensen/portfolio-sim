"""Deribit BTC dated-futures history (public API, no auth) plus BTC-USD spot.

Deribit lists only the most recent expired instruments, so contract names are
generated from the expiry convention instead: dated BTC futures expire on the
last Friday of the month at 08:00 UTC and are named ``BTC-27DEC24``. Candidates
that never existed simply return no candles and are dropped.

Deribit futures are inverse (USD face value, BTC margined) and settle at the
``btc_usd`` delivery price, a 30-minute TWAP of the index before 08:00 UTC.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from data.loader import CACHE_DIR, fetch_prices

API = "https://www.deribit.com/api/v2/public/"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
QUARTER_MONTHS = (3, 6, 9, 12)


def _get(method: str, **params) -> dict:
    url = API + method + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 400:  # unknown instrument: Deribit answers 400, not empty
                return json.load(exc)
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
        except Exception:  # noqa: BLE001 - transient network errors, retry
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def last_friday(year: int, month: int) -> date:
    nxt = date(year + month // 12, month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 4) % 7)


def instrument_name(expiry: date) -> str:
    return f"BTC-{expiry.day}{MONTHS[expiry.month - 1]}{expiry.year % 100:02d}"


def candidate_expiries(start: date, end: date, quarterly_only: bool = False) -> list[date]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        if not quarterly_only or m in QUARTER_MONTHS:
            exp = last_friday(y, m)
            if start <= exp <= end:
                out.append(exp)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def fetch_contract(name: str, expiry: date, lookback_days: int = 400) -> pd.DataFrame:
    """Daily candles for one dated future. Deribit daily candles run 08:00 -> 08:00
    UTC, so the index is relabelled to the *close* day: ``close`` on date D is the
    last trade before 08:00 UTC on D, the same instant as D's delivery price."""
    end = datetime.combine(expiry, datetime.min.time(), timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=lookback_days)
    res = _get("get_tradingview_chart_data", instrument_name=name,
               start_timestamp=int(start.timestamp() * 1000),
               end_timestamp=int(end.timestamp() * 1000), resolution="1D").get("result") or {}
    if res.get("status") != "ok" or not res.get("ticks"):
        return pd.DataFrame()
    df = pd.DataFrame({k: res[k] for k in ("open", "high", "low", "close", "volume")},
                      index=pd.to_datetime(res["ticks"], unit="ms", utc=True).normalize()
                      + pd.Timedelta(days=1))
    df.index.name = "date"
    return df[df["volume"] > 0]


def fetch_delivery_prices() -> pd.Series:
    """Daily ``btc_usd`` delivery (settlement) prices, indexed by UTC date."""
    rows, offset = [], 0
    while True:
        res = _get("get_delivery_prices", index_name="btc_usd", offset=offset, count=1000)["result"]
        rows += res["data"]
        offset += len(res["data"])
        if not res["data"] or offset >= res["records_total"]:
            break
    s = pd.Series({pd.Timestamp(r["date"], tz="UTC"): r["delivery_price"] for r in rows})
    return s.sort_index().rename("delivery_price")


def load_btc_basis_data(start: str = "2019-01-01", end: str | None = None,
                        use_cache: bool = True) -> dict:
    """Spot, delivery prices and every dated future expiring in [start, end].

    Returns ``{"spot": Series, "delivery": Series, "futures": DataFrame}`` where
    ``futures`` is long-format: date, instrument, expiry, close, volume.
    """
    end = end or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    path = CACHE_DIR / f"deribit_btc_futures_{start}_{end}.parquet"
    dpath = CACHE_DIR / "deribit_btc_delivery.parquet"

    if use_cache and path.exists():
        futures = pd.read_parquet(path)
    else:
        frames = []
        for exp in candidate_expiries(date.fromisoformat(start), date.fromisoformat(end)):
            name = instrument_name(exp)
            df = fetch_contract(name, exp)
            if df.empty:
                continue
            df = df[df.index.date <= exp]  # the expiry-day close is the last trade before settlement
            frames.append(df.assign(instrument=name, expiry=pd.Timestamp(exp, tz="UTC")))
        futures = pd.concat(frames).reset_index()[
            ["date", "instrument", "expiry", "close", "volume"]]
        futures.to_parquet(path)

    if use_cache and dpath.exists() and pd.read_parquet(dpath).index.max() >= pd.Timestamp(end, tz="UTC"):
        delivery = pd.read_parquet(dpath)["delivery_price"]
    else:
        delivery = fetch_delivery_prices()
        delivery.to_frame().to_parquet(dpath)

    # Spot at 08:00 UTC: the Deribit index (delivery price) is daily from Feb 2020;
    # before that fill with yfinance BTC-USD, whose bar for D-1 closes at 00:00 UTC
    # on D (8h earlier than the futures close - flagged via ``spot_source``).
    yf_close = fetch_prices(["BTC-USD"], start,
                            (date.fromisoformat(end) + timedelta(days=1)).isoformat(),
                            use_cache=use_cache)["BTC-USD"].dropna()
    yf_close.index = yf_close.index.normalize() + pd.Timedelta(days=1)
    idx = pd.date_range(start, end, freq="D", tz="UTC")
    index08 = delivery.reindex(idx)
    spot = index08.fillna(yf_close.reindex(idx)).rename("spot")
    source = pd.Series("deribit_index", index=idx).where(index08.notna(), "yfinance_00utc")
    return {"spot": spot, "spot_source": source, "delivery": delivery, "futures": futures}
