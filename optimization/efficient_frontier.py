"""Mean-variance efficient frontier via Monte Carlo simulation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FrontierPoint:
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float


class EfficientFrontier:
    """Generate the efficient frontier for a set of assets.

    Usage::

        ef = EfficientFrontier(returns_df, n_portfolios=10_000)
        frontier = ef.compute()
        max_sharpe = ef.max_sharpe_portfolio()
    """

    def __init__(self, returns: pd.DataFrame, n_portfolios: int = 10_000, risk_free_rate: float = 0.0) -> None:
        self.returns = returns
        self.n_portfolios = n_portfolios
        self.risk_free_rate = risk_free_rate
        self._results: list[FrontierPoint] = []

    def compute(self) -> list[FrontierPoint]:
        """Simulate random portfolios and record their risk/return."""
        mu = self.returns.mean() * 252
        cov = self.returns.cov() * 252
        tickers = list(self.returns.columns)
        n = len(tickers)

        for _ in range(self.n_portfolios):
            w = np.random.dirichlet(np.ones(n))
            exp_ret = float(w @ mu)
            vol = float(np.sqrt(w @ cov.values @ w))
            sharpe = (exp_ret - self.risk_free_rate) / vol if vol > 0 else 0.0
            self._results.append(FrontierPoint(
                weights=dict(zip(tickers, w.tolist())),
                expected_return=exp_ret,
                volatility=vol,
                sharpe=sharpe,
            ))
        return self._results

    def max_sharpe_portfolio(self) -> FrontierPoint:
        if not self._results:
            self.compute()
        return max(self._results, key=lambda p: p.sharpe)

    def min_volatility_portfolio(self) -> FrontierPoint:
        if not self._results:
            self.compute()
        return min(self._results, key=lambda p: p.volatility)
