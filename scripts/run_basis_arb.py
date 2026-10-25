"""BTC cash-and-carry backtest: spot vs Deribit dated futures, held to expiry.

    python scripts/run_basis_arb.py --output reports/basis_arb
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.deribit import load_btc_basis_data  # noqa: E402
from data.loader import fetch_prices  # noqa: E402
from research.basis import (BasisConfig, basis_panel, convergence_check,  # noqa: E402
                            roll_backtest, summarize)

BLUE, ORANGE, GREY, INK, MUTED = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e"
# First quarterly roll with a same-instant (08:00 UTC) daily spot index for the
# mark-to-market; 2019 trades are exact at trade level but their daily marks are not.
HEADLINE_START = "2020-03-27"


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8)


def _pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--output", default="reports/basis_arb")
    args = ap.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)

    data = load_btc_basis_data(args.start, args.end)
    panel = basis_panel(data["futures"], data["spot"])
    end = panel["date"].max()
    rf = fetch_prices(["^IRX"], args.start, (end + pd.Timedelta(days=1)).date().isoformat())["^IRX"]
    rf = rf.dropna() / 100
    rf.index = rf.index.normalize()

    cfg = BasisConfig()
    runs = {t: roll_backtest(panel, data["delivery"], cfg, tenor=t, start=HEADLINE_START)
            for t in ("quarterly", "monthly")}
    stats = {t: summarize(r, rf) for t, r in runs.items()}
    full_q = roll_backtest(panel, data["delivery"], cfg, tenor="quarterly")

    sens = []
    for label, c in [("no costs", replace(cfg, spot_fee=0, futures_fee=0, delivery_fee=0, slippage=0)),
                     ("default costs", cfg),
                     ("2x costs", replace(cfg, spot_fee=2 * cfg.spot_fee, futures_fee=2 * cfg.futures_fee,
                                          delivery_fee=2 * cfg.delivery_fee, slippage=2 * cfg.slippage)),
                     ("carry only (no reverse)", replace(cfg, allow_reverse=False)),
                     ("always trade (min_edge=-inf)", replace(cfg, min_edge=float("-inf"))),
                     ("no margin buffer", replace(cfg, margin=0.0))]:
        for t in ("quarterly", "monthly"):
            s = summarize(roll_backtest(panel, data["delivery"], c, tenor=t, start=HEADLINE_START), rf)
            sens.append({"scenario": label, "tenor": t, "cagr": s["cagr"], "sharpe_vs_rf": s["sharpe_vs_rf"],
                         "max_mtm_drawdown": s["max_mtm_drawdown"], "n_traded": s["n_traded"]})
    sens = pd.DataFrame(sens)
    conv = convergence_check(panel, data["delivery"])

    # ---- data exports --------------------------------------------------------
    panel.to_csv(out / "basis_panel.csv", index=False)
    data["spot"].rename("spot_08utc").to_frame().join(data["spot_source"].rename("source")).to_csv(
        out / "btc_spot_08utc.csv")
    for t, r in runs.items():
        r["trades"].to_csv(out / f"trades_{t}.csv", index=False)
    full_q["trades"].to_csv(out / "trades_quarterly_from_2019.csv", index=False)
    sens.to_csv(out / "sensitivity.csv", index=False)

    # ---- charts ----------------------------------------------------------------
    # Basis series only where spot is the same-instant 08:00 index (daily from Feb 2020).
    exact = data["spot_source"][data["spot_source"] == "deribit_index"].index
    q = panel[panel["expiry"].dt.month.isin([3, 6, 9, 12]) & (panel["dte"] >= 7)
              & panel["date"].isin(exact) & (panel["date"] >= exact[exact.to_series().diff().dt.days.gt(1)].max())]
    front = q.sort_values("dte").groupby("date").head(1).set_index("date").sort_index()
    m = panel[(panel["dte"] >= 7) & panel["date"].isin(q["date"])].sort_values("dte").groupby("date").head(1).set_index("date").sort_index()
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(m.index, m["ann_basis"].rolling(7).median() * 100, color=ORANGE, lw=1.2,
            label="nearest expiry (7d median)")
    ax.plot(front.index, front["ann_basis"].rolling(7).median() * 100, color=BLUE, lw=1.6,
            label="front quarterly (7d median)")
    rf_c = rf[rf.index >= front.index[0]]
    ax.plot(rf_c.index, rf_c * 100, color=GREY, lw=1.2, ls="--", label="3m T-bill")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylabel("annualised basis, %", color=MUTED, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style(ax, "BTC futures basis vs spot (Deribit, 08:00 UTC)")
    fig.tight_layout(); fig.savefig(out / "basis.png", dpi=140); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 3.6))
    for t, col in (("quarterly", BLUE), ("monthly", ORANGE)):
        e = runs[t]["equity"]
        ax.plot(e.index, e, color=col, lw=1.6, label=f"{t} roll  CAGR {_pct(stats[t]['cagr'])}")
    e = runs["quarterly"]["equity"]
    tb = (1 + rf.reindex(e.index).ffill().bfill() / 365).cumprod()
    ax.plot(tb.index, tb / tb.iloc[0], color=GREY, lw=1.2, ls="--",
            label=f"3m T-bills  CAGR {_pct(stats['quarterly']['tbill_cagr'])}")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_ylabel("growth of 1", color=MUTED, fontsize=9)
    _style(ax, "Cash-and-carry equity (mark-to-market, after costs)")
    fig.tight_layout(); fig.savefig(out / "equity.png", dpi=140); plt.close(fig)

    tr = full_q["trades"]
    fig, ax = plt.subplots(figsize=(10, 3.2))
    cols = [BLUE if (r.traded and r.ann_ret >= 0) else (ORANGE if r.traded else "#d6d5d0")
            for r in tr.itertuples()]
    ax.bar(tr["expiry"], tr["ann_ret"] * 100, width=60, color=cols)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylabel("annualised net return, %", color=MUTED, fontsize=9)
    _style(ax, "Per-contract locked return, quarterly roll (grey = skipped: basis below costs)")
    fig.tight_layout(); fig.savefig(out / "trades.png", dpi=140); plt.close(fig)

    # ---- markdown report -------------------------------------------------------
    def stat_rows():
        keys = [("start", "Start"), ("end", "End"), ("n_rolls", "Roll dates"), ("n_traded", "Trades taken"),
                ("n_reverse", "Reverse (backwardation) trades"), ("total_return", "Total return"),
                ("cagr", "CAGR"), ("tbill_cagr", "3m T-bill CAGR"), ("ann_vol", "Volatility (MTM)"),
                ("sharpe_vs_rf", "Sharpe vs T-bills"), ("max_mtm_drawdown", "Max MTM drawdown"),
                ("losing_trades", "Losing trades held to expiry"), ("mean_trade_ann_ret", "Mean trade ann. return")]
        pct = {"total_return", "cagr", "tbill_cagr", "ann_vol", "max_mtm_drawdown", "mean_trade_ann_ret"}
        rows = []
        for k, lab in keys:
            v = [stats[t][k] for t in ("quarterly", "monthly")]
            f = (lambda x: _pct(x, 2)) if k in pct else (lambda x: f"{x:.2f}" if isinstance(x, float) else str(x))
            rows.append(f"| {lab} | {f(v[0])} | {f(v[1])} |")
        return "\n".join(rows)

    tq = full_q["trades"]
    trade_rows = "\n".join(
        f"| {r.instrument} | {r.entry.date()} | {r.direction} | {r.spot_entry:,.0f} | {r.fut_entry:,.0f} | "
        f"{r.settle:,.0f} | {_pct(r.basis, 2)} | {_pct(r.ann_basis)} | {r.pnl:,.0f} | {_pct(r.ann_ret)} | "
        f"{'yes' if r.traded else 'skip'} |" for r in tq.itertuples())
    sens_rows = "\n".join(
        f"| {r.scenario} | {r.tenor} | {_pct(r.cagr, 2)} | {r.sharpe_vs_rf:.2f} | {_pct(r.max_mtm_drawdown)} | {r.n_traded} |"
        for r in sens.itertuples())
    by_year = front["ann_basis"].groupby(front.index.year).mean()
    year_rows = "\n".join(f"| {y} | {_pct(v)} | {_pct(rf[rf.index.year == y].mean())} |" for y, v in by_year.items())

    md = f"""# BTC cash-and-carry arbitrage: spot vs Deribit dated futures

