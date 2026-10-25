"""BTC futures basis (cash-and-carry) arbitrage backtest.

Trade: when a dated future trades above spot, buy 1 BTC spot and short 1 BTC of
the future; at expiry the future settles at the delivery price D and the spot is
sold at D, so the USD P&L is ``(D - S0) + (F0 - D) = F0 - S0`` regardless of
where BTC went. When the future trades *below* spot (backwardation) the reverse
trade (short spot, long future) locks ``S0 - F0`` but pays a borrow cost.

Deribit futures are inverse (BTC margined). Shorting USD face value ``F0`` per
BTC of spot gives futures P&L ``F0 * (1/D - 1/F0)`` BTC = ``F0 - D`` USD at
expiry, so the linear formula above is exact for a hold-to-expiry position.

All parameters are fixed a priori (see ``BasisConfig`` defaults); none were
tuned on the data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BasisConfig:
    spot_fee: float = 0.0010        # taker fee per spot trade (10 bps), paid on entry and exit
    futures_fee: float = 0.0005     # Deribit taker fee on entry (5 bps)
    delivery_fee: float = 0.00025   # Deribit delivery fee at expiry (2.5 bps)
    slippage: float = 0.0002        # per leg per trade (2 bps)
    margin: float = 0.10            # extra capital held as futures margin, fraction of notional
    borrow_rate: float = 0.05       # annual cost of borrowing BTC for the reverse trade
    min_edge: float = 0.0           # minimum annualised net locked return to enter
    allow_reverse: bool = True      # trade backwardation (short spot / long future)

    def round_trip_cost(self) -> float:
        """Fees + slippage as a fraction of spot notional for one full trade."""
        return 2 * self.spot_fee + self.futures_fee + self.delivery_fee + 4 * self.slippage


def basis_panel(futures: pd.DataFrame, spot: pd.Series) -> pd.DataFrame:
    """Join every futures close with the same-instant spot price."""
    p = futures.copy()
    p["spot"] = spot.reindex(p["date"]).to_numpy()
    p = p.dropna(subset=["spot", "close"])
    p["dte"] = (p["expiry"] - p["date"]).dt.days
    p = p[p["dte"] >= 0]  # dte == 0 is the last trade before the 08:00 settlement
    p["basis"] = p["close"] / p["spot"] - 1
    p["ann_basis"] = p["basis"] * 365 / p["dte"].clip(lower=1)
    return p.reset_index(drop=True)


def _trade(row: pd.Series, settle: float, cfg: BasisConfig, path: pd.DataFrame | None):
    """Evaluate one hold-to-expiry trade entered at ``row`` (per 1 BTC of spot)."""
    s0, f0, dte = row["spot"], row["close"], int(row["dte"])
    direction = 1 if f0 >= s0 else -1  # +1 cash-and-carry, -1 reverse
    gross = direction * (f0 - s0)
    costs = cfg.round_trip_cost() * s0
    borrow = cfg.borrow_rate * dte / 365 * s0 if direction < 0 else 0.0
    pnl = gross - costs - borrow
    capital = s0 * (1 + cfg.margin)
    out = {
        "instrument": row["instrument"], "entry": row["date"], "expiry": row["expiry"],
        "dte": dte, "direction": "carry" if direction > 0 else "reverse",
        "spot_entry": s0, "fut_entry": f0, "settle": settle,
        "basis": row["basis"], "ann_basis": row["ann_basis"],
        "gross_pnl": gross, "costs": costs + borrow, "pnl": pnl, "capital": capital,
        "ret": pnl / capital, "ann_ret": pnl / capital * 365 / dte,
        # check the identity: realised legs vs locked basis
        "realised_pnl": direction * ((settle - s0) - (settle - f0)) - costs - borrow,
    }
    if path is not None and len(path):
        # Mark-to-market of the open position: locked basis minus current basis.
        mtm = direction * ((f0 - s0) - (path["close"] - path["spot"])) - costs
        out["worst_mtm"] = float(mtm.min())
    return out


def roll_backtest(panel: pd.DataFrame, delivery: pd.Series, cfg: BasisConfig = BasisConfig(),
                  tenor: str = "quarterly", start: str | None = None) -> dict:
    """Continuously roll a basis position, holding each contract to expiry.

    On each roll date (the previous contract's expiry, 08:00 UTC) enter the
    contract chosen by ``tenor``:
      * ``"quarterly"`` - the next Mar/Jun/Sep/Dec expiry (~91 days),
      * ``"monthly"``   - the nearest expiry at least 20 days away.
    If the locked annualised net return is below ``cfg.min_edge`` (or the
    basis is negative and reverse trades are off) sit in cash until the next
    expiry. Returns trades and a daily mark-to-market equity curve (start 1.0).
    """
    expiries = sorted(panel["expiry"].unique())
    is_q = lambda e: pd.Timestamp(e).month in (3, 6, 9, 12)  # noqa: E731
    roll_dates = [e for e in expiries if is_q(e)] if tenor == "quarterly" else expiries
    if start is not None:
        roll_dates = [d for d in roll_dates if d >= pd.Timestamp(start, tz="UTC")]

    trades, curve, equity = [], [], 1.0
    for i, d in enumerate(roll_dates):
        today = panel[panel["date"] == d]
        if tenor == "quarterly":
            cand = today[today["expiry"].map(is_q) & (today["dte"] >= 60)]
        else:
            cand = today[today["dte"] >= 20]
        if cand.empty:
            continue
        row = cand.sort_values("dte").iloc[0]
        exp = row["expiry"]
        if exp not in delivery.index:
            break  # not yet expired
        path = panel[(panel["instrument"] == row["instrument"]) & (panel["date"] >= d)]
        t = _trade(row, float(delivery[exp]), cfg, path)
        nxt = next((r for r in roll_dates[i + 1:] if r >= exp), None)
        traded = t["ann_ret"] >= cfg.min_edge and (cfg.allow_reverse or t["direction"] == "carry")
        t["traded"] = traded
        trades.append(t)

        # Daily equity: units of BTC spot bought = equity / capital per BTC.
        days = pd.date_range(d, exp, freq="D", tz="UTC")
        if traded:
            q = equity / t["capital"]
            sgn = 1 if t["direction"] == "carry" else -1
            px = path.set_index("date")[["close", "spot"]].reindex(days).ffill()
            px.loc[exp, ["close", "spot"]] = t["settle"]
            carry = sgn * ((t["fut_entry"] - t["spot_entry"]) - (px["close"] - px["spot"]))
            borrow_accr = (cfg.borrow_rate * t["spot_entry"] * np.arange(len(days)) / 365
                           if sgn < 0 else 0.0)
            mtm = carry - cfg.round_trip_cost() * t["spot_entry"] - borrow_accr
            curve.append(equity + q * mtm)
            equity = equity + q * t["pnl"]
        else:
            curve.append(pd.Series(equity, index=days))
        if nxt is None:
            break

    eq = pd.concat(curve) if curve else pd.Series(dtype=float)
    eq = eq[~eq.index.duplicated(keep="last")].rename("equity")
    return {"trades": pd.DataFrame(trades), "equity": eq, "config": asdict(cfg), "tenor": tenor}


def summarize(result: dict, rf: pd.Series | None = None) -> dict:
    """Headline statistics for a roll backtest. ``rf`` is an annual T-bill yield
    (decimal) series used for the excess return / Sharpe."""
    eq, tr = result["equity"], result["trades"]
    if eq.empty:
        return {}
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    daily = eq.pct_change().dropna()
    rf_daily = (rf.reindex(daily.index).ffill().bfill() / 365) if rf is not None else 0.0
    ex = daily - rf_daily
    dd = eq / eq.cummax() - 1
    traded = tr[tr["traded"]] if len(tr) else tr
    out = {
        "start": eq.index[0].date().isoformat(), "end": eq.index[-1].date().isoformat(),
        "years": round(years, 2), "n_rolls": int(len(tr)), "n_traded": int(len(traded)),
        "n_reverse": int((traded["direction"] == "reverse").sum()) if len(traded) else 0,
        "total_return": float(eq.iloc[-1] - 1),
        "cagr": float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 else np.nan,
        "ann_vol": float(daily.std() * np.sqrt(365)),
        "sharpe_vs_rf": float(ex.mean() / ex.std() * np.sqrt(365)) if ex.std() > 0 else np.nan,
        "max_mtm_drawdown": float(dd.min()),
        "losing_trades": int((traded["pnl"] < 0).sum()) if len(traded) else 0,
        "mean_trade_ann_ret": float(traded["ann_ret"].mean()) if len(traded) else np.nan,
    }
    if rf is not None:
        rf_eq = (1 + rf.reindex(eq.index).ffill().bfill() / 365).cumprod()
        out["tbill_cagr"] = float((rf_eq.iloc[-1] / rf_eq.iloc[0]) ** (1 / years) - 1)
    return out


def convergence_check(panel: pd.DataFrame, delivery: pd.Series) -> pd.DataFrame:
    """Last trade before the 08:00 UTC settlement vs the delivery price: shows the
    future really converges to the index it is settled against."""
    last = panel[panel["dte"] == 0]
    last = last.assign(settle=last["expiry"].map(delivery))
    last["gap_bps"] = (last["close"] / last["settle"] - 1) * 1e4
    return last[["instrument", "expiry", "dte", "close", "settle", "gap_bps"]].dropna()
