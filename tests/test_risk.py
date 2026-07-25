"""Tests for risk module."""
import numpy as np
import pandas as pd
import pytest

from risk.var import value_at_risk, conditional_var
from risk.drawdown import drawdown_series, max_drawdown


def _returns(n: int = 1000, mu: float = 0.0, sigma: float = 0.01) -> pd.Series:
    np.random.seed(42)
    return pd.Series(np.random.normal(mu, sigma, n))


def test_var_historical_positive():
    r = _returns()
    var = value_at_risk(r, confidence=0.95, method="historical")
    assert var > 0


def test_var_parametric_close_to_historical():
    r = _returns(n=5000)
    hist = value_at_risk(r, confidence=0.95, method="historical")
    param = value_at_risk(r, confidence=0.95, method="parametric")
    assert abs(hist - param) < 0.005


def test_cvar_gt_var():
    r = _returns()
    var = value_at_risk(r, confidence=0.95, method="historical")
    cvar = conditional_var(r, confidence=0.95)
    assert cvar >= var


def test_var_unknown_method():
    with pytest.raises(ValueError):
        value_at_risk(_returns(), method="unknown")


def test_drawdown_series_non_positive():
    nav = pd.Series([100, 110, 95, 105, 115])
    dd = drawdown_series(nav)
    assert (dd <= 0).all()


def test_max_drawdown_known_series():
    nav = pd.Series([100.0, 120.0, 80.0, 100.0])
    assert max_drawdown(nav) == pytest.approx(-80 / 120 + 1 - 1, abs=1e-6)
