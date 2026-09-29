"""Statistical analysis: 95% Confidence Intervals, Hypothesis Testing, and Marginal ROI."""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import optimize, stats


# ---------------------------------------------------------------- paired binary accuracy
def mcnemar_exact(correct_a: Sequence[bool], correct_b: Sequence[bool]) -> Dict[str, Any]:
    """Exact (binomial) two-sided McNemar test on paired binary outcomes.

    b = pairs where only A is correct, c = pairs where only B is correct.
    p = min(1, 2 * P[X <= min(b, c)]) with X ~ Binomial(b + c, 0.5).
    """
    a, b_ = np.asarray(correct_a, bool), np.asarray(correct_b, bool)
    if a.shape != b_.shape:
        raise ValueError("paired outcomes must have equal length")
    only_a, only_b = int((a & ~b_).sum()), int((~a & b_).sum())
    return {"n_pairs": int(len(a)), "only_a_correct": only_a, "only_b_correct": only_b,
            **mcnemar_exact_from_counts(only_a, only_b)}


def mcnemar_exact_from_counts(b: int, c: int) -> Dict[str, Any]:
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2.0 * float(stats.binom.cdf(min(b, c), n, 0.5)))
    return {"n_discordant": int(n), "p_value": p}


def holm_bonferroni(p_values: Sequence[Optional[float]]) -> List[Optional[float]]:
    """Holm step-down adjusted p-values (same order as input; None entries are skipped)."""
    idx = [i for i, p in enumerate(p_values) if p is not None and not math.isnan(p)]
    m = len(idx)
    adjusted: List[Optional[float]] = [None] * len(p_values)
    running = 0.0
    for rank, i in enumerate(sorted(idx, key=lambda j: p_values[j])):
        running = max(running, min(1.0, (m - rank) * float(p_values[i])))
        adjusted[i] = running
    return adjusted


# ---------------------------------------------------------------- effect sizes
def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h for two proportions: 2*asin(sqrt(p2)) - 2*asin(sqrt(p1))."""
    return float(2 * math.asin(math.sqrt(min(1.0, max(0.0, p2)))) - 2 * math.asin(math.sqrt(min(1.0, max(0.0, p1)))))


def rank_biserial(diffs: Sequence[float]) -> Optional[float]:
    """Matched-pairs rank-biserial correlation (effect size for the Wilcoxon signed-rank test).

    r = (R+ - R-) / (R+ + R-), ranks of |d| over non-zero differences (Kerby, 2014).
    """
    d = np.asarray(diffs, float)
    d = d[d != 0]
    if len(d) == 0:
        return None
    ranks = stats.rankdata(np.abs(d))
    pos, neg = ranks[d > 0].sum(), ranks[d < 0].sum()
    return float((pos - neg) / (pos + neg))


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    statistic: Callable[[np.ndarray, np.ndarray], Optional[float]],
    n_boot: int = 2000,
    seed: int = 7,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Percentile 95% CI of statistic(a, b), resampling pairs jointly. Returns (point, lo, hi)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0:
        return None, None, None
    point = statistic(a, b)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n_boot, len(a)))
    draws = [statistic(a[i], b[i]) for i in idx]
    draws = np.asarray([x for x in draws if x is not None and not math.isnan(x)], float)
    if len(draws) == 0:
        return point, None, None
    return point, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


# ---------------------------------------------------------------- inter-rater agreement
def cohens_kappa_categorical(r1: Sequence[Any], r2: Sequence[Any]) -> Optional[float]:
    """Cohen's kappa for two raters over the same items (any hashable categories)."""
    if len(r1) != len(r2) or len(r1) == 0:
        return None
    cats = sorted({*r1, *r2}, key=str)
    n = len(r1)
    po = sum(x == y for x, y in zip(r1, r2, strict=True)) / n
    pe = sum((list(r1).count(c) / n) * (list(r2).count(c) / n) for c in cats)
    return None if pe >= 1 else float((po - pe) / (1 - pe))


def fleiss_kappa(table: Sequence[Sequence[int]]) -> Optional[float]:
    """Fleiss' kappa from an items x categories count matrix (each row sums to the raters per item).

    Requires the same number of raters (>= 2) on every item.
    """
    m = np.asarray(table, float)
    if m.ndim != 2 or m.shape[0] == 0:
        return None
    n_raters = m.sum(axis=1)
    if not np.allclose(n_raters, n_raters[0]) or n_raters[0] < 2:
        raise ValueError("Fleiss' kappa needs the same number (>= 2) of ratings on every item")
    n, big_n = n_raters[0], m.shape[0]
    p_j = m.sum(axis=0) / (big_n * n)
    p_i = ((m * m).sum(axis=1) - n) / (n * (n - 1))
    p_bar, pe = p_i.mean(), float((p_j ** 2).sum())
    return None if pe >= 1 else float((p_bar - pe) / (1 - pe))


