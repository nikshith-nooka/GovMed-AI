"""Governance Efficiency Frontier (GEF) & Uncertainty (JRU) Pareto Analysis.

Computes the empirical Pareto efficiency frontier of governance configurations,
evaluating the trade-off between risk-adjusted clinical quality and total
governance expenditure (compute + human oversight overhead).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.telemetry.db import BenchmarkDB
from src.evaluation.statistics import BenchmarkStatistics
from src.config.governance_economics import (
    HUMAN_REVIEW_RATE_USD_PER_MIN,
    RISK_ADJUSTMENT_LAMBDA,
)


class GovernanceEfficiencyFrontier:
    """Computes Pareto efficiency frontiers and risk-adjusted governance metrics."""

    def __init__(self, db_path: str = "results/benchmark_results.db"):
        self.db = BenchmarkDB(db_path)
        self.runs_df = self.db.get_runs_df()

    def get_runs_df(self) -> pd.DataFrame:
        return self.runs_df

    def compute_frontier(self, use_risk_adjusted: bool = True) -> pd.DataFrame:
        """Computes the empirical Pareto efficiency frontier across governance variants.

        Each variant is characterized by:
        1. Objective 1 (Maximize): Clinical Quality (risk_adjusted_quality or overall_quality_score)
        2. Objective 2 (Minimize): Total Governance Cost (tokens or monetary USD cost)

        Returns DataFrame with columns:
            variant_id, variant_name, n_runs,
            raw_quality, risk_adjusted_quality, jru_uncertainty,
            avg_tokens, avg_latency_ms, avg_llm_cost_usd,
            avg_hitl_minutes, avg_hitl_cost_usd, total_governance_cost_usd,
            governance_efficiency_factor, is_pareto_frontier, dominated_by
        """
        if self.runs_df.empty:
            return pd.DataFrame()

        df = self.runs_df.copy()

        # Handle missing columns gracefully on older databases
        if "risk_adjusted_quality" not in df.columns:
            df["risk_adjusted_quality"] = df["overall_quality_score"]
        if "uncertainty_jru" not in df.columns:
            df["uncertainty_jru"] = 0.0
        if "hitl_minutes" not in df.columns:
            df["hitl_minutes"] = 0.0
        if "hitl_human_cost" not in df.columns:
            df["hitl_human_cost"] = df["hitl_minutes"] * HUMAN_REVIEW_RATE_USD_PER_MIN
        if "governance_efficiency_factor" not in df.columns:
            df["governance_efficiency_factor"] = (
                df["overall_quality_score"] * 1000.0 / df["total_tokens"].replace(0, 1)
            )

        # Fill NAs
        df["risk_adjusted_quality"] = df["risk_adjusted_quality"].fillna(df["overall_quality_score"])
        df["uncertainty_jru"] = df["uncertainty_jru"].fillna(0.0)
        df["hitl_minutes"] = df["hitl_minutes"].fillna(0.0)
        df["hitl_human_cost"] = df["hitl_human_cost"].fillna(0.0)
        df["governance_efficiency_factor"] = df["governance_efficiency_factor"].fillna(
            (df["risk_adjusted_quality"] * 1000.0) / df["total_tokens"].replace(0, 1)
        )

        # Total governance cost in USD (LLM compute + simulated physician review cost)
        df["total_governance_cost_usd"] = df["total_cost_usd"] + df["hitl_human_cost"]

        # Aggregate by variant
        grouped = df.groupby(["variant_id", "variant_name"]).agg(
            n_runs=("id", "count"),
            raw_quality=("overall_quality_score", "mean"),
            risk_adjusted_quality=("risk_adjusted_quality", "mean"),
            jru_uncertainty=("uncertainty_jru", "mean"),
            avg_tokens=("total_tokens", "mean"),
            avg_latency_ms=("total_latency_ms", "mean"),
            avg_llm_cost_usd=("total_cost_usd", "mean"),
            avg_hitl_minutes=("hitl_minutes", "mean"),
            avg_hitl_cost_usd=("hitl_human_cost", "mean"),
            total_governance_cost_usd=("total_governance_cost_usd", "mean"),
            governance_efficiency_factor=("governance_efficiency_factor", "mean"),
        ).reset_index().sort_values("variant_id").reset_index(drop=True)

        quality_col = "risk_adjusted_quality" if use_risk_adjusted else "raw_quality"
        cost_col = "avg_tokens"  # primary resource proxy

        # Compute Pareto Dominance
        # Point i dominates Point j iff Quality(i) >= Quality(j) AND Cost(i) <= Cost(j)
        # with at least one strict inequality.
        n = len(grouped)
        is_frontier = [True] * n
        dominated_by_list = [[] for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                q_i = grouped.loc[i, quality_col]
                c_i = grouped.loc[i, cost_col]
                q_j = grouped.loc[j, quality_col]
                c_j = grouped.loc[j, cost_col]

                # Does j dominate i?
                if (q_j >= q_i and c_j <= c_i) and (q_j > q_i or c_j < c_i):
                    is_frontier[i] = False
                    dominated_by_list[i].append(grouped.loc[j, "variant_id"])

        grouped["is_pareto_frontier"] = is_frontier
        grouped["dominated_by"] = [", ".join(d) if d else "None (Frontier)" for d in dominated_by_list]

        # Round numerical columns
        for col in ["raw_quality", "risk_adjusted_quality", "jru_uncertainty"]:
            grouped[col] = grouped[col].round(4)
        for col in ["avg_tokens", "avg_latency_ms", "governance_efficiency_factor"]:
            grouped[col] = grouped[col].round(1)
        for col in ["avg_llm_cost_usd", "avg_hitl_cost_usd", "total_governance_cost_usd"]:
            grouped[col] = grouped[col].round(6)
        grouped["avg_hitl_minutes"] = grouped["avg_hitl_minutes"].round(2)

        return grouped

    def compute_uncertainty_summary(self) -> pd.DataFrame:
        """Computes statistical confidence intervals for JRU uncertainty per variant."""
        if self.runs_df.empty:
            return pd.DataFrame()

        df = self.runs_df.copy()
        if "uncertainty_jru" not in df.columns:
            df["uncertainty_jru"] = 0.0

        records = []
        for v_id, sub_df in df.groupby("variant_id"):
            v_name = sub_df["variant_name"].iloc[0] if "variant_name" in sub_df.columns else str(v_id)
            u_series = pd.Series(sub_df["uncertainty_jru"].to_numpy())
            q_series = pd.Series(sub_df["overall_quality_score"].to_numpy())
            mean, lower, upper = BenchmarkStatistics.compute_ci_95(u_series)
            qual_mean, qual_low, qual_high = BenchmarkStatistics.compute_ci_95(q_series)
            
            records.append({
                "variant_id": str(v_id),
                "variant_name": str(v_name),
                "uncertainty_mean": mean,
                "uncertainty_ci_lower": lower,
                "uncertainty_ci_upper": upper,
                "quality_mean": qual_mean,
                "quality_ci_lower": qual_low,
                "quality_ci_upper": qual_high,
                "sample_size": len(sub_df),
            })

        return pd.DataFrame(records).sort_values("variant_id").reset_index(drop=True)

    def export_frontier_artifacts(
        self,
        output_dir: str = "paper/tables",
    ) -> Tuple[Path, Path]:
        """Exports CSV and LaTeX tables of the Governance Efficiency Frontier."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        frontier_df = self.compute_frontier()

        csv_file = out_path / "gef_frontier.csv"
        frontier_df.to_csv(csv_file, index=False)

        tex_file = out_path / "gef_frontier.tex"
        # Clean formatting for IEEE LaTeX — pre-format as strings for exact precision
        export_df = pd.DataFrame({
            "Variant": frontier_df["variant_id"],
            "Governance Tier": frontier_df["variant_name"],
            "Runs": frontier_df["n_runs"].astype(int),
            r"$Q_{\text{raw}}$": frontier_df["raw_quality"].apply(lambda x: f"{x:.3f}"),
            r"$Q_{\text{adj}}$": frontier_df["risk_adjusted_quality"].apply(lambda x: f"{x:.3f}"),
            "JRU": frontier_df["jru_uncertainty"].apply(lambda x: f"{x:.3f}"),
            "Tokens": frontier_df["avg_tokens"].apply(lambda x: f"{int(x):,}"),
            "Latency (s)": (frontier_df["avg_latency_ms"] / 1000.0).apply(lambda x: f"{x:.1f}"),
            r"Compute (\$)": frontier_df["avg_llm_cost_usd"].apply(lambda x: f"\\${x:.4f}"),
            "HITL (min)": frontier_df["avg_hitl_minutes"].apply(lambda x: f"{x:.1f}"),
            r"Total Cost (\$)": frontier_df["total_governance_cost_usd"].apply(lambda x: f"\\${x:.4f}"),
            "GEF": (frontier_df["governance_efficiency_factor"] * 1000.0).apply(lambda x: f"{x:.1f}"),
            "Frontier": frontier_df["is_pareto_frontier"].apply(lambda x: r"\textbf{Pareto}" if x else "Dominated"),
        })

        latex_code = export_df.to_latex(
            index=False,
            escape=False,
            caption="Governance Efficiency Frontier (GEF): Empirical Trade-off between Risk-Adjusted Quality, Oversight Latency, and Compute Overhead.",
            label="tab:gef_frontier",
            column_format="llccccccccclc",
        )
        # Ensure two-column width in IEEEtran
        latex_code = latex_code.replace(r"\begin{table}", r"\begin{table*}").replace(r"\end{table}", r"\end{table*}")
        tex_file.write_text(latex_code, encoding="utf-8")

        return csv_file, tex_file
