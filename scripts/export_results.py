#!/usr/bin/env python3
"""Exports SQLite benchmark runs into clean CSV and publication-ready LaTeX tables for IEEE paper insertion."""

from __future__ import annotations

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("results/benchmark_results.db")
OUTPUT_DIR = Path("paper/tables")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM runs", conn)

    # 1. Summary by Variant
    summary = df.groupby(["variant_id", "variant_name"]).agg(
        Cases=("id", "count"),
        Quality=("overall_quality_score", lambda x: f"{x.mean():.3f} $\\pm$ {x.std():.3f}"),
        Accuracy=("diagnostic_accuracy_score", lambda x: f"{x.mean()*100:.1f}\\%"),
        Tokens=("total_tokens", lambda x: f"{int(x.mean()):,}"),
        Latency_ms=("total_latency_ms", lambda x: f"{int(x.mean()):,}"),
        Cost_USD=("total_cost_usd", lambda x: f"\\${x.mean():.4f}"),
        Safety_Flags=("safety_violations_detected", lambda x: f"{x.mean():.2f}"),
    ).reset_index()

    summary.columns = [
        "Variant",
        "Governance Configuration",
        "Runs",
        "Quality Score",
        "Diagnostic Accuracy",
        "Mean Tokens",
        "Latency (ms)",
        "Inference Cost",
        "Safety Flags / Case",
    ]

    # Save to CSV
    csv_path = OUTPUT_DIR / "variant_summary.csv"
    summary.to_csv(csv_path, index=False)
    print(f"Saved CSV: {csv_path}")

    # Generate clean, publication-grade LaTeX Table code
    latex_code = summary.to_latex(
        index=False,
        escape=False,
        caption="Comparative Governance-Cost Performance across Multi-Agent Clinical Pipeline Variants (NVIDIA NIM meta/llama-3.2-11b-vision-instruct).",
        label="tab:governance_summary",
        column_format="llccccccc",
    )

    tex_path = OUTPUT_DIR / "variant_summary.tex"
    with open(tex_path, "w") as f:
        f.write(latex_code)
    print(f"Saved LaTeX: {tex_path}")


if __name__ == "__main__":
    main()
