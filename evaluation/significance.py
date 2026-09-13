"""Statistical significance of a strategy's return series.

Three complementary views are produced:

* **Stationary bootstrap** (Politis & Romano) of the daily returns gives the
  sampling distribution of Sharpe and CAGR, hence confidence intervals. It answers
  "how uncertain is the estimate?".
* **Sign-flip randomisation test**: under the null hypothesis that returns are
  symmetric around zero, flipping the sign of each daily return at random yields
  the null distribution of the Sharpe ratio. The one-sided p-value is the share of
  null Sharpes at least as large as the observed one. (A plain shuffle would be
  useless here: Sharpe is invariant to the ordering of returns.)
* **Probabilistic Sharpe Ratio** (Bailey & Lopez de Prado, 2012): probability that
  the true Sharpe exceeds a benchmark Sharpe, adjusting for skew, kurtosis and
  sample length.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252
MIN_OBSERVATIONS = 30
HIST_BINS = 40


@dataclass
class SignificanceResult:
    observed_sharpe: float
    observed_cagr: float
    bootstrap_sharpe: np.ndarray
    bootstrap_cagr: np.ndarray
    sharpe_ci_95: tuple[float, float]
    cagr_ci_95: tuple[float, float]
    permutation_sharpe: np.ndarray
    p_value_sharpe: float
    prob_sharpe_ratio: float
    t_stat: float
    p_value_t: float
    n_samples: int
    n_observations: int

    def to_dict(self) -> dict:
        """JSON-safe representation with histograms instead of raw samples."""
        return {
            "observed_sharpe": float(self.observed_sharpe),
            "observed_cagr": float(self.observed_cagr),
            "sharpe_ci_95": [float(self.sharpe_ci_95[0]), float(self.sharpe_ci_95[1])],
            "cagr_ci_95": [float(self.cagr_ci_95[0]), float(self.cagr_ci_95[1])],
            "p_value_sharpe": float(self.p_value_sharpe),
            "prob_sharpe_ratio": float(self.prob_sharpe_ratio),
            "t_stat": float(self.t_stat),
            "p_value_t": float(self.p_value_t),
            "n_samples": int(self.n_samples),
            "n_observations": int(self.n_observations),
            "bootstrap_sharpe_hist": _histogram(self.bootstrap_sharpe),
            "bootstrap_cagr_hist": _histogram(self.bootstrap_cagr),
            "permutation_sharpe_hist": _histogram(self.permutation_sharpe),
            "bootstrap_sharpe_percentiles": _percentiles(self.bootstrap_sharpe),
            "bootstrap_cagr_percentiles": _percentiles(self.bootstrap_cagr),
        }


def analyse(
    returns: pd.Series,
    n_samples: int = 1000,
    block: int = 20,
    seed: int = 0,
    benchmark_sharpe: float = 0.0,
) -> SignificanceResult:
    """Run bootstrap, sign-flip and PSR analysis on a daily return series.

    Args:
        returns: Daily simple returns of the strategy.
        n_samples: Number of bootstrap / randomisation samples.
        block: Mean block length for the stationary bootstrap (trading days).
        seed: RNG seed; results are fully deterministic for a given seed.
        benchmark_sharpe: Annualised Sharpe the PSR is measured against.

    Raises:
        ValueError: If fewer than 30 non-missing observations are supplied.
    """
    r = np.asarray(returns.dropna(), dtype=float)
    n = len(r)
    if n < MIN_OBSERVATIONS:
        raise ValueError(f"Need at least {MIN_OBSERVATIONS} return observations, got {n}")
    if n_samples < 1:
        raise ValueError("n_samples must be >= 1")

    rng = np.random.default_rng(seed)

    observed_sharpe = float(_sharpe(r[None, :])[0])
    observed_cagr = float(_cagr(r[None, :])[0])

    idx = _stationary_bootstrap_indices(n, n_samples, block, rng)
    boot = r[idx]
    bootstrap_sharpe = _sharpe(boot)
    bootstrap_cagr = _cagr(boot)

    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_samples, n))
    permutation_sharpe = _sharpe(r[None, :] * signs)
    p_value_sharpe = float((np.sum(permutation_sharpe >= observed_sharpe) + 1) / (n_samples + 1))

    t_stat, p_value_t = stats.ttest_1samp(r, 0.0)

    return SignificanceResult(
        observed_sharpe=observed_sharpe,
        observed_cagr=observed_cagr,
        bootstrap_sharpe=bootstrap_sharpe,
        bootstrap_cagr=bootstrap_cagr,
        sharpe_ci_95=tuple(float(x) for x in np.percentile(bootstrap_sharpe, [2.5, 97.5])),
        cagr_ci_95=tuple(float(x) for x in np.percentile(bootstrap_cagr, [2.5, 97.5])),
        permutation_sharpe=permutation_sharpe,
        p_value_sharpe=p_value_sharpe,
        prob_sharpe_ratio=probabilistic_sharpe_ratio(r, benchmark_sharpe),
        t_stat=float(t_stat),
        p_value_t=float(p_value_t),
        n_samples=int(n_samples),
        n_observations=int(n),
    )


def probabilistic_sharpe_ratio(r: np.ndarray, benchmark_sharpe_annual: float = 0.0) -> float:
    """PSR: P(true Sharpe > benchmark) given skew, kurtosis and sample size.

    Works in per-period units; the annualised benchmark is de-annualised.
    """
    n = len(r)
    std = r.std(ddof=1)
    if std == 0 or n < 3:
        return 0.5
    sr = r.mean() / std
    sr_bench = benchmark_sharpe_annual / np.sqrt(TRADING_DAYS)
    g3 = stats.skew(r)
    g4 = stats.kurtosis(r, fisher=False)  # non-excess kurtosis (normal = 3)
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr**2
    if denom <= 0:
        return 0.5
    z = (sr - sr_bench) * np.sqrt(n - 1) / np.sqrt(denom)
    return float(stats.norm.cdf(z))


# ── vectorised helpers ─────────────────────────────────────────────────────

def _sharpe(samples: np.ndarray) -> np.ndarray:
    mean = samples.mean(axis=1)
    std = samples.std(axis=1, ddof=1)
    out = np.zeros_like(mean)
    np.divide(mean, std, out=out, where=std > 0)
    return out * np.sqrt(TRADING_DAYS)


def _cagr(samples: np.ndarray) -> np.ndarray:
    n = samples.shape[1]
    growth = np.prod(1 + samples, axis=1)
    growth = np.clip(growth, 1e-12, None)
    return growth ** (TRADING_DAYS / n) - 1


def _stationary_bootstrap_indices(
    n: int, n_samples: int, block: int, rng: np.random.Generator
) -> np.ndarray:
    """Index matrix (n_samples, n) for the stationary bootstrap.

    Each row is a sequence of blocks with geometric lengths (mean ``block``),
    wrapping around the end of the series.
    """
    p = 1.0 / max(block, 1)
    restart = rng.random((n_samples, n)) < p
    restart[:, 0] = True
    starts = rng.integers(0, n, size=(n_samples, n))
    positions = np.arange(n)[None, :]
    last_restart = np.maximum.accumulate(np.where(restart, positions, 0), axis=1)
    base = np.take_along_axis(starts, last_restart, axis=1)
    offset = positions - last_restart
    return (base + offset) % n


def _histogram(values: np.ndarray, bins: int = HIST_BINS) -> dict:
    counts, edges = np.histogram(values, bins=bins)
    return {"counts": counts.astype(int).tolist(), "edges": edges.astype(float).tolist()}


def _percentiles(values: np.ndarray) -> dict[str, float]:
    pts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    return {f"p{p}": float(v) for p, v in zip(pts, np.percentile(values, pts))}
