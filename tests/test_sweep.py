"""Tests for parameter grid search over a strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from optimization.sweep import SweepResult, expand_grid, grid_search


def _prices(n: int = 150, tickers=("AAA", "BBB")) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    return pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, n)) for t in tickers}, index=idx)


def test_expand_grid_cartesian_product():
    combos = expand_grid({"lookback": [10, 20], "top_n": [1, 2]})
    assert len(combos) == 4
    assert {"lookback": 20, "top_n": 1} in combos


def test_expand_grid_empty_gives_single_empty_combo():
    assert expand_grid({}) == [{}]


def test_grid_search_returns_one_row_per_combo():
    res = grid_search("momentum", {"lookback": [10, 20], "top_n": [1, 2]}, _prices(), initial_capital=10_000)
    assert isinstance(res, SweepResult)
    assert len(res.table) == 4
    for col in ("lookback", "top_n", "sharpe", "cagr", "max_drawdown", "total_return", "n_trades"):
        assert col in res.table.columns


def test_grid_search_sorted_by_objective_desc():
    res = grid_search("momentum", {"lookback": [10, 20, 40]}, _prices(), objective="sharpe", initial_capital=10_000)
    sharpe = res.table["sharpe"].tolist()
    assert sharpe == sorted(sharpe, reverse=True)
    assert res.best["lookback"] == res.table.iloc[0]["lookback"]


def test_grid_search_objective_max_drawdown_uses_least_negative_first():
    res = grid_search("momentum", {"lookback": [10, 20]}, _prices(), objective="max_drawdown", initial_capital=10_000)
    dd = res.table["max_drawdown"].tolist()
    assert dd == sorted(dd, reverse=True)


def test_grid_search_unknown_objective_raises():
    with pytest.raises(ValueError, match="objective"):
        grid_search("momentum", {"lookback": [10]}, _prices(), objective="nope")


def test_grid_search_records_failures_instead_of_raising():
    # lookback longer than the data -> no trades, still a row (not an exception)
    res = grid_search("momentum", {"lookback": [10, 5000]}, _prices(), initial_capital=10_000)
    assert len(res.table) == 2


def test_sweep_result_to_dict_json_safe():
    import json
    res = grid_search("momentum", {"lookback": [10, 20]}, _prices(), initial_capital=10_000)
    d = res.to_dict()
    json.dumps(d)
    assert d["objective"] == "sharpe"
    assert len(d["rows"]) == 2
    assert d["best"]["lookback"] in (10, 20)
