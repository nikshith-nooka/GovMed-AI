"""Statistical analysis: 95% Confidence Intervals, Hypothesis Testing, and Marginal ROI."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from typing import Any, Dict, List, Tuple


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
