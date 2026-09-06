#!/usr/bin/env python3
"""Fault-tolerant, checkpointed, parallel multi-threaded clinical governance benchmark runner.
Accelerated with both Inter-Case and Inter-Variant Concurrency for maximal throughput.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv

# Ensure root is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.data.loader import ClinicalDatasetLoader
from src.evaluation.scorer import ClinicalEvaluationScorer
from src.telemetry.db import BenchmarkDB

load_dotenv()

# Configure dedicated file and console logging
os.makedirs("results", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("results/full_benchmark_run.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("full_benchmark")


def is_already_completed(db_path: str, case_id: str, variant_id: str) -> bool:
    """Checks SQLite database to skip already executed cases (zero wasted tokens)."""
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM runs WHERE case_id = ? AND variant_id = ? LIMIT 1",
                (str(case_id), str(variant_id)),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def run_single_variant(v_key, case, case_id, c_idx, total_cases, cached_res, cached_diag, pipeline, scorer, db, args, lock, counter_obj):
    """Executes a single governance variant for a case using pre-computed diagnosis/research cache."""
    v_info = ClinicalGovernancePipeline.AVAILABLE_VARIANTS[v_key]
    v_id = v_info["id"]

    if is_already_completed(args.db_path, case_id, v_id):
        with lock:
            counter_obj["skipped"] += 1
        return

    try:
        with lock:
            current_total = counter_obj["completed"] + counter_obj["skipped"] + 1
        logger.info(
            f"[{current_total}/{counter_obj['total']}] [Case {c_idx}/{total_cases}] "
            f"Running '{case_id}' on {v_info['name']}..."
        )

        result = pipeline.run(case, variant_key=v_key, cached_research=cached_res, cached_diagnosis=cached_diag)
        scored = scorer.score_run(result, case)

        with lock:
            db.log_run(scored)
            counter_obj["completed"] += 1
            curr_done = counter_obj["completed"]

        logger.info(
            f"✓ Saved Run {curr_done}: Case={case_id}, Variant={v_info['name']}, "
            f"Quality={scored.overall_quality_score:.3f}, Tokens={scored.total_tokens:,}, "
            f"Latency={scored.total_latency_ms:.0f}ms, Cost=${scored.total_cost_usd:.5f}"
        )
    except Exception as e:
        logger.error(f"Error executing Case '{case_id}' on {v_key}: {e}. Skipping run.")


def process_case(case, c_idx, total_cases, variants, pipeline, scorer, db, args, lock, counter_obj):
    """Processes all 5 governance variants for a single clinical case concurrently."""
    case_id = str(case.get("id", f"case_{c_idx:04d}"))

    # Determine which variants are pending for this case
    pending_variants = [
        v_key for v_key in variants
        if not is_already_completed(args.db_path, case_id, ClinicalGovernancePipeline.AVAILABLE_VARIANTS[v_key]["id"])
    ]

    if not pending_variants:
        with lock:
            counter_obj["skipped"] += len(variants)
        return

    # Compute shared research & diagnosis once for this case
    try:
        findings, step1 = pipeline.research_agent.execute(case)
        options = case.get("options")
        diagnosis_output, step2 = pipeline.diagnosis_agent.execute(findings, case_options=options)
        cached_res = (findings, step1)
        cached_diag = (diagnosis_output, step2)
    except Exception as e:
        logger.error(f"Error generating baseline diagnosis for Case '{case_id}': {e}. Skipping case.")
        return

    # Execute all pending governance variants concurrently for this case
    with ThreadPoolExecutor(max_workers=min(len(pending_variants), 5)) as variant_executor:
        v_futures = [
            variant_executor.submit(
                run_single_variant,
                v_key, case, case_id, c_idx, total_cases,
                cached_res, cached_diag,
                pipeline, scorer, db, args, lock, counter_obj
            )
            for v_key in pending_variants
        ]
        for f in as_completed(v_futures):
            try:
                f.result()
            except Exception as exc:
                logger.error(f"Variant execution generated exception: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Run full-scale clinical governance benchmark.")
    parser.add_argument("--total-cases", type=int, default=2000, help="Total cases to run (default: 2000)")
    parser.add_argument("--provider", type=str, default="nvidia", help="LLM Provider (default: nvidia)")
    parser.add_argument("--source", type=str, default="50_each", help="Dataset source (default: 50_each)")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel concurrent cases (default: 3)")
    parser.add_argument("--db-path", type=str, default="results/benchmark_results.db")
    args = parser.parse_args()

    logger.info("=================================================================")
    logger.info(f"STARTING ACCELERATED BENCHMARK: {args.total_cases} CASES across 5 VARIANTS")
    logger.info(f"Provider: {args.provider.upper()} | Source: {args.source.upper()} | DB: {args.db_path}")
    logger.info("=================================================================")

    # Initialize components
    client = UnifiedLLMClient(provider=args.provider, force_mock=False)
    pipeline = ClinicalGovernancePipeline(client)
    data_loader = ClinicalDatasetLoader()
    scorer = ClinicalEvaluationScorer()
    db = BenchmarkDB(args.db_path)

    # Ingest stratified dataset
    logger.info("Assembling stratified dataset population (MedQA, PubMedQA, MedDialog)...")
    cases = data_loader.get_benchmark_cases(requested_count=args.total_cases, source=args.source)
    logger.info(f"Loaded {len(cases)} clinical benchmark cases successfully.")

    variants = list(ClinicalGovernancePipeline.AVAILABLE_VARIANTS.keys())
    total_runs_planned = len(cases) * len(variants)
    logger.info(f"Total pipeline executions planned: {total_runs_planned}")

    lock = threading.Lock()
    counter_obj = {
        "completed": 0,
        "skipped": 0,
        "total": total_runs_planned,
    }

    # Parallel execution: processes 3 cases in parallel, each case evaluating its variants concurrently
    logger.info(f"Launching multi-tiered concurrency ({args.workers} cases x 5 concurrent variants)...")
    with ThreadPoolExecutor(max_workers=args.workers) as case_executor:
        futures = [
            case_executor.submit(process_case, case, c_idx, len(cases), variants, pipeline, scorer, db, args, lock, counter_obj)
            for c_idx, case in enumerate(cases, 1)
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.error(f"Case worker generated exception: {exc}")

    logger.info("=================================================================")
    logger.info(f"BENCHMARK BATCH COMPLETE! Completed: {counter_obj['completed']}, Skipped: {counter_obj['skipped']}")
    logger.info("=================================================================")


if __name__ == "__main__":
    main()
