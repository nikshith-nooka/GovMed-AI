#!/usr/bin/env python3
"""Fault-tolerant, checkpointed clinical governance benchmark runner.

Research and Diagnosis are computed once per case and shared by every variant. Variants run
one at a time by default (``--variant-workers 1``) so per-call latency is not inflated by
contention; raise it only when throughput matters more than latency measurement.

    uv run govbench --benchmark benchmarks/medqa_300.json --total-cases 300 \\
        --provider groq --judge-provider nvidia --loop-modes open,closed
    uv run govbench --benchmark benchmarks/medqa_300.json --dry-run --provider groq

Every stored run records generator model/provider, per-step model and temperature, the
seed and the judge model. ``--resume`` (default) skips runs already stored for the same
case_id + variant + model, so an interrupted run continues without re-spending tokens.
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
import random
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from dotenv import load_dotenv

# Ensure root is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.loader import ClinicalDatasetLoader  # noqa: E402
from src.evaluation.llm_judge import LLMJudgeAgent, SameModelJudgeError  # noqa: E402
from src.evaluation.scorer import ClinicalEvaluationScorer  # noqa: E402
from src.llm.client import UnifiedLLMClient  # noqa: E402
from src.pipeline.orchestrator import ClinicalGovernancePipeline  # noqa: E402
from src.telemetry.db import BenchmarkDB  # noqa: E402

load_dotenv()

logger = logging.getLogger("full_benchmark")

SHARED_AGENTS = ("Research Agent", "Diagnosis Agent")
JUDGE_AGENT = "LLM Judge Agent"
REVISION_AGENT = "Diagnosis Agent (Revision)"
# Free-tier tokens-per-minute per API key; override with --tpm.
DEFAULT_TPM_PER_KEY = {"groq": 8000}
# Free-tier tokens-per-day for the whole organisation (Groq applies it across all keys of one account,
# so pooling keys does not raise it); override with --tpd.
DEFAULT_TPD_PER_ORG = {"groq": 200_000}
KEY_ENV = {"groq": ("GROQ_API_KEYS", "GROQ_API_KEY"), "nvidia": ("NVIDIA_API_KEYS", "NVIDIA_API_KEY"),
           "nim": ("NVIDIA_API_KEYS", "NVIDIA_API_KEY"), "gemini": (None, "GEMINI_API_KEY"),
           "openrouter": (None, "OPENROUTER_API_KEY")}


def setup_logging() -> None:
    os.makedirs("results", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("results/full_benchmark_run.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ---------------------------------------------------------------- provenance
class GenerationRecorder:
    """Wraps a client's generate() to record the model and temperature of every call.

    Agent step logs do not carry sampling parameters, so each response is keyed by
    (prompt_tokens, completion_tokens, latency_ms) - the fields a step log copies from it -
    and annotate() writes model/temperature back onto matching steps. Thread-safe.
    """

    def __init__(self, client: Any):
        self.client = client
        self._orig = client.generate
        self._calls: Dict[Tuple[int, int, float], Tuple[str, float]] = {}
        self._lock = threading.Lock()
        client.generate = self._generate

    def _generate(self, messages, temperature: float = 0.2, max_tokens: int = 1500, model_override=None):
        resp = self._orig(messages, temperature=temperature, max_tokens=max_tokens, model_override=model_override)
        model = getattr(resp, "model", "") or model_override or getattr(self.client, "default_model", "")
        with self._lock:
            self._calls[(resp.prompt_tokens, resp.completion_tokens, resp.latency_ms)] = (model, float(temperature))
        return resp

    def annotate(self, steps: List[Any]) -> Dict[str, Any]:
        """Sets step.model / step.temperature; returns {agent_name: {model, temperature}}."""
        config: Dict[str, Any] = {}
        with self._lock:
            for step in steps:
                hit = self._calls.get((step.prompt_tokens, step.completion_tokens, step.latency_ms))
                if hit:
                    step.model, step.temperature = hit
                    config[step.agent_name] = {"model": hit[0], "temperature": hit[1]}
        return config


# ---------------------------------------------------------------- checkpointing
def is_already_completed(db_path: str, case_id: str, variant_id: str, model: Optional[str] = None) -> bool:
    """True when a run for this case + variant (+ model, if given) is already stored."""
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            query = "SELECT 1 FROM runs WHERE case_id = ? AND variant_id = ?"
            params: List[Any] = [str(case_id), str(variant_id)]
            if model:
                query += " AND model = ?"
                params.append(model)
            return conn.execute(query + " LIMIT 1", params).fetchone() is not None
    except Exception:
        return False


def variant_run_id(v_key: str, args) -> str:
    base = ClinicalGovernancePipeline.AVAILABLE_VARIANTS[v_key]["id"]
    return base + "-CL" if getattr(args, "closed_loop", False) and v_key != "baseline" else base


def should_skip(args, case_id: str, v_id: str) -> bool:
    return bool(args.resume) and is_already_completed(args.db_path, case_id, v_id, args.generator_model)


def run_single_variant(v_key, case, case_id, c_idx, total_cases, cached_res, cached_diag, pipeline, scorer, judge,
                       db, args, lock, counter_obj, recorders):
    """Executes a single governance variant for a case using pre-computed diagnosis/research cache."""
    v_info = ClinicalGovernancePipeline.AVAILABLE_VARIANTS[v_key]
    v_id = variant_run_id(v_key, args)

    if should_skip(args, case_id, v_id):
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

        result = pipeline.run(case, variant_key=v_key, cached_research=cached_res, cached_diagnosis=cached_diag,
                              closed_loop=args.closed_loop)
        judge_scores = None
        if judge is not None:
            judge_scores, judge_step = judge.execute(result.raw_outputs, case)
            result.agent_steps.append(judge_step)
            result.raw_outputs["llm_judge"] = judge_scores
        scored = scorer.score_run(result, case, judge_scores=judge_scores)

        config: Dict[str, Any] = {}
        for rec in recorders:
            config.update(rec.annotate(scored.agent_steps))
        scored.temperature_config = config
        scored.seed = args.seed
        scored.provider_seed_applied = args.seed is not None  # forwarded to the provider as a best-effort seed

        with lock:
            db.log_run(scored)
            counter_obj["completed"] += 1
            curr_done = counter_obj["completed"]

        logger.info(
            f"Saved Run {curr_done}: Case={case_id}, Variant={v_info['name']}, "
            f"Accuracy={scored.diagnostic_accuracy_score:.2f} ({scored.scoring_mode}), "
            f"Tokens={scored.total_tokens:,}, Latency={scored.total_latency_ms:.0f}ms, Cost=${scored.total_cost_usd:.5f}"
        )
    except Exception as e:
        logger.error(f"Error executing Case '{case_id}' on {v_key}: {e}. Skipping run.")


def process_case(case, c_idx, total_cases, variants, pipeline, scorer, judge, db, args, lock, counter_obj, recorders):
    """Processes all governance variants for a single clinical case."""
    case_id = str(case.get("id", f"case_{c_idx:04d}"))

    pending_variants = [v_key for v_key in variants if not should_skip(args, case_id, variant_run_id(v_key, args))]
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
        with lock:
            counter_obj["skipped"] += len(pending_variants)
        return

    with ThreadPoolExecutor(max_workers=max(1, min(len(pending_variants), args.variant_workers))) as variant_executor:
        v_futures = [
            variant_executor.submit(
                run_single_variant,
                v_key, case, case_id, c_idx, total_cases,
                cached_res, cached_diag,
                pipeline, scorer, judge, db, args, lock, counter_obj, recorders,
            )
            for v_key in pending_variants
        ]
        for f in as_completed(v_futures):
            try:
                f.result()
            except Exception as exc:
                logger.error(f"Variant execution generated exception: {exc}")


# ---------------------------------------------------------------- dry run
def count_api_keys(provider: str) -> int:
    """Number of configured keys for a provider (values are never read out)."""
    pooled, single = KEY_ENV.get(provider, (None, None))
    if pooled and os.getenv(pooled, "").strip():
        return len([k for k in os.getenv(pooled, "").split(",") if k.strip()])
    return 1 if single and os.getenv(single, "").strip() else 0


def measured_step_means(db_path: str, model: Optional[str]) -> Tuple[Dict[Tuple[str, str], Dict[str, float]], str]:
    """Mean prompt/completion tokens and latency per (variant_id, agent_name) from stored runs.

    Uses rows for ``model`` when present, else all rows (the returned basis says which).
    """
    import pandas as pd

    if not Path(db_path).exists():
        return {}, "no database"
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT s.variant_id, s.agent_name, s.prompt_tokens, s.completion_tokens, s.latency_ms, r.model "
            "FROM agent_steps s JOIN runs r ON r.id = s.run_id", conn)
    basis = "all stored runs"
    if model and (df["model"] == model).any():
        df, basis = df[df["model"] == model], f"stored runs of {model}"
    elif model:
        basis = f"all stored runs (none for {model}; token counts are a proxy)"
    means = df.groupby(["variant_id", "agent_name"])[["prompt_tokens", "completion_tokens", "latency_ms"]].mean()
    return {k: v.to_dict() for k, v in means.iterrows()}, basis


def estimate_plan(cases: List[Dict[str, Any]], variants: List[str], loop_modes: List[str], args,
                  means: Dict[Tuple[str, str], Dict[str, float]], generator_model: str,
                  judge_model: Optional[str]) -> Dict[str, Any]:
    """Tokens / cost / wall time for the planned runs, from measured per-step means."""
    rates = UnifiedLLMClient.PRICING_TABLE.get(generator_model, {"input": 0.50, "output": 0.80})
    judge_rates = UnifiedLLMClient.PRICING_TABLE.get(judge_model or "", {"input": 0.50, "output": 0.80})
    notes: List[str] = []
    zero = {"prompt_tokens": 0.0, "completion_tokens": 0.0, "latency_ms": 0.0}

    def step(vid: str, agent: str) -> Dict[str, float]:
        return means.get((vid, agent)) or means.get((vid.replace("-CL", ""), agent)) or zero

    def agents_of(vid: str) -> List[str]:
        own = sorted({a for v, a in means if v == vid})
        return own or sorted({a for v, a in means if v == vid.replace("-CL", "")})

    rows, totals = [], {"runs": 0, "prompt": 0.0, "completion": 0.0, "latency_s": 0.0, "cost": 0.0}
    for mode in loop_modes:
        mode_args = copy.copy(args)
        mode_args.closed_loop = mode == "closed"
        shared = [step("V1", a) for a in SHARED_AGENTS]
        planned_cases = 0
        for v_key in variants:
            vid = variant_run_id(v_key, mode_args)
            if mode == "closed" and vid == "V1" and "open" in loop_modes:
                continue  # baseline has no closed-loop form; it is shared with the open-loop pass
            pending = sum(not (args.resume and is_already_completed(args.db_path, str(c.get("id")), vid, generator_model))
                          for c in cases)
            per_run = [step(vid, a) for a in agents_of(vid) if a not in SHARED_AGENTS and a != JUDGE_AGENT]
            if mode == "closed" and vid.endswith("-CL") and not any(v == vid for v, _ in means):
                per_run.append(step("V1", "Diagnosis Agent"))  # upper bound: one revision per run
                notes.append(f"{vid}: no closed-loop rows stored; assumed one revision call per run (upper bound).")
            p = sum(s["prompt_tokens"] for s in per_run)
            c_ = sum(s["completion_tokens"] for s in per_run)
            lat = sum(s["latency_ms"] for s in per_run) / 1000.0
            cost = pending * (p * rates["input"] + c_ * rates["output"]) / 1e6
            jp = jc = 0.0
            if judge_model:
                j = step(vid, JUDGE_AGENT)
                if j is zero:
                    # The judge reads the full run output: approximate its prompt by the run's tokens.
                    jp, jc = p + c_ + sum(s["prompt_tokens"] + s["completion_tokens"] for s in shared), 400.0
                else:
                    jp, jc = j["prompt_tokens"], j["completion_tokens"]
                cost += pending * (jp * judge_rates["input"] + jc * judge_rates["output"]) / 1e6
            rows.append({"loop_mode": mode, "variant_id": vid, "pending_runs": pending,
                         "tokens_per_run": round(p + c_ + jp + jc), "cost_usd": round(cost, 4)})
            totals["runs"] += pending
            totals["prompt"] += pending * (p + jp)
            totals["completion"] += pending * (c_ + jc)
            totals["latency_s"] += pending * lat / max(1, args.variant_workers)
            totals["cost"] += cost
            planned_cases = max(planned_cases, pending)
        # Shared research + diagnosis run once per case that has any pending variant.
        sp = sum(s["prompt_tokens"] for s in shared)
        sc = sum(s["completion_tokens"] for s in shared)
        totals["prompt"] += planned_cases * sp
        totals["completion"] += planned_cases * sc
        totals["latency_s"] += planned_cases * sum(s["latency_ms"] for s in shared) / 1000.0
        totals["cost"] += planned_cases * (sp * rates["input"] + sc * rates["output"]) / 1e6
        if not any(v == "V1" for v, _ in means):
            notes.append("No stored V1 steps: shared Research/Diagnosis cost is unknown (counted as 0).")

    tokens = totals["prompt"] + totals["completion"]
    keys = count_api_keys(args.provider)
    tpm_key = args.tpm or DEFAULT_TPM_PER_KEY.get(args.provider)
    latency_min = totals["latency_s"] / max(1, args.workers) / 60.0
    rate_min = tokens / (tpm_key * max(1, keys)) if tpm_key else None
    tpd = args.tpd or DEFAULT_TPD_PER_ORG.get(args.provider)
    days_min = tokens / tpd * 24 * 60 if tpd else None  # daily quota: minutes of calendar time
    return {"daily_quota_bound_min": None if days_min is None else round(days_min, 1), "tpd": tpd,
            "rows": rows, "runs": totals["runs"], "tokens": round(tokens), "cost_usd": round(totals["cost"], 4),
            "latency_bound_min": round(latency_min, 1), "rate_limit_bound_min": None if rate_min is None else round(rate_min, 1),
            "estimated_wall_min": round(max(latency_min, rate_min or 0.0, days_min or 0.0), 1), "api_keys": keys,
            "tpm_per_key": tpm_key, "notes": sorted(set(notes))}


def print_estimate(est: Dict[str, Any], basis: str, n_cases: int, args, generator_model: str,
                   judge_model: Optional[str]) -> None:
    print(f"\nDRY RUN - nothing is called. Estimates from {basis} in {args.db_path}.")
    print(f"Generator: {args.provider} / {generator_model}   Judge: {judge_model or 'disabled'}   "
          f"Cases: {n_cases}   Loop modes: {args.loop_modes}   Resume: {args.resume}")
    print(f"{'loop':<7}{'variant':<9}{'pending':>9}{'tokens/run':>12}{'cost USD':>11}")
    for r in est["rows"]:
        print(f"{r['loop_mode']:<7}{r['variant_id']:<9}{r['pending_runs']:>9}{r['tokens_per_run']:>12,}{r['cost_usd']:>11.4f}")
    print(f"\nPending runs: {est['runs']:,}   Tokens: {est['tokens']:,}   Cost: ${est['cost_usd']:.4f}")
    rate = (f"{est['rate_limit_bound_min']} min at {est['tpm_per_key']:,} TPM x {est['api_keys']} key(s)"
            if est["rate_limit_bound_min"] is not None else "no TPM limit given (--tpm)")
    print(f"Time: latency-bound {est['latency_bound_min']} min ({args.workers} case worker(s), "
          f"{args.variant_workers} variant worker(s)); rate-limit-bound {rate}.")
    if est.get("daily_quota_bound_min") is not None:
        print(f"Daily quota: {est['tpd']:,} tokens/day per organisation -> {est['daily_quota_bound_min'] / 1440:.1f} day(s) "
              f"of quota (keys on the same account share it).")
    wall = est["estimated_wall_min"]
    print(f"Estimated wall time: {wall} min (~{wall / 60:.1f} h, ~{wall / 1440:.1f} days)")
    for note in est["notes"]:
        print(f"  note: {note}")


# ---------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the clinical governance benchmark.",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--total-cases", type=int, default=2000, help="Cases to run (default: 2000)")
    parser.add_argument("--provider", type=str, default="nvidia", help="Generator LLM provider (default: nvidia)")
    parser.add_argument("--model", type=str, default=None, help="Generator model (provider default if omitted)")
    parser.add_argument("--source", type=str, default="50_each", help="Dataset source when --benchmark is not given")
    parser.add_argument("--benchmark", type=str, default=None,
                        help="Frozen benchmark JSON, e.g. benchmarks/medqa_300.json (overrides --source)")
    parser.add_argument("--workers", type=int, default=3, help="Parallel cases (default: 3)")
    parser.add_argument("--db-path", type=str, default="results/benchmark_results.db")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (Python/NumPy); recorded per run")
    parser.add_argument("--closed-loop", action="store_true",
                        help="Feed governance concerns back to the Diagnosis Agent (variant ids get a -CL suffix)")
    parser.add_argument("--loop-modes", type=str, default=None,
                        help="Comma list of open,closed to run/estimate both passes (default: from --closed-loop)")
    parser.add_argument("--variant-workers", type=int, default=1,
                        help="Concurrent variants per case (default 1: contention-free latency measurement)")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                        help="Skip runs already stored for the same case_id + variant + model (default: on)")
    parser.add_argument("--judge-provider", type=str, default=None,
                        help="Provider for the LLM judge; must yield a different model than the generator. "
                             "Omit to disable the judge (JRU then stays a grounding proxy).")
    parser.add_argument("--judge-model", type=str, default=None)
    parser.add_argument("--allow-same-model-judge", action="store_true",
                        help="Permit a same-model judge; its verdicts are flagged and excluded from JRU")
    parser.add_argument("--dry-run", action="store_true", help="Print estimated tokens / cost / time and exit")
    parser.add_argument("--tpm", type=int, default=None,
                        help="Tokens-per-minute limit per API key for --dry-run (Groq free tier default: 8000)")
    parser.add_argument("--tpd", type=int, default=None,
                        help="Tokens-per-day limit per organisation for --dry-run (Groq free tier default: 200000)")
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    setup_logging()
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
    loop_modes = [m.strip() for m in (args.loop_modes or ("closed" if args.closed_loop else "open")).split(",") if m.strip()]
    if not set(loop_modes) <= {"open", "closed"}:
        raise SystemExit(f"--loop-modes must be a comma list of open,closed (got {args.loop_modes})")
    args.loop_modes = ",".join(loop_modes)

    data_loader = ClinicalDatasetLoader()
    if args.benchmark:
        cases = data_loader.load_benchmark_file(args.benchmark, limit=args.total_cases)
    else:
        cases = data_loader.get_benchmark_cases(requested_count=args.total_cases, source=args.source)
    variants = list(ClinicalGovernancePipeline.AVAILABLE_VARIANTS.keys())

    if args.dry_run:
        # Resolves the provider's default model name only; no request is made.
        generator_model = UnifiedLLMClient(provider=args.provider, model=args.model, allow_mock_fallback=True).default_model
        judge_model = None
        if args.judge_provider:
            judge_model = UnifiedLLMClient(provider=args.judge_provider, model=args.judge_model,
                                           allow_mock_fallback=True).default_model
        args.generator_model = generator_model
        means, basis = measured_step_means(args.db_path, generator_model)
        est = estimate_plan(cases, variants, loop_modes, args, means, generator_model, judge_model)
        print_estimate(est, basis, len(cases), args, generator_model, judge_model)
        return

    # Strict: a failed live call skips that run instead of logging simulated output as a real result.
    client = UnifiedLLMClient(provider=args.provider, model=args.model, force_mock=False, allow_mock_fallback=False)
    client.seed = args.seed
    args.generator_model = client.default_model
    recorders = [GenerationRecorder(client)]
    judge = None
    if args.judge_provider:
        try:
            judge = LLMJudgeAgent.from_config(args.judge_provider, args.judge_model, client.default_model,
                                              allow_same_model=args.allow_same_model_judge,
                                              force_mock=False, allow_mock_fallback=False)
        except SameModelJudgeError as e:
            raise SystemExit(str(e)) from e
        recorders.append(GenerationRecorder(judge.llm_client))
    else:
        logger.warning("No --judge-provider: the LLM judge is disabled (a same-model judge is not an independent rater).")

    pipeline = ClinicalGovernancePipeline(client)
    scorer = ClinicalEvaluationScorer()
    db = BenchmarkDB(args.db_path)

    logger.info("=================================================================")
    logger.info(f"BENCHMARK: {len(cases)} cases x {len(variants)} variants x loop modes {loop_modes}")
    logger.info(f"Generator: {args.provider} / {client.default_model} | Judge: "
                f"{judge.judge_model if judge else 'disabled'} | Source: {args.benchmark or args.source} | "
                f"DB: {args.db_path} | seed={args.seed} | resume={args.resume}")
    logger.info("=================================================================")

    lock = threading.Lock()
    for mode in loop_modes:
        args.closed_loop = mode == "closed"
        mode_variants = [v for v in variants if not (mode == "closed" and v == "baseline" and "open" in loop_modes)]
        counter_obj = {"completed": 0, "skipped": 0, "total": len(cases) * len(mode_variants)}
        logger.info(f"Loop mode '{mode}': {counter_obj['total']} executions planned "
                    f"({args.workers} case workers x {args.variant_workers} variant workers)")
        with ThreadPoolExecutor(max_workers=args.workers) as case_executor:
            futures = [
                case_executor.submit(process_case, case, c_idx, len(cases), mode_variants, pipeline, scorer, judge,
                                     db, args, lock, counter_obj, recorders)
                for c_idx, case in enumerate(cases, 1)
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.error(f"Case worker generated exception: {exc}")
        logger.info(f"Loop mode '{mode}' complete. Completed: {counter_obj['completed']}, "
                    f"Skipped: {counter_obj['skipped']}")


if __name__ == "__main__":
    main()
