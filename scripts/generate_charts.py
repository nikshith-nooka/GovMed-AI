#!/usr/bin/env python3
"""Generate publication-quality charts from ablation analysis results.

Outputs 4 figures to paper/figures/:
  1. governance_cost_curve.png  – dual-axis quality + tokens vs variant
  2. ablation_results.png       – marginal quality gain per governance layer
  3. latency_breakdown.png      – stacked per-agent latency per variant
  4. cost_effectiveness.png     – scatter: token cost vs quality improvement
"""

from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

from src.evaluation.statistics import BenchmarkStatistics
from src.analysis.frontier import GovernanceEfficiencyFrontier

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "results" / "benchmark_results.db"
FIG_DIR = PROJECT_ROOT / "paper" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Publication styling
# ---------------------------------------------------------------------------
sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

COLORS = ["#2563EB", "#059669", "#D97706", "#DC2626", "#7C3AED"]
AGENT_COLORS = {
    "diagnosis": "#3B82F6",
    "research": "#10B981",
    "report": "#F59E0B",
    "verifier": "#EF4444",
    "safety": "#8B5CF6",
    "hitl": "#EC4899",
    "consistency": "#6366F1",
}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_runs_df() -> pd.DataFrame:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    with sqlite3.connect(str(DB_PATH)) as conn:
        return pd.read_sql_query("SELECT * FROM runs ORDER BY id", conn)


def load_agent_steps_df() -> pd.DataFrame:
    with sqlite3.connect(str(DB_PATH)) as conn:
        return pd.read_sql_query(
            "SELECT * FROM agent_steps ORDER BY id", conn
        )


def variant_summary(runs_df: pd.DataFrame) -> pd.DataFrame:
    return (
        runs_df
        .groupby(["variant_id", "variant_name"])
        .agg(
            avg_quality=("overall_quality_score", "mean"),
            std_quality=("overall_quality_score", "std"),
            avg_tokens=("total_tokens", "mean"),
            std_tokens=("total_tokens", "std"),
            avg_latency_ms=("total_latency_ms", "mean"),
            std_latency_ms=("total_latency_ms", "std"),
            count=("id", "count"),
        )
        .reset_index()
        .sort_values("variant_id")
    )


