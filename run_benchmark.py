#!/usr/bin/env python3
"""GovBench-Clinical Benchmark CLI Runner."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from dotenv import load_dotenv

from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.data.loader import ClinicalDatasetLoader
from src.evaluation.scorer import ClinicalEvaluationScorer
from src.evaluation.statistics import BenchmarkStatistics
from src.telemetry.db import BenchmarkDB

# Load .env cleanly
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("govbench")
console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="GovBench-Clinical: Benchmark Framework for Quantifying Governance-Cost Tradeoffs"
    )
    parser.add_argument(
        "--cases",
        type=int,
        default=5,
        help="Number of clinical cases to benchmark (default: 5)",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default="baseline",
        choices=["baseline", "verifier", "hitl", "safety", "full_governance", "all"],
        help="Pipeline variant to test (default: baseline, or 'all' to run full ablation)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        choices=["groq", "gemini", "openrouter", "mock"],
        help="LLM provider backend (default: groq)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Specific model name override",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="curated",
        choices=["curated", "medqa", "pubmedqa", "meddialog", "stratified", "equal_1000", "all_dbs_1000"],
        help="Data source (curated benchmark cases, HuggingFace MedQA, PubMedQA, MedDialog, stratified mix, or 1000 from each medical DB)",

    )

    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in offline deterministic mock mode (no API key required)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="results/benchmark_results.db",
        help="SQLite database storage path",
    )
    return parser.parse_args()


def display_results_table(summary_df):
    """Displays a rich terminal table of results."""
    table = Table(title="[bold green]GovBench-Clinical Benchmark Summary[/bold green]", show_header=True)
    table.add_column("Variant ID", style="cyan", no_wrap=True)
    table.add_column("Variant Name", style="bold white")
    table.add_column("Cases", justify="right")
    table.add_column("Quality", justify="right", style="green")
    table.add_column("Accuracy", justify="right", style="green")
    table.add_column("Tokens", justify="right", style="yellow")
    table.add_column("Latency (ms)", justify="right", style="magenta")
    table.add_column("Cost ($)", justify="right", style="yellow")
    table.add_column("Hallucinations", justify="right", style="red")

    for _, row in summary_df.iterrows():
        table.add_row(
            str(row["variant_id"]),
            str(row["variant_name"]),
            str(row["total_cases"]),
            f"{row['avg_quality']:.3f}",
            f"{row['avg_accuracy']:.1%}",
            f"{row['avg_tokens']:,.0f}",
            f"{row['avg_latency_ms']:,.0f}",
            f"${row['avg_cost_usd']:.5f}",
            f"{row['avg_hallucinations']:.2f}",
        )
    console.print(table)


def main():
    args = parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]GovBench-Clinical[/bold cyan] : [white]Multi-Agent Governance-Cost Benchmark[/white]\n"
            f"[dim]Provider: {args.provider.upper()} | Mode: {'MOCK' if args.mock else 'LIVE'} | Variant: {args.variant} | Cases: {args.cases}[/dim]",
            border_style="blue",
        )
    )

    # API key check
    if not args.mock:
        key_var = f"{args.provider.upper()}_API_KEY"
        api_key = os.getenv(key_var)
        if not api_key:
            console.print(
                f"[bold red]Warning:[/bold red] Environment variable [bold yellow]{key_var}[/bold yellow] is not set.\n"
                f"Falling back safely to high-fidelity offline mock mode.\n"
                f"To run live with Groq: [bold green]export GROQ_API_KEY='your_key'[/bold green]"
            )
            args.mock = True

    # Initialize components
    llm_client = UnifiedLLMClient(
        provider=args.provider,
        model=args.model,
        force_mock=args.mock,
    )
    pipeline = ClinicalGovernancePipeline(llm_client)
    data_loader = ClinicalDatasetLoader()
    scorer = ClinicalEvaluationScorer()
    db = BenchmarkDB(args.db_path)

    # Load dataset
    cases = data_loader.get_benchmark_cases(requested_count=args.cases, source=args.source)
    console.print(f"Loaded [bold green]{len(cases)}[/bold green] clinical evaluation cases.")

    # Determine variants to execute
    if args.variant == "all":
        variants_to_run = list(ClinicalGovernancePipeline.AVAILABLE_VARIANTS.keys())
    else:
        variants_to_run = [args.variant]

    total_executions = len(cases) * len(variants_to_run)
    console.print(f"Executing [bold cyan]{total_executions}[/bold cyan] pipeline runs...")

    for v_key in variants_to_run:
        v_name = ClinicalGovernancePipeline.AVAILABLE_VARIANTS[v_key]["name"]
        console.print(f"\n[bold yellow]► Testing Variant: {v_name} ({v_key})[/bold yellow]")

        for case in track(cases, description=f"Running {v_name}..."):
            # 1. Run pipeline
            run_result = pipeline.run(case, variant_key=v_key)

            # 2. Score output
            scored_result = scorer.score_run(run_result, case)

            # 3. Log to SQLite
            db.log_run(scored_result)

    # Output Summary
    summary_df = db.get_variant_summary()
    console.print("\n")
    display_results_table(summary_df)

    # Marginal ROI analysis if multiple variants run
    runs_df = db.get_runs_df()
    if len(runs_df["variant_id"].unique()) > 1:
        roi_df = BenchmarkStatistics.compute_marginal_roi(runs_df)
        console.print("\n[bold green]Marginal Governance ROI Analysis (vs Baseline V1):[/bold green]")
        for _, r in roi_df.iterrows():
            if r["variant_id"] != "V1":
                console.print(
                    f" • [bold cyan]{r['variant_name']}[/bold cyan]: "
                    f"Δ Quality: [green]+{r['delta_quality_pct']}%[/green] | "
                    f"Δ Tokens: [yellow]+{r['delta_tokens_pct']}%[/yellow] | "
                    f"Δ Latency: [magenta]+{r['delta_latency_pct']}%[/magenta] | "
                    f"ROI: [bold]{r['quality_gain_per_1k_tokens']} pts / 1k tokens[/bold]"
                )

    console.print(f"\nAll run logs saved to: [bold white]{args.db_path}[/bold white]\n")


if __name__ == "__main__":
    main()
