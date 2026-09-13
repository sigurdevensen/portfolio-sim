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


ALGORITHMS: list[AlgoSpec] = _build_library()
BY_NAME: dict[str, AlgoSpec] = {a.name: a for a in ALGORITHMS}


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
) -> list[AlgoSpec]:
    fam = set(families) if families else None
    dts = set(data_types) if data_types else None
    nms = set(names) if names else None
    out = [
        a for a in ALGORITHMS
        if (fam is None or a.family in fam)
        and (dts is None or a.data_type in dts)
        and (nms is None or a.name in nms)
    ]
    return out[:limit] if limit else out