**Trade.** On each roll date buy 1 BTC spot and short 1 BTC of a dated future
(or the reverse when the future trades below spot), hold to expiry, and collect
the basis `F0 - S0`. At expiry the future settles at the Deribit delivery price
(30-min TWAP of the BTC index to 08:00 UTC) and the spot is sold at that price,
so the BTC price move cancels.

**Data.** {panel['instrument'].nunique()} Deribit BTC dated futures expiring
{panel['expiry'].min().date()} - {panel['expiry'].max().date()} (daily closes at
08:00 UTC, public API), Deribit `btc_usd` index at 08:00 UTC as spot (daily from
Feb 2020; yfinance BTC-USD before that), 3-month T-bill (`^IRX`) as the hurdle.

**Costs (fixed a priori).** spot taker {_pct(cfg.spot_fee, 2)} x2, futures taker
{_pct(cfg.futures_fee, 2)}, delivery {_pct(cfg.delivery_fee, 3)}, slippage
{_pct(cfg.slippage, 2)} per leg x4 = **{_pct(cfg.round_trip_cost(), 3)} of notional per
round trip**. Capital = spot cost + {_pct(cfg.margin, 0)} futures margin buffer.
Reverse trades pay {_pct(cfg.borrow_rate, 0)}/yr to borrow BTC. A trade is skipped (cash
earns 0) when the locked net return is below {cfg.min_edge:.0%}.

