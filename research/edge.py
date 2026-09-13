"""Mathematics for deciding whether any of N tested algorithms has a real edge.

Everything operates on a matrix ``R`` of daily strategy returns (T days x N
algorithms). The single-strategy tests in ``evaluation/significance.py`` are not
enough once many strategies are compared: the best of N noise strategies has an
expected Sharpe that grows like sqrt(2 ln N). This module supplies the corrections:

* Benjamini-Hochberg and Holm adjustments of the N per-strategy p-values.
* Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014): PSR against the expected
  maximum Sharpe of N trials.
* White's Reality Check (2000): a joint stationary bootstrap over all strategies
  giving the null distribution of the *best* performance.
* Probability of Backtest Overfitting via CSCV (Bailey, Borwein, Lopez de Prado,
  Zhu 2017).
* Block stability and Minimum Track Record Length.

``assess`` combines them into a leaderboard with an ``edge`` verdict per algorithm
and a batch-level summary.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from evaluation.significance import _stationary_bootstrap_indices

TRADING_DAYS = 252
EULER_GAMMA = 0.5772156649015329
MIN_DAYS = 120


# ── p-value adjustments ────────────────────────────────────────────────────

def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    """BH step-up adjusted p-values (control the false discovery rate)."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adj_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    adj = np.empty(n)
    adj[order] = np.clip(adj_sorted, 0, 1)
    return adj