def ci95_for_group(df: pd.DataFrame, col: str) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) using BenchmarkStatistics."""
    m, lo, hi = BenchmarkStatistics.compute_ci_95(df[col])
    return m, lo, hi


# ---------------------------------------------------------------------------
# Chart 1: Governance Cost Curve (dual axis)
# ---------------------------------------------------------------------------

def plot_governance_cost_curve(runs_df: pd.DataFrame) -> None:
    summary = variant_summary(runs_df)

    # Compute 95% CI for quality and tokens
    ci_rows = []
    for _, grp in runs_df.groupby(["variant_id", "variant_name"]):
        q_m, q_lo, q_hi = ci95_for_group(grp, "overall_quality_score")
        t_m, t_lo, t_hi = ci95_for_group(grp, "total_tokens")
        ci_rows.append({
            "variant_id": grp["variant_id"].iloc[0],
            "variant_name": grp["variant_name"].iloc[0],
            "avg_quality": q_m, "q_err_lo": q_m - q_lo, "q_err_hi": q_hi - q_m,
            "avg_tokens": t_m, "t_err_lo": t_m - t_lo, "t_err_hi": t_hi - t_m,
        })
    ci_df = pd.DataFrame(ci_rows).sort_values("variant_id")

    x = np.arange(len(ci_df))

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax2 = ax1.twinx()

    # Quality on left axis
    bars = ax1.bar(
        x - 0.18, ci_df["avg_quality"], 0.36,
        yerr=[ci_df["q_err_lo"], ci_df["q_err_hi"]],
        color=COLORS[: len(ci_df)], edgecolor="black", linewidth=0.6,
        capsize=3, label="Avg Quality", zorder=3,
    )
    ax1.set_ylabel("Composite Quality Score")
    ax1.set_ylim(0, 1.05)

    # Tokens on right axis
    ax2.plot(
        x, ci_df["avg_tokens"], "s--", color="#1E3A8A",
        markersize=8, linewidth=1.5, label="Avg Tokens", zorder=4,
    )
    ax2.fill_between(
        x,
        ci_df["avg_tokens"] - ci_df["t_err_lo"],
        ci_df["avg_tokens"] + ci_df["t_err_hi"],
        alpha=0.12, color="#1E3A8A",
    )
    ax2.set_ylabel("Total Tokens per Case")

    ax1.set_xticks(x)
    ax1.set_xticklabels(ci_df["variant_id"], rotation=0)
    ax1.set_xlabel("Governance Variant")
    ax1.set_title("Governance Cost Curve: Quality vs Token Consumption")

    # Combined legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="lower right", framealpha=0.9)

    plt.tight_layout()
    out = FIG_DIR / "governance_cost_curve.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"  ✓ {out}")


# ---------------------------------------------------------------------------
# Chart 2: Ablation Results – marginal quality gain per layer
# ---------------------------------------------------------------------------

def plot_ablation_results(runs_df: pd.DataFrame) -> None:
    base = runs_df[runs_df["variant_id"] == "V1"]
    if base.empty:
        print("  ⚠ No V1 baseline – skipping ablation chart")
        return
    base_q = base["overall_quality_score"].mean()

    layer_labels = ["None\n(V1)", "Verifier", "HITL", "Safety", "Consistency"]
    variant_ids = ["V1", "V2", "V3", "V4", "V5"]
    gains = []
    errs = []
    for vid in variant_ids:
        grp = runs_df[runs_df["variant_id"] == vid]
        if grp.empty:
            gains.append(0.0)
            errs.append(0.0)
            continue
        m, lo, hi = ci95_for_group(grp, "overall_quality_score")
        gains.append(m - base_q)
        errs.append(hi - m)

    x = np.arange(len(layer_labels))
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(
        x, gains, color=COLORS[: len(gains)],
        edgecolor="black", linewidth=0.6, zorder=3,
    )
    ax.errorbar(
        x, gains, yerr=errs, fmt="none", ecolor="black",
        capsize=4, linewidth=1, zorder=4,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(layer_labels)
    ax.set_ylabel("Δ Quality vs Baseline (V1)")
    ax.set_xlabel("Governance Layer Added")
    ax.set_title("Ablation: Marginal Quality Gain per Governance Layer")
    ax.axhline(0, color="grey", linewidth=0.8, linestyle="--")
    ax.grid(axis="y", alpha=0.4)

    plt.tight_layout()
    out = FIG_DIR / "ablation_results.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"  ✓ {out}")


# ---------------------------------------------------------------------------
# Chart 3: Latency Breakdown – stacked per-agent latency
# ---------------------------------------------------------------------------

def plot_latency_breakdown(runs_df: pd.DataFrame, steps_df: pd.DataFrame) -> None:
    if steps_df.empty:
        print("  ⚠ No agent_steps data – skipping latency breakdown chart")
        return

    pivot = (
        steps_df
        .groupby(["variant_id", "agent_name"])["latency_ms"]
        .mean()
        .unstack(fill_value=0)
    )
    pivot = pivot.sort_index()

    agent_names = list(pivot.columns)
    colors = [AGENT_COLORS.get(a, "#999999") for a in agent_names]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    pivot.plot(kind="bar", stacked=True, ax=ax, color=colors,
               edgecolor="white", linewidth=0.4)

    ax.set_xlabel("Governance Variant")
    ax.set_ylabel("Mean Latency (ms)")
    ax.set_title("Per-Agent Latency Breakdown by Variant")
    ax.legend(title="Agent", bbox_to_anchor=(1.02, 1), loc="upper left", framealpha=0.9)
    plt.xticks(rotation=0)
    plt.tight_layout()

    out = FIG_DIR / "latency_breakdown.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"  ✓ {out}")


# ---------------------------------------------------------------------------
# Chart 4: Cost-Effectiveness scatter
# ---------------------------------------------------------------------------

def plot_cost_effectiveness(runs_df: pd.DataFrame) -> None:
    base = runs_df[runs_df["variant_id"] == "V1"]
    if base.empty:
        print("  ⚠ No V1 baseline – skipping cost-effectiveness chart")
        return
    base_q = base["overall_quality_score"].mean()
    base_t = base["total_tokens"].mean()

    records = []
    for vid, grp in runs_df.groupby("variant_id"):
        q_m, q_lo, q_hi = ci95_for_group(grp, "overall_quality_score")
        t_m, _, _ = ci95_for_group(grp, "total_tokens")
        add_tok = t_m - base_t
        imp = q_m - base_q
        ce = imp / add_tok if add_tok > 0 else 0.0
        records.append({
            "variant_id": vid,
            "token_cost": add_tok,
            "quality_improvement": imp,
            "cost_effectiveness": ce,
            "q_err": q_hi - q_m,
        })

    cedf = pd.DataFrame(records)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    scatter = ax.scatter(
        cedf["token_cost"], cedf["quality_improvement"],
        s=140, c=COLORS[: len(cedf)],
        edgecolor="black", linewidth=0.8, zorder=3,
    )
    for _, row in cedf.iterrows():
        ax.annotate(
            row["variant_id"],
            (row["token_cost"], row["quality_improvement"]),
            textcoords="offset points", xytext=(6, 6),
            fontweight="bold", fontsize=9,
        )

    # Reference line from origin
    valid = cedf[cedf["token_cost"] > 0]
    if not valid.empty:
        slope = valid["quality_improvement"].max() / valid["token_cost"].max()
        ax.plot(
            [0, cedf["token_cost"].max()],
            [0, slope * cedf["token_cost"].max()],
            "k--", alpha=0.3, linewidth=1,
        )

    ax.set_xlabel("Additional Tokens vs Baseline")
    ax.set_ylabel("Quality Improvement vs Baseline")
    ax.set_title("Cost-Effectiveness: Token Spend vs Quality Gain")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = FIG_DIR / "cost_effectiveness.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"  ✓ {out}")


# ---------------------------------------------------------------------------
# Chart 5: Governance Efficiency Frontier (GEF Pareto Optimal Curve)
# ---------------------------------------------------------------------------

def plot_gef_pareto(runs_df: pd.DataFrame) -> None:
    analyzer = GovernanceEfficiencyFrontier(str(DB_PATH))
    frontier_df = analyzer.compute_frontier(use_risk_adjusted=True)
    if frontier_df.empty:
        print("  ⚠ No data for GEF Pareto chart")
        return

    fig, ax = plt.subplots(figsize=(7.5, 4.8))

    frontier_pts = pd.DataFrame(frontier_df[frontier_df["is_pareto_frontier"]]).sort_values(by=["avg_tokens"])
    dominated_pts = pd.DataFrame(frontier_df[~frontier_df["is_pareto_frontier"]])

    # Plot frontier curve
    if not frontier_pts.empty:
        ax.plot(
            frontier_pts["avg_tokens"],
            frontier_pts["risk_adjusted_quality"],
            "o--",
            color="#059669",
            linewidth=2.2,
            markersize=9,
            label="Pareto Efficient Frontier",
            zorder=4,
        )

    # Plot dominated points
    if not dominated_pts.empty:
        ax.scatter(
            dominated_pts["avg_tokens"],
            dominated_pts["risk_adjusted_quality"],
            color="#DC2626",
            s=120,
            marker="x",
            linewidths=2.2,
            label="Dominated Governance Variants",
            zorder=5,
        )

    # Custom offsets for clean label layout without overlaps or clipping
    offsets = {
        "V1": (10, -15),
        "V2": (10, -16),
        "V3": (-130, 8),
        "V4": (-150, 10),
        "V5": (-175, -20),
    }

    # Annotations
    for _, row in frontier_df.iterrows():
        vid = row["variant_id"]
        vname = row["variant_name"].split("(")[0].strip()
        if vid == "V4":
            label = f"{vid}: {vname} (Optimal Knee)"
            bbox = dict(boxstyle="round,pad=0.25", fc="#ECFDF5", ec="#059669", lw=1.2, alpha=0.95)
        else:
            label = f"{vid}: {vname}"
            bbox = dict(boxstyle="round,pad=0.2", fc="white", ec="#9CA3AF", lw=0.8, alpha=0.9)

        xytext = offsets.get(vid, (8, 5))
        ax.annotate(
            label,
            (row["avg_tokens"], row["risk_adjusted_quality"]),
            textcoords="offset points",
            xytext=xytext,
            fontsize=8.5,
            fontweight="bold" if vid == "V4" else "semibold",
            bbox=bbox,
            zorder=6,
        )

    ax.set_xlim(2600, 9400)
    ax.set_ylim(0.35, 0.73)
    ax.set_xlabel("Mean Total Tokens per Case (Cost Proxy)")
    ax.set_ylabel(r"Risk-Adjusted Quality $Q_{\text{adj}}$ (Risk-Penalized Utility, Eq. 3)")
    ax.set_title("Governance Efficiency Frontier (GEF): Pareto Optimal Trade-offs")
    ax.legend(loc="lower left", framealpha=0.92, bbox_to_anchor=(0.04, 0.18))
    ax.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()
    out = FIG_DIR / "gef_pareto.png"
    plt.savefig(out, dpi=300)
    plt.savefig(FIG_DIR / "gef_pareto.pdf", dpi=300)
    plt.close()
    print(f"  ✓ {out}")


# ---------------------------------------------------------------------------
# Chart 6: Judge/Rubric Uncertainty (JRU) Disagreement Distribution
# ---------------------------------------------------------------------------

def plot_jru_uncertainty(runs_df: pd.DataFrame) -> None:
    analyzer = GovernanceEfficiencyFrontier(str(DB_PATH))
    unc_df = analyzer.compute_uncertainty_summary()
    if unc_df.empty:
        print("  ⚠ No data for JRU Uncertainty chart")
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(unc_df))

    y_err_lo = unc_df["uncertainty_mean"] - unc_df["uncertainty_ci_lower"]
    y_err_hi = unc_df["uncertainty_ci_upper"] - unc_df["uncertainty_mean"]

    bars = ax.bar(
        x,
        unc_df["uncertainty_mean"],
        color=COLORS[: len(unc_df)],
        edgecolor="black",
        linewidth=0.6,
        yerr=[y_err_lo, y_err_hi],
        capsize=4,
        zorder=3,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(unc_df["variant_id"])
    ax.set_xlabel("Governance Variant")
    ax.set_ylabel("Mean JRU Uncertainty ($|\\text{Rubric} - \\text{Judge}|$)")
    ax.set_title("Evaluation Uncertainty across Governance Variants (95% CI)")
    ax.grid(axis="y", alpha=0.3)

    # Annotate bar values
    for idx, val in enumerate(unc_df["uncertainty_mean"].tolist()):
        ax.text(
            float(idx),
            float(val) + 0.015,
            f"{float(val):.3f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    plt.tight_layout()
    out = FIG_DIR / "jru_uncertainty_by_variant.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"  ✓ {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_all_charts() -> None:
    """Generate all 6 publication figures."""
    print("Loading benchmark data...")
    runs_df = load_runs_df()
    steps_df = load_agent_steps_df()
    print(f"  {len(runs_df)} runs, {len(steps_df)} agent steps loaded.\n")

    print("Generating charts:")
    plot_governance_cost_curve(runs_df)
    plot_ablation_results(runs_df)
    plot_latency_breakdown(runs_df, steps_df)
    plot_cost_effectiveness(runs_df)
    plot_gef_pareto(runs_df)
    plot_jru_uncertainty(runs_df)
    print("\nAll charts saved to paper/figures/")


if __name__ == "__main__":
    generate_all_charts()
