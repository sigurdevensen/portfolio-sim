"""Named stock universes with their external data, fixed before any testing.

The universe list is part of the experimental design: it is chosen a priori and
must not be edited after looking at results (that would be another form of
selection). Tickers without yfinance history are simply dropped at load time.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from data.market import MarketData, fetch_dividends, fetch_external, fetch_market_data

# External series available to strategies via market.extra[name]
MACRO_SYMBOLS: dict[str, str] = {
    "brent": "BZ=F",        # Brent crude front month
    "wti": "CL=F",
    "usdnok": "USDNOK=X",   # NOK per USD (up = NOK weaker)
    "eurnok": "EURNOK=X",
    "vix": "^VIX",
    "spx": "^GSPC",
    "us10y": "^TNX",        # US 10-year yield (%)
    "gold": "GC=F",
    "copper": "HG=F",
    "natgas": "NG=F",
    "obx": "OBX.OL",        # Oslo Børs OBX index
    "stoxx50": "^STOXX50E",
}

# Hand-assigned GICS-like sectors for the Oslo universe (a priori, public knowledge).
OSLO_SECTORS: dict[str, str] = {
    "EQNR.OL": "energy", "AKRBP.OL": "energy", "SUBC.OL": "energy_services", "TGS.OL": "energy_services",
    "AKSO.OL": "energy_services", "ODL.OL": "energy_services", "BWLPG.OL": "shipping", "FRO.OL": "shipping",
    "MOWI.OL": "seafood", "SALM.OL": "seafood", "LSG.OL": "seafood", "AUSS.OL": "seafood", "BAKKA.OL": "seafood",
    "GSF.OL": "seafood", "DNB.OL": "financials", "STB.OL": "financials", "GJF.OL": "financials",
    "MING.OL": "financials", "NONG.OL": "financials", "PROT.OL": "financials", "YAR.OL": "materials",
    "NHY.OL": "materials", "TOM.OL": "industrials", "VEI.OL": "industrials", "AFG.OL": "industrials",
    "KIT.OL": "industrials", "BONHR.OL": "industrials", "KOG.OL": "industrials", "WAWI.OL": "consumer",
    "ORK.OL": "consumer", "NAS.OL": "consumer", "ATEA.OL": "technology", "NOD.OL": "technology",
    "TEL.OL": "telecom", "SCATC.OL": "renewables", "ENTRA.OL": "real_estate",
}

UNIVERSES: dict[str, dict[str, Any]] = {
    "oslo": {
        "description": "28 Oslo Stock Exchange large/mid caps with yfinance history from 2008-2014: "
                       "energy, seafood, banks, shipping, industrials, telecom, technology.",
        "tickers": [
            "EQNR.OL", "DNB.OL", "TEL.OL", "MOWI.OL", "YAR.OL", "NHY.OL", "ORK.OL", "AKRBP.OL",
            "SUBC.OL", "KOG.OL", "SALM.OL", "TGS.OL", "STB.OL", "GJF.OL", "NOD.OL", "TOM.OL",
            "FRO.OL", "BAKKA.OL", "LSG.OL", "AUSS.OL", "ENTRA.OL", "NAS.OL", "BWLPG.OL", "ATEA.OL",
            "VEI.OL", "PROT.OL", "KIT.OL", "AFG.OL", "BONHR.OL", "WAWI.OL", "AKSO.OL", "MING.OL",
            "NONG.OL", "GSF.OL", "ODL.OL", "SCATC.OL",
        ],
        "extra": MACRO_SYMBOLS,
        "dividends": True,
        "sectors": OSLO_SECTORS,
        "default_start": "2010-01-01",
    },
    "oslo_holdout": {
        "description": "Replication universe fixed AFTER the search on 'oslo' and BEFORE any test on it: "
                       "OSEAX all-share members (LSEG chain, 2026-09-13) that were not in 'oslo', with "
                       "yfinance history from before mid-2016 and >= 2000 trading days. Used only to "
                       "confirm or refute pre-registered hypotheses.",
        "tickers": [
            "ACR.OL", "AFK.OL", "AKAST.OL", "AKER.OL", "AKVA.OL", "AZT.OL", "BNOR.OL", "BOR.OL", "BOUV.OL",
            "BWO.OL", "CONTX.OL", "DNO.OL", "EIOF.OL", "ENH.OL", "GOD.OL", "GYL.OL", "HAVI.OL", "HEX.OL",
            "IOX.OL", "ITERA.OL", "KOA.OL", "MEDI.OL", "MGN.OL", "NAVA.OL", "NEL.OL", "NKR.OL", "NOM.OL",
            "NRC.OL", "ODF.OL", "ODFB.OL", "OTEC.OL", "PHO.OL", "POL.OL", "PSE.OL", "QEC.OL", "REACH.OL",
            "SB1NO.OL", "SCANA.OL", "SNI.OL", "SOFF.OL", "STRO.OL", "TECH.OL", "VOIM.OL", "VVL.OL", "WWI.OL",
            "WWIB.OL", "ENSU.OL", "ENDUR.OL", "IDEX.OL", "BINT.OL", "SDSD.OL", "HBC.OL", "NAPA.OL", "VOW.OL",
            "ZAL.OL", "NEXT.OL", "EQVA.OL", "TRMED.OL", "MULTI.OL", "VEND.OL", "VISTN.OL", "EPR.OL", "KID.OL",
            "PARB.OL", "B2I.OL",
        ],
        "extra": {k: MACRO_SYMBOLS[k] for k in ("brent", "usdnok", "vix", "spx", "obx")},
        "dividends": False,
        "default_start": "2010-01-01",
        "min_adv_nok": 200_000.0,   # a priori: exclude names too thin to trade at all
    },
    "us10": {
        "description": "10 US mega-caps.",
        "tickers": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM", "JNJ", "PG"],
        "extra": {k: MACRO_SYMBOLS[k] for k in ("brent", "vix", "spx", "us10y", "gold", "copper")},
        "dividends": True,
        "default_start": "2015-01-01",
    },
}


def universe_tickers(name: str) -> list[str]:
    return list(UNIVERSES[name]["tickers"])


def load_universe(
    name: str,
    start: str | None = None,
    end: str = "2024-12-31",
    use_cache: bool = True,
    min_history_days: int = 500,
) -> MarketData:
    """Fetch OHLCV for the universe plus its external series and dividends."""
    spec = UNIVERSES[name]
    start = start or spec["default_start"]
    market = fetch_market_data(spec["tickers"], start, end, use_cache=use_cache)

    # Drop tickers with too little history or corrupt data; keep the survivors' order.
    counts = market.close.notna().sum()
    bad_price = (market.close <= 0).any()
    adv = (market.close * market.volume).mean()
    min_adv = float(spec.get("min_adv_nok", 0.0))
    keep = [
        t for t in market.tickers
        if counts.get(t, 0) >= min_history_days and not bool(bad_price.get(t, False))
        and (min_adv <= 0 or (pd.notna(adv.get(t)) and adv.get(t) >= min_adv))
    ]
    dropped = [t for t in market.tickers if t not in keep]
    if keep != market.tickers:
        market = MarketData(
            **{f: getattr(market, f)[keep] for f in ("open", "high", "low", "close", "volume")},
            synthetic=market.synthetic, meta=dict(market.meta),
        )

    if spec.get("extra"):
        ext = fetch_external(spec["extra"], start, end, use_cache=use_cache)
        for col in ext.columns:
            if ext[col].notna().any():
                market.attach_extra(col, ext[col])
    if spec.get("dividends"):
        market.dividends = fetch_dividends(keep, market.index, use_cache=use_cache)

    market.meta.update({"universe": name, "description": spec["description"], "dropped": dropped})
    if spec.get("sectors"):
        market.meta["sectors"] = {t: spec["sectors"].get(t, "other") for t in keep}
    return market
