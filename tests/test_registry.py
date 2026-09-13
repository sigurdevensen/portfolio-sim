"""Tests for the strategy registry used by the web UI."""
from __future__ import annotations

import pytest

from strategies import Momentum
from web.registry import build, strategy_specs


def test_specs_include_all_registered_strategies():
    names = {s["name"] for s in strategy_specs()}
    assert {"buy_and_hold", "equal_weight", "momentum", "mean_reversion"} <= names


def test_momentum_spec_has_typed_params_with_defaults():
    spec = next(s for s in strategy_specs() if s["name"] == "momentum")
    params = {p["name"]: p for p in spec["params"]}
    assert params["lookback"] == {"name": "lookback", "type": "int", "default": 252}
    assert params["top_n"] == {"name": "top_n", "type": "int", "default": 3}


def test_spec_has_description():
    spec = next(s for s in strategy_specs() if s["name"] == "momentum")
    assert "momentum" in spec["description"].lower()


def test_build_with_params_coerces_types():
    strat = build("momentum", {"lookback": "20", "top_n": 2})
    assert isinstance(strat, Momentum)
    assert strat.lookback == 20
    assert strat.top_n == 2


def test_build_uses_defaults_when_params_missing():
    strat = build("momentum", {})
    assert strat.lookback == 252


def test_build_unknown_strategy_raises():
    with pytest.raises(ValueError, match="Unknown strategy"):
        build("nope", {})


def test_build_unknown_param_raises():
    with pytest.raises(ValueError, match="Unknown parameter"):
        build("momentum", {"bogus": 1})


def test_build_bad_type_raises():
    with pytest.raises(ValueError, match="lookback"):
        build("momentum", {"lookback": "abc"})