## Headline (rolls from {HEADLINE_START})

| | Quarterly roll | Monthly roll |
|---|---:|---:|
{stat_rows()}

![equity](equity.png)

![basis](basis.png)

## Front-quarterly annualised basis by year

| Year | Mean ann. basis | Mean 3m T-bill |
|---|---:|---:|
{year_rows}

## Sensitivity

| Scenario | Tenor | CAGR | Sharpe vs T-bills | Max MTM DD | Trades |
|---|---|---:|---:|---:|---:|
{sens_rows}

## Every quarterly contract since 2019 (P&L per 1 BTC, USD)

![trades](trades.png)

| Contract | Entry | Side | Spot | Future | Settle | Basis | Ann. | Net P&L | Ann. ret | Taken |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
{trade_rows}

## Does the future converge?

Last trade before settlement vs delivery price over {len(conv)} expiries: median
gap {conv['gap_bps'].median():.1f} bps, mean {conv['gap_bps'].mean():.1f} bps,
worst {conv['gap_bps'].abs().max():.1f} bps. Held to expiry the basis is locked; the
only path risk is mark-to-market (the basis can widen before it converges) and
margin on the short future.

## Caveats

- Counterparty / exchange risk (Deribit, the spot venue) is the real risk of this
  trade and is not priced here; the 2022 FTX collapse is the canonical example.
- The inverse (BTC-margined) contract makes the hedge exact only at expiry if the
  short is sized to `F0` USD face per BTC; intra-trade margin is in BTC.
- Daily closes are last trades, so thin monthly contracts can carry stale prints
  (affects the MTM curve, not the hold-to-expiry P&L which uses the delivery price).
- Spot is assumed sold exactly at the delivery TWAP; in practice you would TWAP
  the spot sale over the same window and incur small tracking error.
- Idle cash and the margin buffer earn nothing here; in practice they would earn
  roughly the T-bill rate, which raises the strategy's return.
"""
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md[:1800])
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
