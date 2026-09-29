#!/usr/bin/env python3
"""End-to-end ablation analysis pipeline.

Loads benchmark data, runs AblationAnalyzer, prints summary tables,
generates charts, and exports CSV + LaTeX tables to paper/tables/.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.ablation import AblationAnalyzer
from src.analysis.frontier import GovernanceEfficiencyFrontier
from scripts.generate_charts import generate_all_charts

TABLE_DIR = PROJECT_ROOT / "paper" / "tables"
TABLE_DIR.mkdir(parents=True, exist_ok=True)


def print_section(title: str) -> None:
    width = 72
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def export_variant_summary(analyzer: AblationAnalyzer) -> None:
    """Export ablation table as CSV and LaTeX to paper/tables/."""
    table = analyzer.compute_ablation_table()

    csv_path = TABLE_DIR / "variant_summary.csv"
    table.to_csv(csv_path, index=False)
    print(f"\n  ✓ {csv_path}")

    tex_path = TABLE_DIR / "variant_summary.tex"
    export_df = pd.DataFrame({
        "Variant": table["variant_id"],
        "Governance Configuration": table["variant_name"],
        r"Quality ($Q$)": table["avg_quality"].round(3),
        r"$\Delta Q$ (\%)": table["delta_quality_pct"].round(1),
        "Tokens ($T$)": table["avg_tokens"].apply(lambda x: f"{int(x):,}"),
        r"$\Delta T$ (\%)": table["delta_tokens_pct"].round(1),
        "Latency (s)": (table["avg_latency_ms"] / 1000.0).round(1),
        "Halluc. Rate": table["hallucination_rate"].round(3),
        "Safety Interventions": table["safety_violation_rate"].round(3),
    })

    latex = export_df.to_latex(
        index=False,
        escape=False,
        caption="Comparative Governance-Cost Performance and Ablation across Multi-Agent Clinical Architectures.",
        label="tab:variant_summary",
        column_format="llccccccc",
    )
    latex = latex.replace(r"\begin{table}", r"\begin{table*}").replace(r"\end{table}", r"\end{table*}")
    tex_path.write_text(latex)
    print(f"  ✓ {tex_path}")


def export_frontier_summary(frontier_analyzer: GovernanceEfficiencyFrontier) -> None:
    """Export Governance Efficiency Frontier table as CSV and LaTeX to paper/tables/."""
    csv_file, tex_file = frontier_analyzer.export_frontier_artifacts(str(TABLE_DIR))
    print(f"  ✓ {csv_file}")
    print(f"  ✓ {tex_file}")


def export_dataset_ablation(db_path: str) -> None:
    """Export per-dataset breakdown (MedQA / PubMedQA / MedDialog) as Table III."""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("""
            SELECT
                CASE
                    WHEN case_id LIKE 'medqa%' THEN 'MedQA-USMLE'
                    WHEN case_id LIKE 'pubmedqa%' THEN 'PubMedQA'
                    ELSE 'MedDialog'
                END AS dataset,
                variant_id,
                round(avg(overall_quality_score), 3)  AS quality,
                round(avg(total_tokens))               AS tokens,
                sum(safety_violations_detected)        AS safety_flags,
                sum(hallucinations_detected)           AS halluc_flags,
                round(avg(total_latency_ms)/1000.0, 1) AS latency_s
            FROM runs
            GROUP BY dataset, variant_id
            ORDER BY dataset, variant_id
        """, conn)

    # Pivot to wide form: dataset as rows, variants as sub-columns on quality
    pivot = df.pivot_table(index="dataset", columns="variant_id",
                           values=["quality", "safety_flags", "halluc_flags"],
                           aggfunc="first")
    pivot.columns = [f"{v}_{c}" for v, c in pivot.columns]
    pivot = pivot.reset_index()

    csv_path = TABLE_DIR / "dataset_ablation.csv"
    df.to_csv(csv_path, index=False)
    print(f"  ✓ {csv_path}")

    # Build clean LaTeX table (flat, not pivoted — more readable for IEEE)
    export_df = pd.DataFrame({
        "Dataset": df["dataset"],
        "Variant": df["variant_id"],
        r"Quality ($Q$)": df["quality"].apply(lambda x: f"{x:.3f}"),
        "Tokens": df["tokens"].apply(lambda x: f"{int(x):,}"),
        "Latency (s)": df["latency_s"].apply(lambda x: f"{x:.1f}"),
        "Safety Flags": df["safety_flags"].astype(int),
        "Halluc. Flags": df["halluc_flags"].astype(int),
    })

    latex = export_df.to_latex(
        index=False,
        escape=False,
        caption="Dataset-Stratified Ablation: Clinical Quality and Safety Interception across MedQA-USMLE, PubMedQA, and MedDialog Paradigms.",
        label="tab:dataset_ablation",
        column_format="llccccc",
    )
    latex = latex.replace(r"\begin{table}", r"\begin{table*}").replace(r"\end{table}", r"\end{table*}")

    tex_path = TABLE_DIR / "dataset_ablation.tex"
    tex_path.write_text(latex)
    print(f"  ✓ {tex_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ablation analysis.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    print_section("Clinical Governance Benchmark – Ablation Analysis")

    # 1. Run ablation analysis
    analyzer = AblationAnalyzer(str(PROJECT_ROOT / "results" / "benchmark_results.db"))
    frontier_analyzer = GovernanceEfficiencyFrontier(str(PROJECT_ROOT / "results" / "benchmark_results.db"))

    # 2. Ablation table
    print_section("Ablation Table")
    ablation_table = analyzer.compute_ablation_table()
    print(ablation_table.to_string(index=False))

    # 3. Marginal contributions
    print_section("Marginal Contribution per Governance Layer")
    marginal = analyzer.compute_marginal_contribution()
    print(marginal.to_string(index=False))

    # 4. Cost-benefit curve
    print_section("Cost-Benefit Curve")
    cost_benefit = analyzer.compute_cost_benefit_curve()
    print(cost_benefit.to_string(index=False))

    # 5. Governance Efficiency Frontier (GEF)
    print_section("Governance Efficiency Frontier (GEF Pareto Analysis)")
    gef_table = frontier_analyzer.compute_frontier()
    print(gef_table.to_string(index=False))

    # 6. Judge/Rubric Disagreement Uncertainty (JRU)
    print_section("Judge/Rubric Uncertainty (JRU) Summary (95% CI)")
    jru_table = frontier_analyzer.compute_uncertainty_summary()
    print(jru_table.to_string(index=False))

    # 7. Statistical significance
    print_section("Statistical Significance (Mann-Whitney U)")
    significance = analyzer.compute_statistical_significance()
    print(significance.to_string(index=False))

    # 8. Export tables
    print_section("Exporting Tables")
    export_variant_summary(analyzer)
    export_frontier_summary(frontier_analyzer)
    export_dataset_ablation(str(PROJECT_ROOT / "results" / "benchmark_results.db"))

    # 9. Generate charts
    print_section("Generating Charts")
    generate_all_charts()

    print_section("Done")


if __name__ == "__main__":
    main()
