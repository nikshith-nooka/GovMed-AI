#!/usr/bin/env python3
"""Concurrency smoke test: many cases at once, reporting latency percentiles and failures.

In-process (mock LLM, temp DB) checks pipeline + SQLite thread safety:
    uv run python -m scripts.load_test --requests 200 --concurrency 16
Against a running server in demo mode:
    uv run python -m scripts.load_test --url http://localhost:8001 --requests 50 --concurrency 8
"""

from __future__ import annotations

import argparse
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import numpy as np

from src.evaluation.scorer import ClinicalEvaluationScorer
from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.telemetry.db import BenchmarkDB

PROMPTS = [
    "58M with tearing chest pain radiating to the back, BP 190/110.",
    "54M with acute knee pain, effusion, CKD 3b, negatively birefringent crystals.",
    "Room-spinning vertigo with nausea for 6 hours, no focal deficits.",
    "Migratory RLQ abdominal pain, anorexia, fever 38.2C.",
    "Fever 39.5C but WBC 4.2; patient denies fever.",
]
VARIANTS = ["baseline", "verifier", "safety", "full_governance"]


def run_in_process(i: int, db: BenchmarkDB) -> float:
    start = time.perf_counter()
    case = {"id": f"load_{i}", "question": PROMPTS[i % len(PROMPTS)], "gold_diagnosis": "Aortic Dissection"}
    pipeline = ClinicalGovernancePipeline(UnifiedLLMClient(provider="mock", force_mock=True))
    result = pipeline.run(case, VARIANTS[i % len(VARIANTS)], closed_loop=True)
    db.log_run(ClinicalEvaluationScorer().score_run(result, case))
    return time.perf_counter() - start


def run_http(i: int, url: str) -> float:
    start = time.perf_counter()
    resp = httpx.post(f"{url}/api/run-custom-case", timeout=120, json={
        "chief_complaint": PROMPTS[i % len(PROMPTS)][:60], "hpi": PROMPTS[i % len(PROMPTS)],
        "governance_level": ["G0", "G1", "G3", "G4"][i % 4], "provider": "simulation"})
    resp.raise_for_status()
    return time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--url", default=None, help="Base URL of a running server (demo mode only)")
    args = parser.parse_args()

    tmp = tempfile.TemporaryDirectory()
    db = None if args.url else BenchmarkDB(str(Path(tmp.name) / "load.db"))
    latencies, errors = [], []
    wall = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_http, i, args.url) if args.url else pool.submit(run_in_process, i, db)
                   for i in range(args.requests)]
        for future in as_completed(futures):
            try:
                latencies.append(future.result())
            except Exception as exc:
                errors.append(repr(exc))
    wall = time.perf_counter() - wall

    lat = np.array(latencies) if latencies else np.array([float("nan")])
    print(f"mode={'http ' + args.url if args.url else 'in-process mock'} requests={args.requests} "
          f"concurrency={args.concurrency}")
    print(f"ok={len(latencies)} failed={len(errors)} throughput={len(latencies) / wall:.1f}/s")
    print(f"latency p50={np.percentile(lat, 50):.3f}s p95={np.percentile(lat, 95):.3f}s max={lat.max():.3f}s")
    if db is not None:
        print(f"rows persisted={len(db.get_runs_df())}")
    for err in errors[:5]:
        print("  error:", err)
    tmp.cleanup()


if __name__ == "__main__":
    main()
