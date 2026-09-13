"""The algorithm library: 100+ fixed-parameter trading algorithms.

Every entry is an ``AlgoSpec`` — a strategy family, a parameter set chosen a priori
from textbook defaults, and optional stop settings. Nothing here is tuned to data;
that is the point. The batch runner tests all of them at once and the edge
statistics correct for the number of trials.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from strategies.base import Strategy
from web.registry import build

DATA_TYPES: dict[str, str] = {
    # price-only
    "buy_and_hold": "price", "equal_weight": "price", "sma_cross": "price", "ema_cross": "price",
    "price_vs_sma": "price", "macd": "price", "rsi_reversal": "price", "rsi_trend": "price",
    "bollinger_reversion": "price", "bollinger_breakout": "price", "roc_momentum": "price",
    "ts_momentum": "price", "mean_reversion": "price", "vol_regime": "price", "buy_the_dip": "price",
    "streak_reversal": "price", "random": "price",
    # open/high/low
    "keltner_breakout": "ohlc", "stochastic": "ohlc", "donchian_breakout": "ohlc",
    "atr_breakout": "ohlc", "gap_reversal": "ohlc",
    # volume
    "volume_breakout": "volume", "obv_trend": "volume", "volume_z_reversal": "volume",
    # calendar
    "turn_of_month": "calendar", "day_of_week": "calendar", "sell_in_may": "calendar",
    # universe-relative
    "low_volatility": "cross_sectional", "dual_momentum": "cross_sectional",
    "relative_strength": "cross_sectional", "high_52w": "cross_sectional", "momentum": "cross_sectional",
    "weekly_reversal": "cross_sectional",
    # external / macro series
    "macro_trend": "macro", "macro_level": "macro", "macro_beta_rotation": "macro",
    "cross_asset_agreement": "macro", "relative_to_index": "macro", "index_dip_buy": "macro",
    "vix_spike_reversal": "macro", "us_lead_lag": "macro",
    # corporate actions
    "dividend_capture": "events", "post_dividend_reversal": "events", "dividend_yield_rank": "events",
    # documented anomalies
    "low_beta_rank": "macro", "long_term_reversal": "cross_sectional", "relative_vol_regime": "price",
    "sector_momentum": "sector", "illiquidity_rank": "volume",
    "same_month_seasonality": "calendar", "low_max_return": "price", "low_idio_vol": "macro",
    "high_volume_premium": "volume",
}


@dataclass(frozen=True)
class AlgoSpec:
    name: str
    family: str
    params: dict[str, Any] = field(default_factory=dict)
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop: float | None = None
    data_type: str = "price"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "family": self.family, "params": dict(self.params),
            "stop_loss": self.stop_loss, "take_profit": self.take_profit,
            "trailing_stop": self.trailing_stop, "data_type": self.data_type,
        }


def _label(value: Any) -> str:
    s = str(value).replace(".", "p").replace(",", "").replace("-", "m")
    return s


def _spec(family: str, params: dict[str, Any], stop_loss=None, take_profit=None, trailing_stop=None) -> AlgoSpec:
    parts = [family] + [_label(v) for v in params.values()]
    if stop_loss is not None:
        parts.append(f"sl{int(round(stop_loss * 100))}")
    if take_profit is not None:
        parts.append(f"tp{int(round(take_profit * 100))}")
    if trailing_stop is not None:
        parts.append(f"ts{int(round(trailing_stop * 100))}")
    return AlgoSpec(
        name="_".join(parts), family=family, params=dict(params),
        stop_loss=stop_loss, take_profit=take_profit, trailing_stop=trailing_stop,
        data_type=DATA_TYPES.get(family, "price"),
    )


def _variants(family: str, param_sets: Iterable[dict[str, Any]], **stops) -> list[AlgoSpec]:
    return [_spec(family, p, **stops) for p in param_sets]


def _build_library() -> list[AlgoSpec]:
    lib: list[AlgoSpec] = []
    P = lambda **kw: kw  # noqa: E731 - compact param-set literal

    # ── baselines ─────────────────────────────────────────────────────────
    lib += [_spec("buy_and_hold", {})]
    lib += _variants("equal_weight", [P(rebalance_freq="M"), P(rebalance_freq="Q")])

    # ── trend following (price) ───────────────────────────────────────────
    sma_sets = [P(fast=10, slow=30), P(fast=20, slow=50), P(fast=50, slow=200), P(fast=20, slow=100), P(fast=5, slow=20)]
    lib += _variants("sma_cross", sma_sets)
    lib += _variants("sma_cross", [P(fast=20, slow=50), P(fast=50, slow=200)], stop_loss=0.10)
    lib += _variants("ema_cross", [P(fast=12, slow=26), P(fast=20, slow=50), P(fast=8, slow=21)])
    lib += _variants("ema_cross", [P(fast=12, slow=26)], stop_loss=0.10)
    lib += _variants("price_vs_sma", [P(window=50), P(window=100), P(window=200)])
    lib += _variants("price_vs_sma", [P(window=200)], trailing_stop=0.15)
    lib += _variants("macd", [P(fast=12, slow=26, signal=9), P(fast=5, slow=35, signal=5), P(fast=19, slow=39, signal=9)])
    lib += _variants("roc_momentum", [P(window=21), P(window=63), P(window=126), P(window=252)])
    lib += _variants("ts_momentum", [P(lookback=252, skip=21), P(lookback=126, skip=21), P(lookback=63, skip=5)])
    lib += _variants("ts_momentum", [P(lookback=252, skip=21)], stop_loss=0.10)

    # ── oscillators / mean reversion (price) ──────────────────────────────
    lib += _variants("rsi_reversal", [P(window=14, lower=30.0, upper=70.0), P(window=14, lower=25.0, upper=75.0),
                                      P(window=7, lower=20.0, upper=80.0), P(window=21, lower=35.0, upper=65.0)])
    lib += _variants("rsi_reversal", [P(window=14, lower=30.0, upper=70.0)], stop_loss=0.10)
    lib += _variants("rsi_trend", [P(window=14, threshold=50.0), P(window=14, threshold=55.0), P(window=28, threshold=50.0)])
    lib += _variants("bollinger_reversion", [P(window=20, n_std=2.0), P(window=20, n_std=2.5), P(window=10, n_std=1.5)])
    lib += _variants("bollinger_reversion", [P(window=20, n_std=2.0)], stop_loss=0.10)
    lib += _variants("bollinger_breakout", [P(window=20, n_std=2.0), P(window=50, n_std=2.0), P(window=20, n_std=1.5)])
    lib += _variants("bollinger_breakout", [P(window=20, n_std=2.0)], trailing_stop=0.15)
    lib += _variants("mean_reversion", [P(window=20, z_threshold=1.5), P(window=20, z_threshold=2.0), P(window=10, z_threshold=1.0)])
    lib += _variants("mean_reversion", [P(window=20, z_threshold=1.5)], stop_loss=0.10)

    # ── OHLC based ────────────────────────────────────────────────────────
    lib += _variants("keltner_breakout", [P(window=20, atr_window=10, mult=2.0), P(window=20, atr_window=10, mult=1.5),
                                          P(window=50, atr_window=14, mult=2.0)])
    lib += _variants("stochastic", [P(k=14, d=3, lower=20.0, upper=80.0), P(k=21, d=5, lower=20.0, upper=80.0),
                                    P(k=14, d=3, lower=30.0, upper=70.0)])
    lib += _variants("donchian_breakout", [P(entry=20, exit=10), P(entry=55, exit=20), P(entry=100, exit=50)])
    lib += _variants("donchian_breakout", [P(entry=55, exit=20)], stop_loss=0.10)
    lib += _variants("donchian_breakout", [P(entry=20, exit=10)], trailing_stop=0.15)
    lib += _variants("atr_breakout", [P(window=20, mult=1.5), P(window=20, mult=2.5), P(window=50, mult=2.0)])
    lib += _variants("gap_reversal", [P(gap=0.01), P(gap=0.02), P(gap=0.03)])

    # ── volume based ──────────────────────────────────────────────────────
    lib += _variants("volume_breakout", [P(price_window=20, vol_window=20, vol_mult=1.5),
                                         P(price_window=50, vol_window=20, vol_mult=2.0),
                                         P(price_window=10, vol_window=10, vol_mult=1.5)])
    lib += _variants("volume_breakout", [P(price_window=20, vol_window=20, vol_mult=1.5)], stop_loss=0.10)
    lib += _variants("obv_trend", [P(window=10), P(window=20), P(window=50)])
    lib += _variants("volume_z_reversal", [P(window=20, z=2.0, exit_window=10), P(window=20, z=2.5, exit_window=5),
                                           P(window=60, z=2.0, exit_window=10)])

    # ── cross-sectional ───────────────────────────────────────────────────
    lib += _variants("momentum", [P(lookback=252, top_n=3), P(lookback=126, top_n=2), P(lookback=63, top_n=3)])
    lib += _variants("momentum", [P(lookback=126, top_n=2)], trailing_stop=0.15)
    lib += _variants("low_volatility", [P(window=60, top_n=3), P(window=126, top_n=2), P(window=20, top_n=3)])
    lib += _variants("dual_momentum", [P(lookback=126, top_n=2), P(lookback=252, top_n=2), P(lookback=63, top_n=3)])
    lib += _variants("relative_strength", [P(window=21), P(window=63), P(window=126)])
    lib += _variants("high_52w", [P(window=252, threshold=0.95, exit_threshold=0.85),
                                  P(window=252, threshold=0.98, exit_threshold=0.90),
                                  P(window=126, threshold=0.95, exit_threshold=0.85)])
    lib += _variants("high_52w", [P(window=252, threshold=0.95, exit_threshold=0.85)], trailing_stop=0.15)

    # ── calendar ──────────────────────────────────────────────────────────
    lib += _variants("turn_of_month", [P(days_before=1, days_after=3), P(days_before=2, days_after=2), P(days_before=3, days_after=5)])
    lib += _variants("day_of_week", [P(long_days="1,2,3,4"), P(long_days="0,1,2,3"), P(long_days="2,3,4")])
    lib += _variants("sell_in_may", [P(long_months="11,12,1,2,3,4"), P(long_months="10,11,12,1,2,3,4,5")])

    # ── regime / dip / reversal ───────────────────────────────────────────
    lib += _variants("vol_regime", [P(window=20, threshold=0.20), P(window=20, threshold=0.30), P(window=60, threshold=0.25)])
    lib += _variants("buy_the_dip", [P(drawdown=0.10, window=126, exit_dd=0.02), P(drawdown=0.05, window=63, exit_dd=0.01),
                                     P(drawdown=0.20, window=252, exit_dd=0.05)])
    lib += _variants("buy_the_dip", [P(drawdown=0.10, window=126, exit_dd=0.02)], stop_loss=0.10)
    lib += _variants("streak_reversal", [P(down_days=2), P(down_days=3), P(down_days=4)])

    # ── random controls (must NOT show edge) ──────────────────────────────
    lib += _variants("random", [P(seed=s, p_long=0.5, hold=5) for s in range(5)])

    names = [a.name for a in lib]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise RuntimeError(f"Duplicate algorithm names in library: {dupes}")
    return lib


def _build_oslo_library() -> list[AlgoSpec]:
    """Universe-specific ideas that need external series or dividends.

    Designed for Oslo (oil, NOK, seafood dividends) but valid for any universe whose
    MarketData carries the same extras. Parameters are a priori, as in the base library.
    """
    lib: list[AlgoSpec] = []
    P = lambda **kw: kw  # noqa: E731

    # Oil is the OSE macro factor: long the exchange only when Brent trends up (and the inverse control)
    lib += _variants("macro_trend", [P(series="brent", window=20, direction=1), P(series="brent", window=60, direction=1),
                                     P(series="brent", window=120, direction=1), P(series="brent", window=60, direction=-1),
                                     P(series="wti", window=60, direction=1)])
    # NOK: weaker krone (usdnok up) helps exporters; both directions tested
    lib += _variants("macro_trend", [P(series="usdnok", window=60, direction=1), P(series="usdnok", window=60, direction=-1),
                                     P(series="eurnok", window=60, direction=1)])
    # Global risk appetite and rates
    lib += _variants("macro_trend", [P(series="spx", window=60, direction=1), P(series="spx", window=120, direction=1),
                                     P(series="stoxx50", window=60, direction=1), P(series="vix", window=20, direction=-1),
                                     P(series="us10y", window=60, direction=-1), P(series="copper", window=60, direction=1),
                                     P(series="gold", window=60, direction=1), P(series="natgas", window=60, direction=1)])
    lib += _variants("macro_trend", [P(series="brent", window=60, direction=1)], stop_loss=0.10)
    # Level regimes
    lib += _variants("macro_level", [P(series="vix", threshold=20.0, below=True), P(series="vix", threshold=25.0, below=True),
                                     P(series="vix", threshold=30.0, below=True), P(series="us10y", threshold=3.0, below=True),
                                     P(series="brent", threshold=60.0, below=False), P(series="usdnok", threshold=8.5, below=False)])
    # Sector rotation on macro beta
    lib += _variants("macro_beta_rotation", [P(series="brent", beta_window=120, mom_window=60, top_n=5),
                                             P(series="brent", beta_window=250, mom_window=120, top_n=8),
                                             P(series="usdnok", beta_window=120, mom_window=60, top_n=5),
                                             P(series="spx", beta_window=120, mom_window=60, top_n=5),
                                             P(series="brent", beta_window=120, mom_window=20, top_n=3)])
    # Agreement between own momentum and two macro drivers
    lib += _variants("cross_asset_agreement", [P(mom_window=60, series_a="brent", series_b="spx"),
                                               P(mom_window=120, series_a="brent", series_b="spx"),
                                               P(mom_window=60, series_a="obx", series_b="spx"),
                                               P(mom_window=60, series_a="brent", series_b="usdnok")])
    # Relative strength against the OBX index
    lib += _variants("relative_to_index", [P(series="obx", window=21), P(series="obx", window=63), P(series="obx", window=126),
                                           P(series="stoxx50", window=63)])
    # Index-level dip buying and fear spikes
    lib += _variants("index_dip_buy", [P(series="obx", drawdown=0.05, window=63, exit_dd=0.01),
                                       P(series="obx", drawdown=0.10, window=126, exit_dd=0.02),
                                       P(series="obx", drawdown=0.15, window=252, exit_dd=0.03),
                                       P(series="spx", drawdown=0.10, window=126, exit_dd=0.02)])
    lib += _variants("vix_spike_reversal", [P(spike=0.20, window=20), P(spike=0.30, window=20), P(spike=0.50, window=40)])
    # US close leads the Oslo session
    lib += _variants("us_lead_lag", [P(lookback=1), P(lookback=2), P(lookback=5)])
    # Corporate actions: Norwegian dividend season is concentrated and generous
    lib += _variants("dividend_capture", [P(days_before=5, days_after=1), P(days_before=10, days_after=0),
                                          P(days_before=20, days_after=0), P(days_before=2, days_after=2)])
    lib += _variants("post_dividend_reversal", [P(hold=3), P(hold=5), P(hold=10), P(hold=20)])
    lib += _variants("sell_in_may", [P(long_months="3,4,5"), P(long_months="2,5,8,11"), P(long_months="12,1,2,3,4,5")])
    # Short-term reversal (price only, but new)
    lib += _variants("weekly_reversal", [P(lookback=5, top_n=3), P(lookback=5, top_n=5), P(lookback=10, top_n=5)])

    # ── round 2: documented anomalies (added after round 1; N grows accordingly) ──
    lib += _variants("dividend_yield_rank", [P(window=252, top_n=5), P(window=252, top_n=8), P(window=504, top_n=8)])
    lib += _variants("low_beta_rank", [P(series="obx", window=252, top_n=5, direction=1),
                                       P(series="obx", window=252, top_n=8, direction=1),
                                       P(series="obx", window=126, top_n=8, direction=1),
                                       P(series="obx", window=252, top_n=8, direction=-1)])   # high-beta control
    lib += _variants("long_term_reversal", [P(lookback=756, skip=21, top_n=5), P(lookback=504, skip=21, top_n=5),
                                            P(lookback=756, skip=21, top_n=8)])
    lib += _variants("relative_vol_regime", [P(window=20, ref_window=252), P(window=10, ref_window=252),
                                             P(window=60, ref_window=504)])

    # ── round 3: sector classification and liquidity data ────────────────────────
    lib += _variants("sector_momentum", [P(lookback=126, top_k=2, skip=21), P(lookback=252, top_k=2, skip=21),
                                         P(lookback=126, top_k=3, skip=21), P(lookback=63, top_k=2, skip=5)])
    lib += _variants("illiquidity_rank", [P(window=252, top_n=5), P(window=252, top_n=8), P(window=126, top_n=8)])

    # ── round 6: further documented anomalies ─────────────────────────────────────
    lib += _variants("same_month_seasonality", [P(years=3, top_n=5), P(years=5, top_n=5), P(years=3, top_n=8)])
    lib += _variants("low_max_return", [P(window=21, top_n=8), P(window=21, top_n=5), P(window=63, top_n=8)])
    lib += _variants("low_idio_vol", [P(series="obx", window=63, top_n=8), P(series="obx", window=126, top_n=5),
                                      P(series="obx", window=252, top_n=8)])
    lib += _variants("high_volume_premium", [P(window=50, quantile=0.9, hold=20), P(window=50, quantile=0.95, hold=10),
                                             P(window=100, quantile=0.9, hold=20)])

    names = [a.name for a in lib]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise RuntimeError(f"Duplicate algorithm names in oslo library: {dupes}")
    return lib


ALGORITHMS: list[AlgoSpec] = _build_library()
OSLO_ALGORITHMS: list[AlgoSpec] = _build_oslo_library()
BY_NAME: dict[str, AlgoSpec] = {a.name: a for a in ALGORITHMS + OSLO_ALGORITHMS}

UNIVERSE_ADDITIONS: dict[str, list[AlgoSpec]] = {"oslo": OSLO_ALGORITHMS, "us10": OSLO_ALGORITHMS}


def library_for(universe: str | None) -> list[AlgoSpec]:
    """Base library plus the additions that a universe's external data makes possible."""
    if universe is None:
        return list(ALGORITHMS)
    return list(ALGORITHMS) + list(UNIVERSE_ADDITIONS.get(universe, []))


def build_algorithm(spec: AlgoSpec) -> Strategy:
    """Instantiate the strategy for a spec and attach its stop settings."""
    strat = build(spec.family, spec.params)
    strat.stop_loss = spec.stop_loss
    strat.take_profit = spec.take_profit
    strat.trailing_stop = spec.trailing_stop
    return strat


def families() -> list[str]:
    return sorted({a.family for a in ALGORITHMS})


def filter_algorithms(
    families: Iterable[str] | None = None,
    data_types: Iterable[str] | None = None,
    names: Iterable[str] | None = None,
    limit: int | None = None,
    universe: str | None = None,
) -> list[AlgoSpec]:
    fam = set(families) if families else None
    dts = set(data_types) if data_types else None
    nms = set(names) if names else None
    out = [
        a for a in library_for(universe)
        if (fam is None or a.family in fam)
        and (dts is None or a.data_type in dts)
        and (nms is None or a.name in nms)
    ]
    return out[:limit] if limit else out
