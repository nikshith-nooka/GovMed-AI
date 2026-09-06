#!/usr/bin/env python3
"""Generates 300-DPI publication figures from SQLite benchmark database for IEEE paper."""

from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Plot styling for IEEE Papers
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 12,
    "figure.dpi": 300,
})

OUTPUT_DIR = Path("paper/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("results/benchmark_results.db")


def load_data():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found.")
        sys.exit(1)
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM runs", conn)
    return df


def plot_governance_cost_curve(df: pd.DataFrame):
    """Figure 1: Quality vs. Token Cost (Pareto Frontier)."""
    summary = df.groupby(["variant_id", "variant_name"]).agg(
        avg_quality=("overall_quality_score", "mean"),
        avg_tokens=("total_tokens", "mean"),
        avg_accuracy=("diagnostic_accuracy_score", "mean"),
        count=("id", "count"),
    ).reset_index().sort_values("avg_tokens")

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = ["#2563EB", "#059669", "#D97706", "#DC2626", "#7C3AED"]

    ax.plot(summary["avg_tokens"], summary["avg_quality"], "k--", alpha=0.5, zorder=1)
    scatter = ax.scatter(
        summary["avg_tokens"],
        summary["avg_quality"],
        s=120,
        c=colors[:len(summary)],
        edgecolor="black",
        linewidth=1,
        zorder=2,
    )

    for _, row in summary.iterrows():
        ax.annotate(
            f"{row['variant_id']}: {row['variant_name'].split()[0]}",
            (row["avg_tokens"], row["avg_quality"]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontweight="bold",
        )

    ax.set_xlabel("Total Tokens Consumed per Case")
    ax.set_ylabel("Composite Diagnostic Quality (0 - 1.0)")
    ax.set_title("Figure 1: Governance-Cost Pareto Frontier in Clinical AI")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()

    out_path = OUTPUT_DIR / "governance_cost_curve.pdf"
    plt.savefig(out_path, dpi=300)
    plt.savefig(OUTPUT_DIR / "governance_cost_curve.png", dpi=300)
    print(f"Saved: {out_path}")
    plt.close()


def plot_ablation_metrics(df: pd.DataFrame):
    """Figure 2: Multi-attribute comparison across variants."""
    summary = df.groupby("variant_name").agg(
        Diagnostic_Accuracy=("diagnostic_accuracy_score", "mean"),
        Evidence_Grounding=("evidence_grounding_score", "mean"),
        Overall_Quality=("overall_quality_score", "mean"),
    ).reset_index()

    melted = summary.melt(id_vars="variant_name", var_name="Metric", value_name="Score")

    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(data=melted, x="variant_name", y="Score", hue="Metric", ax=ax, palette="Set2")

    ax.set_xlabel("Pipeline Variant")
    ax.set_ylabel("Score (0.0 - 1.0)")
    ax.set_title("Figure 2: Component Ablation on Diagnostic Quality & Grounding")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.legend(title="Metric", loc="lower right")
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    plt.tight_layout()

    out_path = OUTPUT_DIR / "ablation_results.pdf"
    plt.savefig(out_path, dpi=300)
    plt.savefig(OUTPUT_DIR / "ablation_results.png", dpi=300)
    print(f"Saved: {out_path}")
    plt.close()


def plot_latency_breakdown(df: pd.DataFrame):
    """Figure 3: End-to-End Latency vs. Safety Violations Detected."""
    summary = df.groupby("variant_name").agg(
        Latency_s=("total_latency_ms", lambda x: x.mean() / 1000.0),
        Safety_Flags=("safety_violations_detected", "mean"),
    ).reset_index()

    fig, ax1 = plt.subplots(figsize=(6.5, 4))
    ax2 = ax1.twinx()

    x = np.arange(len(summary))
    width = 0.35

    b1 = ax1.bar(x - width/2, summary["Latency_s"], width, label="Mean Latency (s)", color="#3B82F6")
    b2 = ax2.bar(x + width/2, summary["Safety_Flags"], width, label="Safety Hazards Flagged", color="#EF4444")

    ax1.set_xlabel("Pipeline Variant")
    ax1.set_ylabel("End-to-End Latency (seconds)", color="#1E3A8A")
    ax2.set_ylabel("Safety Flags Caught", color="#991B1B")
    ax1.set_xticks(x)
    ax1.set_xticklabels(summary["variant_name"], rotation=15, ha="right")
    ax1.set_title("Figure 3: Latency Overhead vs. Safety Violations Detected")
    plt.tight_layout()

    out_path = OUTPUT_DIR / "latency_breakdown.pdf"
    plt.savefig(out_path, dpi=300)
    plt.savefig(OUTPUT_DIR / "latency_breakdown.png", dpi=300)
    print(f"Saved: {out_path}")
    plt.close()


def main():
    df = load_data()
    print(f"Loaded {len(df)} runs from SQLite. Generating publication figures...")
    plot_governance_cost_curve(df)
    plot_ablation_metrics(df)
    plot_latency_breakdown(df)
    print("All publication figures successfully created in paper/figures/")


if __name__ == "__main__":
    main()