def holm(p: np.ndarray) -> np.ndarray:
    """Holm step-down adjusted p-values (control the family-wise error rate)."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * (n - np.arange(n))
    adj_sorted = np.maximum.accumulate(ranked)
    adj = np.empty(n)
    adj[order] = np.clip(adj_sorted, 0, 1)
    return adj


# ── Sharpe utilities (per-period units unless stated) ──────────────────────

def _sharpe_period(r: np.ndarray) -> np.ndarray:
    """Per-period Sharpe of each column of a (T x N) matrix."""
    mean = r.mean(axis=0)
    std = r.std(axis=0, ddof=1)
    out = np.zeros_like(mean)
    np.divide(mean, std, out=out, where=std > 0)
    return out


def _psr(r: np.ndarray, sr_bench: np.ndarray | float) -> np.ndarray:
    """Probabilistic Sharpe Ratio of each column against a per-period benchmark Sharpe."""
    n = r.shape[0]
    sr = _sharpe_period(r)
    g3 = stats.skew(r, axis=0)
    g4 = stats.kurtosis(r, axis=0, fisher=False)
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr**2
    denom = np.where(denom <= 0, np.nan, denom)
    z = (sr - sr_bench) * np.sqrt(n - 1) / np.sqrt(denom)
    out = stats.norm.cdf(z)
    return np.where(np.isnan(out), 0.5, out)


def expected_max_sharpe(n_trials: int, var_sharpe: float) -> float:
    """Expected maximum per-period Sharpe of ``n_trials`` independent zero-mean trials.

    Bailey & Lopez de Prado (2014), eq. for E[max SR] using the Euler-Mascheroni
    approximation. Returns 0 for a single trial.
    """
    if n_trials <= 1 or var_sharpe <= 0:
        return 0.0
    z1 = stats.norm.ppf(1 - 1 / n_trials)
    z2 = stats.norm.ppf(1 - 1 / (n_trials * math.e))
    return float(math.sqrt(var_sharpe) * ((1 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe_ratio(r: np.ndarray, n_trials: int | None = None) -> np.ndarray:
    """DSR of every column: PSR evaluated against E[max SR] of the trial set."""
    r = np.asarray(r, dtype=float)
    n_trials = n_trials or r.shape[1]
    sr = _sharpe_period(r)
    var_sr = float(np.var(sr, ddof=1)) if len(sr) > 1 else 0.0
    sr_max = expected_max_sharpe(n_trials, var_sr)
    return _psr(r, sr_max)


def min_track_record_length(r: np.ndarray, sr_bench_annual: float = 0.0, confidence: float = 0.95) -> float:
    """Days of history needed for PSR >= confidence given the observed moments."""
    r = np.asarray(r, dtype=float)
    std = r.std(ddof=1)
    if std == 0:
        return np.inf
    sr = r.mean() / std
    sr_b = sr_bench_annual / math.sqrt(TRADING_DAYS)
    if sr <= sr_b:
        return np.inf
    g3 = stats.skew(r)
    g4 = stats.kurtosis(r, fisher=False)
    z = stats.norm.ppf(confidence)
    return float(1 + (1 - g3 * sr + (g4 - 1) / 4 * sr**2) * (z / (sr - sr_b)) ** 2)


# ── White's Reality Check ──────────────────────────────────────────────────

def reality_check(
    r: np.ndarray,
    benchmark: np.ndarray | None = None,
    n_boot: int = 1000,
    block: int = 20,
    seed: int = 0,
) -> dict[str, Any]:
    """Bootstrap the distribution of the best strategy's mean excess return.

    Statistic: ``V = max_k sqrt(T) * mean(f_k)`` with ``f_k = r_k - benchmark``.
    Each bootstrap sample re-indexes all strategies with the *same* stationary
    bootstrap indices (preserving cross-strategy dependence) and recentres:
    ``V* = max_k sqrt(T) * (mean(f*_k) - mean(f_k))``. ``p = P(V* >= V)``.
    """
    f = np.asarray(r, dtype=float)
    if benchmark is not None:
        f = f - np.asarray(benchmark, dtype=float)[:, None]
    t, n = f.shape
    means = f.mean(axis=0)
    observed = np.sqrt(t) * means
    best = int(np.argmax(observed))

    rng = np.random.default_rng(seed)
    max_dist = np.empty(n_boot)
    chunk = max(1, min(n_boot, int(2e7 // max(t * n, 1))))
    done = 0
    while done < n_boot:
        m = min(chunk, n_boot - done)
        idx = _stationary_bootstrap_indices(t, m, block, rng)          # (m, T)
        boot_means = f[idx].mean(axis=1)                                # (m, N)
        max_dist[done:done + m] = np.sqrt(t) * (boot_means - means).max(axis=1)
        done += m

    p_value = float((np.sum(max_dist >= observed[best]) + 1) / (n_boot + 1))
    per_strategy = (np.sum(max_dist[None, :] >= observed[:, None], axis=1) + 1) / (n_boot + 1)
    return {
        "p_value": p_value,
        "best_index": best,
        "observed_max": float(observed[best]),
        "per_strategy_p": per_strategy,
        "max_distribution": max_dist,
    }


# ── Probability of Backtest Overfitting (CSCV) ─────────────────────────────

def pbo_cscv(r: np.ndarray, n_blocks: int = 16) -> dict[str, Any]:
    """Combinatorially symmetric cross-validation estimate of PBO.

    Split T into ``n_blocks`` contiguous blocks. For every choice of half the
    blocks as in-sample, select the IS-best strategy (by Sharpe) and compute its
    OOS relative rank ``w = rank / (N + 1)`` (1 = best). ``logit = ln(w / (1 - w))``;
    ``PBO = P(logit <= 0)``: the probability that the IS winner is below median
    out of sample.
    """
    r = np.asarray(r, dtype=float)
    t, n = r.shape
    if n_blocks % 2 != 0 or n_blocks < 2:
        raise ValueError("n_blocks must be an even number >= 2")
    if t < 2 * n_blocks:
        raise ValueError("not enough observations for the requested number of blocks")

    bounds = np.linspace(0, t, n_blocks + 1).astype(int)
    block_sum = np.stack([r[a:b].sum(axis=0) for a, b in zip(bounds[:-1], bounds[1:])])       # (S, N)
    block_sq = np.stack([(r[a:b] ** 2).sum(axis=0) for a, b in zip(bounds[:-1], bounds[1:])])
    block_len = np.diff(bounds).astype(float)                                                   # (S,)

    combos = np.array(list(itertools.combinations(range(n_blocks), n_blocks // 2)))
    c = np.zeros((len(combos), n_blocks))
    c[np.arange(len(combos))[:, None], combos] = 1.0

    def sharpe(mask: np.ndarray) -> np.ndarray:
        cnt = mask @ block_len                              # (C,)
        s1 = mask @ block_sum                               # (C, N)
        s2 = mask @ block_sq
        mean = s1 / cnt[:, None]
        var = (s2 / cnt[:, None] - mean**2) * (cnt / (cnt - 1))[:, None]
        std = np.sqrt(np.clip(var, 0, None))
        out = np.zeros_like(mean)
        np.divide(mean, std, out=out, where=std > 0)
        return out

    sr_is = sharpe(c)
    sr_oos = sharpe(1.0 - c)
    best_is = np.argmax(sr_is, axis=1)
    chosen_oos = sr_oos[np.arange(len(combos)), best_is]
    rank = (sr_oos <= chosen_oos[:, None]).sum(axis=1)     # 1 = worst ... N = best
    w = rank / (n + 1)
    logits = np.log(w / (1 - w))
    return {
        "pbo": float(np.mean(logits <= 0)),
        "logits": logits,
        "n_combinations": int(len(combos)),
        "n_blocks": n_blocks,
        "oos_sharpe_of_is_best": chosen_oos * math.sqrt(TRADING_DAYS),
    }


# ── Jensen's alpha with Newey-West standard errors ─────────────────────────

def jensen_alpha(r: np.ndarray, benchmark: np.ndarray, lags: int | None = None) -> dict[str, np.ndarray]:
    """OLS ``r = alpha + beta * benchmark + e`` per column, HAC (Newey-West) t-stats.

    Alpha is the return unexplained by benchmark exposure: a strategy that holds
    half the market has beta 0.5 and zero alpha even though its excess return
    over the fully invested benchmark is negative. Returns per-period alpha,
    beta, t-stat and one-sided p-value (H1: alpha > 0).
    """
    r = np.asarray(r, dtype=float)
    b = np.asarray(benchmark, dtype=float)
    t, n = r.shape
    lags = lags if lags is not None else int(np.floor(4 * (t / 100) ** (2 / 9)))
    has_benchmark = np.std(b) > 0
    # With no (or constant) benchmark the regression degenerates to alpha = mean(r).
    x = np.column_stack([np.ones(t), b]) if has_benchmark else np.ones((t, 1))
    xtx_inv = np.linalg.inv(x.T @ x)
    coef = xtx_inv @ x.T @ r                                 # (k, n)
    resid = r - x @ coef                                     # (t, n)

    # Newey-West long-run covariance of the score, per column (vectorised over n)
    scores = x[:, :, None] * resid[:, None, :]               # (t, 2, n)
    s0 = np.einsum("tin,tjn->ijn", scores, scores)
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        g = np.einsum("tin,tjn->ijn", scores[lag:], scores[:-lag])
        s0 += w * (g + g.transpose(1, 0, 2))
    cov = np.einsum("ij,jkn,kl->iln", xtx_inv, s0, xtx_inv)  # (2, 2, n)
    se_alpha = np.sqrt(np.clip(cov[0, 0, :], 1e-24, None))
    t_stat = coef[0] / se_alpha
    p_one = 1 - stats.norm.cdf(t_stat)
    beta = coef[1] if has_benchmark else np.zeros(n)
    return {"alpha_daily": coef[0], "beta": beta, "t_stat": t_stat, "p_value": p_one, "se_alpha": se_alpha}


# ── stability ──────────────────────────────────────────────────────────────

def block_stability(r: np.ndarray, k: int = 5) -> pd.DataFrame:
    """Per column: share of contiguous blocks with positive mean, worst/best block Sharpe (annualised)."""
    r = np.asarray(r, dtype=float)
    t = r.shape[0]
    bounds = np.linspace(0, t, k + 1).astype(int)
    sharpes = np.stack([_sharpe_period(r[a:b]) for a, b in zip(bounds[:-1], bounds[1:])]) * math.sqrt(TRADING_DAYS)
    means = np.stack([r[a:b].mean(axis=0) for a, b in zip(bounds[:-1], bounds[1:])])
    return pd.DataFrame({
        "stability": (means > 0).mean(axis=0),
        "worst_block_sharpe": sharpes.min(axis=0),
        "best_block_sharpe": sharpes.max(axis=0),
    })


# ── full assessment ────────────────────────────────────────────────────────

@dataclass
class EdgeReport:
    leaderboard: pd.DataFrame
    summary: dict[str, Any]
    reality_check_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    pbo_logits: np.ndarray = field(default_factory=lambda: np.array([]))


def _metrics(r: np.ndarray) -> dict[str, np.ndarray]:
    t = r.shape[0]
    nav = np.cumprod(1 + r, axis=0)
    total = nav[-1] - 1
    cagr = np.where(nav[-1] > 0, nav[-1] ** (TRADING_DAYS / t) - 1, -1.0)
    peak = np.maximum.accumulate(nav, axis=0)
    dd = (nav / peak - 1).min(axis=0)
    return {
        "sharpe": _sharpe_period(r) * math.sqrt(TRADING_DAYS),
        "cagr": cagr,
        "total_return": total,
        "max_drawdown": dd,
        "volatility": r.std(axis=0, ddof=1) * math.sqrt(TRADING_DAYS),
    }


def assess(
    returns: pd.DataFrame,
    n_trades: pd.Series | None = None,
    benchmark: pd.Series | None = None,
    is_fraction: float = 0.6,
    n_boot: int = 1000,
    seed: int = 0,
    pbo_blocks: int = 16,
    min_trades: int = 20,
    prior_trials: int = 0,
) -> EdgeReport:
    """Rank N algorithms and decide which have an edge after multiple-testing corrections.

    Args:
        returns: T x N DataFrame of daily strategy returns (columns = algorithm names).
        n_trades: Optional number of completed round trips per algorithm; fewer than
            ``min_trades`` blocks a ``strong``/``candidate`` verdict.
        benchmark: Daily returns of the passive alternative (e.g. equal-weight
            buy-and-hold of the same universe). Every edge statistic is computed on
            returns in excess of it, so market beta is not mistaken for skill.
            ``None`` means "versus cash" (benchmark = 0).
        is_fraction: Share of days used as in-sample for the IS/OOS split.
        n_boot: Bootstrap samples for the Reality Check.
        pbo_blocks: Blocks for CSCV (even; 16 -> 12 870 combinations).
        prior_trials: Algorithms tried in earlier rounds or configurations that are not
            in this matrix. They are added to N for the Deflated Sharpe Ratio and
            E[max SR] so a multi-round search cannot forget its own history.
    """
    if len(returns) < MIN_DAYS:
        raise ValueError(f"Need at least {MIN_DAYS} days of returns, got {len(returns)}")
    r = returns.fillna(0.0).to_numpy(dtype=float)
    t, n = r.shape
    names = list(returns.columns)
    split = int(t * is_fraction)
    r_is, r_oos = r[:split], r[split:]

    if benchmark is not None:
        b = benchmark.reindex(returns.index).fillna(0.0).to_numpy(dtype=float)
    else:
        b = np.zeros(t)
    x = r - b[:, None]                      # excess returns: the object of every edge test
    x_is, x_oos = x[:split], x[split:]

    full, ins, oos = _metrics(r), _metrics(r_is), _metrics(r_oos)
    ex_full = _sharpe_period(x) * math.sqrt(TRADING_DAYS)
    ex_is = _sharpe_period(x_is) * math.sqrt(TRADING_DAYS)
    ex_oos = _sharpe_period(x_oos) * math.sqrt(TRADING_DAYS)

    t_stat, p_two = stats.ttest_1samp(x, 0.0, axis=0)
    t_stat = np.nan_to_num(t_stat)
    p_one = np.where(t_stat > 0, np.nan_to_num(p_two, nan=1.0) / 2, 1 - np.nan_to_num(p_two, nan=1.0) / 2)

    n_trials = n + max(int(prior_trials), 0)
    psr = _psr(x, 0.0)
    dsr = deflated_sharpe_ratio(x, n_trials=n_trials)
    rc = reality_check(x, n_boot=n_boot, seed=seed)
    # Columns with constant excess return (e.g. the benchmark itself) carry no
    # information about selection and would trivially win every IS split.
    informative = x.std(axis=0, ddof=1) > 0
    x_pbo = x[:, informative]
    if t >= 2 * pbo_blocks and x_pbo.shape[1] >= 2:
        pbo = pbo_cscv(x_pbo, n_blocks=pbo_blocks)
    else:
        pbo = {"pbo": float("nan"), "logits": np.array([]), "n_combinations": 0}
    stab = block_stability(x, k=5)
    min_trl = np.array([min_track_record_length(x[:, j]) for j in range(n)])

    trades = (
        n_trades.reindex(names).fillna(0).to_numpy(dtype=float)
        if n_trades is not None else np.full(n, np.nan)
    )
    enough_trades = np.isnan(trades) | (trades >= min_trades)

    p_fdr = benjamini_hochberg(p_one)
    p_holm = holm(p_one)

    # Beta-adjusted view: Jensen's alpha against the benchmark (full, IS, OOS)
    ja = jensen_alpha(r, b)
    ja_is = jensen_alpha(r_is, b[:split])
    ja_oos = jensen_alpha(r_oos, b[split:])
    p_alpha_fdr = benjamini_hochberg(ja["p_value"])
    # Stability of the beta-adjusted residual across 5 contiguous blocks
    resid = r - b[:, None] * ja["beta"][None, :]
    alpha_stab = block_stability(resid, k=5)["stability"].to_numpy()
    alpha_strong = ((p_alpha_fdr < 0.05) & (ja_oos["alpha_daily"] > 0) & (ja_is["alpha_daily"] > 0)
                    & (alpha_stab >= 0.6) & enough_trades)
    alpha_candidate = ~alpha_strong & (p_alpha_fdr < 0.10) & (ja_oos["alpha_daily"] > 0) & enough_trades
    alpha_edge = np.where(alpha_strong, "strong", np.where(alpha_candidate, "candidate", "none"))

    strong = (p_fdr < 0.05) & (dsr > 0.95) & (ex_oos > 0) & (stab["stability"].to_numpy() >= 0.6) & enough_trades
    candidate = ~strong & (p_fdr < 0.10) & (ex_oos > 0) & enough_trades
    edge = np.where(strong, "strong", np.where(candidate, "candidate", "none"))

    lb = pd.DataFrame({
        "sharpe_full": full["sharpe"], "sharpe_is": ins["sharpe"], "sharpe_oos": oos["sharpe"],
        "excess_sharpe_full": ex_full, "excess_sharpe_is": ex_is, "excess_sharpe_oos": ex_oos,
        "cagr_full": full["cagr"], "cagr_is": ins["cagr"], "cagr_oos": oos["cagr"],
        "total_return_full": full["total_return"], "max_drawdown_full": full["max_drawdown"],
        "max_drawdown_oos": oos["max_drawdown"], "volatility_full": full["volatility"],
        "t_stat": t_stat, "p_value": p_one, "p_fdr": p_fdr, "p_holm": p_holm, "p_rc": rc["per_strategy_p"],
        "psr": psr, "dsr": dsr,
        "stability": stab["stability"].to_numpy(), "worst_block_sharpe": stab["worst_block_sharpe"].to_numpy(),
        "min_trl": min_trl, "n_trades": trades, "edge": edge,
        "alpha_ann": ja["alpha_daily"] * TRADING_DAYS, "alpha_t": ja["t_stat"], "p_alpha": ja["p_value"],
        "p_alpha_fdr": p_alpha_fdr, "alpha_is_ann": ja_is["alpha_daily"] * TRADING_DAYS,
        "alpha_oos_ann": ja_oos["alpha_daily"] * TRADING_DAYS, "beta": ja["beta"], "alpha_stability": alpha_stab,
        "alpha_edge": alpha_edge,
    }, index=pd.Index(names, name="algorithm"))
    lb = lb.sort_values(["excess_sharpe_is"], ascending=False, kind="stable")

    best_is_name = str(lb.index[0])
    sr_period = _sharpe_period(x)
    var_sr = float(np.var(sr_period, ddof=1)) if n > 1 else 0.0
    corr = stats.spearmanr(ex_is, ex_oos).statistic if n > 2 else float("nan")
    b_std = b.std(ddof=1)
    benchmark_sharpe = float(b.mean() / b_std * math.sqrt(TRADING_DAYS)) if b_std > 0 else 0.0

    summary = {
        "n_algorithms": int(n),
        "n_days": int(t),
        "is_days": int(split),
        "oos_days": int(t - split),
        "is_fraction": float(is_fraction),
        "benchmark_sharpe": benchmark_sharpe,
        "has_benchmark": benchmark is not None,
        "n_trials": int(n_trials),
        "expected_max_sharpe": float(expected_max_sharpe(n_trials, var_sr) * math.sqrt(TRADING_DAYS)),
        "observed_max_sharpe": float(ex_full.max()),
        "observed_max_abs_sharpe": float(full["sharpe"].max()),
        "reality_check_p": float(rc["p_value"]),
        "reality_check_best": names[rc["best_index"]],
        "reality_check_observed": float(rc["observed_max"]),
        "pbo": float(pbo["pbo"]),
        "pbo_combinations": int(pbo["n_combinations"]),
        "pbo_excluded_constant": int((~informative).sum()),
        "n_strong": int((edge == "strong").sum()),
        "n_candidate": int((edge == "candidate").sum()),
        "n_alpha_strong": int((alpha_edge == "strong").sum()),
        "n_alpha_candidate": int((alpha_edge == "candidate").sum()),
        "best_alpha_name": str(names[int(np.argmax(ja["t_stat"]))]),
        "best_alpha_t": float(np.max(ja["t_stat"])),
        "best_alpha_p_fdr": float(p_alpha_fdr[int(np.argmax(ja["t_stat"]))]),
        "n_fdr_5pct": int((p_fdr < 0.05).sum()),
        "is_oos_rank_corr": float(corr) if corr is not None and not np.isnan(corr) else None,
        "best_is_name": best_is_name,
        "best_is_sharpe_is": float(lb.iloc[0]["excess_sharpe_is"]),
        "best_is_oos_sharpe": float(lb.iloc[0]["excess_sharpe_oos"]),
        "best_is_consistent_with_luck": bool(rc["p_value"] > 0.05 or (not np.isnan(pbo["pbo"]) and pbo["pbo"] > 0.5)),
        "n_boot": int(n_boot),
    }
    return EdgeReport(
        leaderboard=lb,
        summary=summary,
        reality_check_distribution=rc["max_distribution"],
        pbo_logits=np.asarray(pbo["logits"]),
    )
