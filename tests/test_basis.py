"""Cash-and-carry backtest on synthetic futures with a known basis."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from data.deribit import candidate_expiries, instrument_name, last_friday
from research.basis import BasisConfig, basis_panel, convergence_check, roll_backtest, summarize


def test_expiry_naming():
    assert last_friday(2024, 12) == date(2024, 12, 27)
    assert instrument_name(date(2024, 12, 27)) == "BTC-27DEC24"
    assert instrument_name(date(2025, 3, 7)) == "BTC-7MAR25"
    q = candidate_expiries(date(2024, 1, 1), date(2024, 12, 31), quarterly_only=True)
    assert [d.month for d in q] == [3, 6, 9, 12]


def _market(ann_basis: float, seed: int = 0):
    """Random-walk spot; each quarterly future = spot * (1 + ann_basis * dte/365)."""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2022-01-01", "2024-01-31", freq="D", tz="UTC")
    spot = pd.Series(30000 * np.exp(np.cumsum(rng.normal(0, 0.03, len(days)))), index=days)
    rows = []
    for e in candidate_expiries(date(2022, 3, 1), date(2023, 12, 31), quarterly_only=True):
        exp = pd.Timestamp(e, tz="UTC")
        live = days[(days >= exp - pd.Timedelta(days=200)) & (days <= exp)]
        dte = (exp - live).days
        rows.append(pd.DataFrame({"date": live, "instrument": instrument_name(e), "expiry": exp,
                                  "close": spot[live].to_numpy() * (1 + ann_basis * dte / 365),
                                  "volume": 1.0}))
    return pd.concat(rows, ignore_index=True), spot


def test_locked_pnl_ignores_price_path():
    fut, spot = _market(0.10)
    panel = basis_panel(fut, spot)
    res = roll_backtest(panel, spot, BasisConfig(), tenor="quarterly")
    tr = res["trades"]
    assert len(tr) >= 6 and tr["traded"].all() and (tr["direction"] == "carry").all()
    np.testing.assert_allclose(tr["pnl"], tr["realised_pnl"])
    cfg = BasisConfig()
    expected = tr["fut_entry"] - tr["spot_entry"] - cfg.round_trip_cost() * tr["spot_entry"]
    np.testing.assert_allclose(tr["pnl"], expected)
    # ~10% annualised basis minus ~1.4%/yr of quarterly costs, divided by 1.1 capital
    assert 0.06 < tr["ann_ret"].mean() < 0.09
    # Basis is a deterministic function of dte, so the hedged curve never draws down
    assert summarize(res)["max_mtm_drawdown"] > -0.01


def test_negative_basis_below_costs_is_skipped():
    fut, spot = _market(-0.01)
    res = roll_backtest(basis_panel(fut, spot), spot, BasisConfig(), tenor="quarterly")
    assert not res["trades"]["traded"].any()
    assert res["equity"].iloc[-1] == pytest.approx(1.0)


def test_reverse_trade_when_backwardation_is_deep():
    fut, spot = _market(-0.30)
    tr = roll_backtest(basis_panel(fut, spot), spot, BasisConfig(), tenor="quarterly")["trades"]
    assert (tr["direction"] == "reverse").all() and tr["traded"].all()
    assert (tr["pnl"] > 0).all()


def test_convergence_check_zero_gap():
    fut, spot = _market(0.05)
    conv = convergence_check(basis_panel(fut, spot), spot)
    assert len(conv) == 8
    assert conv["gap_bps"].abs().max() < 1e-6
