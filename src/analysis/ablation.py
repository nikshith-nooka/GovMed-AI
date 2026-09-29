"""Ablation study analysis for clinical governance benchmark.

Isolates the marginal contribution of each governance layer (verifier, HITL,
safety) across pipeline variants V1-V5, and computes statistical significance
between adjacent variants.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

from src.telemetry.db import BenchmarkDB
from src.evaluation.statistics import BenchmarkStatistics


class AblationAnalyzer:
    """Quantifies marginal cost-benefit of each governance layer."""

    # Canonical governance-layer label per variant transition
    LAYER_LABELS = {
        ("V1", "V2"): "verifier",
        ("V2", "V3"): "HITL",
        ("V3", "V4"): "safety",
        ("V4", "V5"): "consistency",
    }

    def __init__(self, db_path: str = "results/benchmark_results.db"):
        self.db = BenchmarkDB(db_path)
        self.runs_df = self.db.get_runs_df()
        self.variant_summary = self.db.get_variant_summary()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_row(self) -> pd.Series:
        """Return the V1 baseline summary row."""
        row = self.variant_summary[self.variant_summary["variant_id"] == "V1"]
        if row.empty:
            raise ValueError("No V1 baseline found in database.")
        return row.iloc[0]

    def _variant_rows(self) -> pd.DataFrame:
        """Return variant summary sorted by variant_id."""
        return self.variant_summary.sort_values("variant_id").reset_index(drop=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_marginal_contribution(self) -> pd.DataFrame:
        """For each governance layer, isolate marginal quality gain and
        marginal token/cost overhead vs the previous variant.

        Returns a DataFrame with columns:
            layer, from_variant, to_variant,
            delta_quality, delta_quality_pct,
            delta_tokens, delta_tokens_pct,
            delta_latency_ms, delta_cost_usd,
            hallucination_rate, safety_violation_rate
        """
        rows = self._variant_rows()
        base = self._base_row()

        results: List[Dict] = []
        for i in range(1, len(rows)):
            curr = rows.iloc[i]
            prev = rows.iloc[i - 1]
            key = (prev["variant_id"], curr["variant_id"])
            layer = self.LAYER_LABELS.get(key, f"{prev['variant_id']}→{curr['variant_id']}")

            base_q = base["avg_quality"] if base["avg_quality"] > 0 else 1.0
            base_t = base["avg_tokens"] if base["avg_tokens"] > 0 else 1.0

            delta_q = curr["avg_quality"] - prev["avg_quality"]
            delta_t = curr["avg_tokens"] - prev["avg_tokens"]

            results.append({
                "layer": layer,
                "from_variant": prev["variant_id"],
                "to_variant": curr["variant_id"],
                "delta_quality": round(float(delta_q), 4),
                "delta_quality_pct": round(float(delta_q / base_q * 100), 2),
                "delta_tokens": round(float(delta_t), 1),
                "delta_tokens_pct": round(float(delta_t / base_t * 100), 2),
                "delta_latency_ms": round(
                    float(curr["avg_latency_ms"] - prev["avg_latency_ms"]), 1
                ),
                "delta_cost_usd": round(
                    float(curr["avg_cost_usd"] - prev["avg_cost_usd"]), 6
                ),
                "hallucination_rate": float(curr["avg_hallucinations"]),
                "safety_violation_rate": float(curr["avg_safety_violations"]),
            })

        return pd.DataFrame(results)

    def compute_ablation_table(self) -> pd.DataFrame:
        """Full ablation table with per-variant metrics and deltas vs baseline.

        Returns DataFrame with columns:
            variant_id, variant_name, avg_quality, delta_quality_pct,
            avg_tokens, delta_tokens_pct, avg_latency_ms,
            quality_gain_per_1k_tokens, hallucination_rate,
            safety_violation_rate
        """
        base = self._base_row()
        rows = self._variant_rows()

        base_q = base["avg_quality"] if base["avg_quality"] > 0 else 1.0
        base_t = base["avg_tokens"] if base["avg_tokens"] > 0 else 1.0

        table_rows: List[Dict] = []
        for _, row in rows.iterrows():
            d_q = row["avg_quality"] - base["avg_quality"]
            d_t = row["avg_tokens"] - base["avg_tokens"]

            if d_t > 0:
                gain_per_1k = round(float((d_q * 100 / d_t) * 1000), 3)
            else:
                gain_per_1k = 0.0

            table_rows.append({
                "variant_id": row["variant_id"],
                "variant_name": row["variant_name"],
                "avg_quality": float(row["avg_quality"]),
                "delta_quality_pct": round(float(d_q / base_q * 100), 2),
                "avg_tokens": float(row["avg_tokens"]),
                "delta_tokens_pct": round(float(d_t / base_t * 100), 2),
                "avg_latency_ms": float(row["avg_latency_ms"]),
                "quality_gain_per_1k_tokens": gain_per_1k,
                "hallucination_rate": float(row["avg_hallucinations"]),
                "safety_violation_rate": float(row["avg_safety_violations"]),
            })

        return pd.DataFrame(table_rows)

    def compute_cost_benefit_curve(self) -> pd.DataFrame:
        """For each variant, compute cost-effectiveness ratio.

        cost_effectiveness = (quality - baseline_quality) / additional_tokens

        Returns a DataFrame suitable for plotting with columns:
            variant_id, variant_name, quality_score, additional_tokens,
            cost_effectiveness, quality_improvement
        """
        base = self._base_row()
        rows = self._variant_rows()

        base_q = float(base["avg_quality"])
        base_t = float(base["avg_tokens"])

        records: List[Dict] = []
        for _, row in rows.iterrows():
            q = float(row["avg_quality"])
            t = float(row["avg_tokens"])
            add_tok = t - base_t
            imp = q - base_q

            ce = float(imp / add_tok) if add_tok > 0 else 0.0

            records.append({
                "variant_id": row["variant_id"],
                "variant_name": row["variant_name"],
                "quality_score": q,
                "additional_tokens": round(add_tok, 1),
                "cost_effectiveness": round(ce, 8),
                "quality_improvement": round(imp, 4),
            })

        return pd.DataFrame(records)

    def compute_statistical_significance(self) -> pd.DataFrame:
        """For each pair of adjacent variants, run Mann-Whitney U test
        on overall_quality_score.

        Returns DataFrame with columns:
            variant_a, variant_b, u_statistic, p_value, significant_at_05
        """
        rows = self._variant_rows()
        results: List[Dict] = []

        for i in range(len(rows) - 1):
            vid_a = rows.iloc[i]["variant_id"]
            vid_b = rows.iloc[i + 1]["variant_id"]

            scores_a = self.runs_df[self.runs_df["variant_id"] == vid_a][
                "overall_quality_score"
            ]
            scores_b = self.runs_df[self.runs_df["variant_id"] == vid_b][
                "overall_quality_score"
            ]

            test = BenchmarkStatistics.compute_mann_whitney_u(scores_a, scores_b)

            results.append({
                "variant_a": vid_a,
                "variant_b": vid_b,
                "u_statistic": test["u_statistic"],
                "p_value": test["p_value"],
                "significant_at_05": test["p_value"] < 0.05,
            })

        return pd.DataFrame(results)