# ---------------------------------------------------------------- power (paired McNemar)
def mcnemar_power(n: int, delta: float, discordance: float, alpha: float = 0.05) -> float:
    """Approximate power of the two-sided McNemar test (Connor, 1987).

    delta = p10 - p01 (accuracy difference), discordance = p10 + p01.
    power = Phi((sqrt(n)*|delta| - z_{1-alpha/2}*sqrt(psi)) / sqrt(psi - delta^2)).
    """
    psi, d = float(discordance), abs(float(delta))
    if d > psi:
        raise ValueError("an accuracy difference cannot exceed the discordance rate")
    if n <= 0 or d == 0 or psi <= 0:
        return float(alpha) if d == 0 else 0.0
    z_a = stats.norm.ppf(1 - alpha / 2)
    return float(stats.norm.cdf((math.sqrt(n) * d - z_a * math.sqrt(psi)) / math.sqrt(psi - d * d)))


def mcnemar_required_n(delta: float, discordance: float, alpha: float = 0.05, power: float = 0.8) -> Optional[int]:
    """Pairs needed to detect accuracy difference delta at the given discordance rate (Connor, 1987)."""
    psi, d = float(discordance), abs(float(delta))
    if d == 0 or psi <= 0 or d > psi:
        return None
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return int(math.ceil((z_a * math.sqrt(psi) + z_b * math.sqrt(psi - d * d)) ** 2 / (d * d)))


def mcnemar_mde(n: int, discordance: float, alpha: float = 0.05, power: float = 0.8) -> Optional[float]:
    """Minimum detectable |accuracy difference| for n pairs at the given discordance rate."""
    psi = float(discordance)
    if n <= 0 or psi <= 0:
        return None
    if mcnemar_power(n, psi, psi, alpha) < power:
        return None  # no difference that the observed discordance allows is detectable
    return float(optimize.brentq(lambda d: mcnemar_power(n, d, psi, alpha) - power, 1e-9, psi))


class BenchmarkStatistics:
    """Computes academic-grade statistical significance and marginal governance cost curves."""

    @staticmethod
    def compute_ci_95(series: pd.Series) -> Tuple[float, float, float]:
        """Returns (mean, lower_95_ci, upper_95_ci)."""
        clean = series.dropna().to_numpy()
        if len(clean) < 2:
            val = float(clean[0]) if len(clean) == 1 else 0.0
            return val, val, val
        mean = float(np.mean(clean))
        sem = stats.sem(clean)
        ci = sem * stats.t.ppf((1 + 0.95) / 2.0, len(clean) - 1)
        return round(mean, 4), round(mean - ci, 4), round(mean + ci, 4)

    @staticmethod
    def compute_mann_whitney_u(sample_a: pd.Series, sample_b: pd.Series) -> Dict[str, float]:
        """Runs two-sided Mann-Whitney U test."""
        clean_a = sample_a.dropna().to_numpy()
        clean_b = sample_b.dropna().to_numpy()
        if len(clean_a) < 2 or len(clean_b) < 2 or np.array_equal(clean_a, clean_b):
            return {"u_statistic": 0.0, "p_value": 1.0}
        stat, p_val = stats.mannwhitneyu(clean_a, clean_b, alternative="two-sided")
        return {"u_statistic": round(float(stat), 4), "p_value": round(float(p_val), 5)}

    @staticmethod
    def compute_marginal_roi(runs_df: pd.DataFrame) -> pd.DataFrame:
        """Computes marginal gain in quality per token and per second overhead relative to baseline."""
        if runs_df.empty:
            return pd.DataFrame()

        summary = runs_df.groupby(["variant_id", "variant_name"]).agg(
            avg_quality=("overall_quality_score", "mean"),
            avg_accuracy=("diagnostic_accuracy_score", "mean"),
            avg_tokens=("total_tokens", "mean"),
            avg_latency_ms=("total_latency_ms", "mean"),
            avg_cost_usd=("total_cost_usd", "mean"),
            avg_hallucinations=("hallucinations_detected", "mean"),
        ).reset_index()

        baseline_rows = summary[summary["variant_id"] == "V1"]
        if baseline_rows.empty:
            return summary

        base_qual = baseline_rows["avg_quality"].values[0]
        base_tok = baseline_rows["avg_tokens"].values[0]
        base_lat = baseline_rows["avg_latency_ms"].values[0]

        summary["delta_quality_pct"] = (
            (summary["avg_quality"] - base_qual) / (base_qual if base_qual > 0 else 1.0) * 100
        ).round(2)
        summary["delta_tokens_pct"] = (
            (summary["avg_tokens"] - base_tok) / (base_tok if base_tok > 0 else 1.0) * 100
        ).round(2)
        summary["delta_latency_pct"] = (
            (summary["avg_latency_ms"] - base_lat) / (base_lat if base_lat > 0 else 1.0) * 100
        ).round(2)

        # Marginal Quality per 1000 tokens added
        def calc_roi(row):
            d_tok = row["avg_tokens"] - base_tok
            if d_tok <= 0:
                return 0.0
            d_qual = (row["avg_quality"] - base_qual) * 100
            return round((d_qual / d_tok) * 1000, 3)

        summary["quality_gain_per_1k_tokens"] = summary.apply(calc_roi, axis=1)
        return summary
