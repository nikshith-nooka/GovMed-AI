"""FastAPI backend server for GovBench-Clinical interactive workbench."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from src.agents.base import is_parse_failure, parse_llm_json
from src.clinical.decision_support import build_case_response, collect_alerts
from src.evaluation.scorer import ClinicalEvaluationScorer, is_valid_gold_label
from src.llm.client import LiveInferenceUnavailable, UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.telemetry.db import BenchmarkDB

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="GovBench-Clinical API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("GOVBENCH_CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("GOVBENCH_DB_PATH", BASE_DIR / "results" / "benchmark_results.db"))
CURATED_PATH = BASE_DIR / "benchmarks" / "curated_sample.json"
RIGOR_REPORT_PATH = Path(os.getenv("GOVBENCH_RIGOR_REPORT", BASE_DIR / "results" / "rigor_report.json"))
FRONTEND_DIR = BASE_DIR / "client" / "dist"

GOVERNANCE_LEVELS = {
    "G0": ("baseline", "G0 (Baseline, no checks)"),
    "G1": ("verifier", "G1 (Grounding verifier)"),
    "G2": ("hitl", "G2 (Simulated attending review)"),
    "G3": ("safety", "G3 (Safety validator)"),
    "G4": ("full_governance", "G4 (All checks)"),
}
DEMO_NOTICE = (
    "DEMO MODE: output comes from a deterministic demo generator that recognizes a few specialties by keyword. "
    "It is NOT an analysis of this patient. Use a live model for real cases."
)


def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail=f"Benchmark database not found at {DB_PATH.name}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _load_cases() -> List[Dict[str, Any]]:
    if not CURATED_PATH.exists():
        return []
    return json.loads(CURATED_PATH.read_text(encoding="utf-8"))


_report_cache: Dict[str, Any] = {"mtime": None, "data": None}


def load_rigor_report() -> Optional[Dict[str, Any]]:
    if not RIGOR_REPORT_PATH.exists():
        return None
    mtime = RIGOR_REPORT_PATH.stat().st_mtime
    if _report_cache["mtime"] != mtime:
        _report_cache.update(mtime=mtime, data=json.loads(RIGOR_REPORT_PATH.read_text(encoding="utf-8")))
    return _report_cache["data"]


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "time": time.time(), "db_exists": DB_PATH.exists(),
            "rigor_report_exists": RIGOR_REPORT_PATH.exists()}


PROVIDER_ENV = {
    "groq": ("GROQ_API_KEYS", "GROQ_API_KEY"),
    "nvidia": ("NVIDIA_API_KEYS", "NVIDIA_API_KEY"),
    "gemini": ("GEMINI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
}


@app.get("/api/providers")
def get_providers():
    """Which live engines have a key configured (never returns key values)."""
    return {
        name: {"available": any(os.getenv(var, "").strip() for var in env_vars), "default_model": DEFAULT_MODELS.get(name)}
        for name, env_vars in PROVIDER_ENV.items()
    }


@app.get("/api/stats")
def get_benchmark_stats():
    """Aggregated benchmark KPIs. Returns zeros (not illustrative numbers) when there is no data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    total_runs = cursor.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    if total_runs == 0:
        conn.close()
        return {"has_data": False, "total_runs": 0, "total_cases": 0, "total_pool": 0, "completed_experiments": 0,
                "avg_diagnostic_quality": 0, "avg_token_cost": 0, "avg_latency": 0, "verification_rate": 0,
                "total_cost_usd": 0, "contraindications_blocked": 0, "hallucinations_caught": 0,
                "variant_breakdown": []}

    avg_accuracy = cursor.execute("SELECT AVG(diagnostic_accuracy_score) FROM runs").fetchone()[0] or 0
    avg_tokens = cursor.execute("SELECT AVG(total_tokens) FROM runs").fetchone()[0] or 0
    avg_latency = cursor.execute("SELECT AVG(total_latency_ms) / 1000.0 FROM runs").fetchone()[0] or 0
    total_cases = cursor.execute("SELECT COUNT(DISTINCT case_id) FROM runs").fetchone()[0] or 0
    verification_rate = (cursor.execute("SELECT COUNT(*) FROM runs WHERE hallucinations_detected = 0").fetchone()[0]
                         / total_runs) * 100.0
    total_cost_usd = cursor.execute("SELECT COALESCE(SUM(total_cost_usd), 0) FROM runs").fetchone()[0] or 0.0
    safety_alerts = cursor.execute("SELECT COALESCE(SUM(safety_violations_detected), 0) FROM runs").fetchone()[0] or 0
    hallucinations = cursor.execute("SELECT COALESCE(SUM(hallucinations_detected), 0) FROM runs").fetchone()[0] or 0
    variants = cursor.execute("""
        SELECT variant_name as variant, variant_id, COUNT(*) as runs,
               AVG(diagnostic_accuracy_score) as avg_acc, AVG(overall_quality_score) as avg_quality,
               AVG(total_tokens) as avg_tokens, AVG(total_latency_ms) / 1000.0 as avg_latency
        FROM runs GROUP BY variant_id, variant_name
    """).fetchall()
    conn.close()
    return {
        "has_data": True,
        "total_runs": total_runs,
        "total_cases": total_cases,
        "total_pool": total_cases,
        "completed_experiments": total_runs,
        "avg_diagnostic_quality": round(avg_accuracy * 100, 1),
        "avg_token_cost": int(avg_tokens),
        "avg_latency": round(avg_latency, 1),
        "verification_rate": round(verification_rate, 1),
        "total_cost_usd": total_cost_usd,
        # Kept for the dashboard; these are alerts raised, not validated hazards.
        "contraindications_blocked": safety_alerts,
        "safety_alerts_raised": safety_alerts,
        "hallucinations_caught": hallucinations,
        "variant_breakdown": [dict(row) for row in variants],
    }


@app.get("/api/cases")
def get_clinical_cases(specialty: Optional[str] = None, search: Optional[str] = None):
    cases = _load_cases()
    if specialty and specialty != "All":
        cases = [c for c in cases if c.get("specialty") == specialty]
    if search:
        s = search.lower()
        cases = [c for c in cases if s in c.get("question", "").lower()
                 or s in c.get("gold_diagnosis", "").lower() or s in c.get("id", "").lower()]
    return cases


@app.get("/api/runs")
def get_historical_runs(limit: int = 100, offset: int = 0, variant: Optional[str] = None):
    limit = max(1, min(limit, 500))
    conn = get_db_connection()
    cursor = conn.cursor()
    where, params = " WHERE 1=1", []
    if variant and variant != "All":
        where += " AND (variant_name = ? OR variant_id = ? OR variant_id = ?)"
        params.extend([variant, variant, f"{variant}-CL"])
    total = cursor.execute("SELECT COUNT(*) FROM runs" + where, params).fetchone()[0]
    rows = cursor.execute("SELECT * FROM runs" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                          params + [limit, max(0, offset)]).fetchall()
    conn.close()
    cases = {c["id"]: c for c in _load_cases()}
    return {"total": total, "runs": [measured_run(dict(r), cases.get(r["case_id"], {})) for r in rows]}


SYNTHETIC_COLUMNS = ("uncertainty_jru", "llm_judge_score", "rubric_quality_score", "risk_adjusted_quality",
                     "governance_efficiency_factor", "hitl_minutes", "hitl_human_cost", "raw_outputs_json")


def measured_run(row: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
    """Re-scores a stored run from its raw outputs; drops post-hoc columns."""
    raw = _recovered(json.loads(row.get("raw_outputs_json") or "{}"))
    diagnosis = raw.get("diagnosis", {}) or {}
    gold = case.get("gold_diagnosis", "")
    gold_valid = is_valid_gold_label(gold)
    diffs = [d for d in diagnosis.get("differential_diagnoses", []) or [] if isinstance(d, dict)]
    primary = str(diagnosis.get("primary_diagnosis", "") or "")
    out = {k: v for k, v in row.items() if k not in SYNTHETIC_COLUMNS}
    out.update({
        "dataset": str(row.get("case_id", "")).split("_")[0],
        "primary_diagnosis": primary,
        "gold_diagnosis": gold,
        "gold_valid": gold_valid,
        "measured_accuracy": _scorer.evaluate_diagnostic_match(primary, diffs, gold) if gold_valid else None,
        "safety_alerts": len((raw.get("safety") or {}).get("safety_flags", []) or []) if "safety" in raw else None,
        "hallucination_flagged": bool((raw.get("verifier") or {}).get("hallucination_detected")) if "verifier" in raw else None,
    })
    return out


@app.get("/api/research/findings")
def get_research_findings():
    report = load_rigor_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No analysis yet. Run: uv run python -m scripts.run_rigor_analysis")
    return report


class CustomCaseInput(BaseModel):
    chief_complaint: str = Field(..., min_length=2, max_length=500)
    hpi: str = Field(..., min_length=5, max_length=8000)
    age: Optional[str] = Field("", max_length=20)
    sex: Optional[str] = Field("", max_length=20)
    pmh: Optional[str] = Field("", max_length=4000)
    medications: Optional[str] = Field("", max_length=4000)
    allergies: Optional[str] = Field("", max_length=1000)
    vitals: Optional[str] = Field("", max_length=1000)
    labs: Optional[str] = Field("", max_length=4000)
    governance_level: str = "G4"
    provider: Literal["groq", "nvidia", "nim", "gemini", "openrouter", "simulation", "mock", "offline"] = "simulation"
    model: Optional[str] = Field(None, max_length=120)
    use_live_llm: bool = False
    closed_loop: bool = True

    @field_validator("chief_complaint", "hpi")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


def resolve_governance(level: str):
    raw = (level or "").upper()
    for code, (variant_key, label) in GOVERNANCE_LEVELS.items():
        if code in raw:
            return code, variant_key, label
    if "BASELINE" in raw:
        return ("G0",) + GOVERNANCE_LEVELS["G0"]
    return ("G4",) + GOVERNANCE_LEVELS["G4"]


def compose_case(case: CustomCaseInput) -> Dict[str, Any]:
    sections = [
        ("Patient", " ".join(x for x in (case.age, case.sex) if x)),
        ("Chief Complaint", case.chief_complaint),
        ("History of Present Illness", case.hpi),
        ("Past Medical History", case.pmh),
        ("Medications", case.medications),
        ("Allergies", case.allergies),
        ("Vitals", case.vitals),
        ("Labs/Findings", case.labs),
    ]
    text = "\n\n".join(f"{title}: {body}" for title, body in sections if body)
    return {"id": f"CASE-LIVE-{int(time.time() * 1000) % 10_000_000:07d}", "question": text,
            "chief_complaint": case.chief_complaint}


DEFAULT_MODELS = {"nvidia": "meta/llama-3.2-11b-vision-instruct", "groq": "openai/gpt-oss-120b"}


INTERACTIVE_REASONING_EFFORT = os.getenv("GOVBENCH_REASONING_EFFORT", "low")


def execute_pipeline(clinical_case: Dict[str, Any], variant_key: str, provider_choice: str, live: bool,
                     closed_loop: bool, model: Optional[str] = None, include_report: bool = True, on_step=None):
    """Runs the pipeline; returns (result, mode, provider_label, model_label). Live failures raise HTTP 502."""
    options = dict(variant_key=variant_key, closed_loop=closed_loop, include_report=include_report, on_step=on_step)
    if not live or provider_choice in ("simulation", "mock", "offline"):
        client = UnifiedLLMClient(provider="mock", force_mock=True)
        result = ClinicalGovernancePipeline(client).run(clinical_case, **options)
        return result, "SIMULATION", "DEMO", "Deterministic demo generator"
    provider = "nvidia" if provider_choice in ("nvidia", "nim") else provider_choice
    try:
        client = UnifiedLLMClient(provider=provider, model=model or DEFAULT_MODELS.get(provider),
                                  timeout_seconds=45.0, allow_mock_fallback=False,
                                  reasoning_effort=None if include_report else INTERACTIVE_REASONING_EFFORT)
        result = ClinicalGovernancePipeline(client).run(clinical_case, **options)
    except LiveInferenceUnavailable as exc:
        raise HTTPException(status_code=502, detail=f"Live model unavailable: {exc}. No result was generated.")
    except Exception as exc:
        logger.exception("Live pipeline failed")
        raise HTTPException(status_code=502, detail=f"Live pipeline failed: {exc}. No result was generated.")
    return result, "LIVE_LLM", provider.upper(), f"{provider} / {client.default_model}"


@app.post("/api/run-custom-case")
def run_custom_case(case_data: CustomCaseInput):
    """Runs the real multi-agent pipeline. Demo mode uses the deterministic mock LLM, clearly labelled."""
    return run_interactive_case(case_data)


def run_interactive_case(case_data: CustomCaseInput, on_step=None) -> Dict[str, Any]:
    """Interactive runs skip the SOAP report (not shown in the UI) and use low reasoning effort for speed."""
    code, variant_key, label = resolve_governance(case_data.governance_level)
    result, mode, provider_label, model_label = execute_pipeline(
        compose_case(case_data), variant_key, case_data.provider.lower(), case_data.use_live_llm,
        case_data.closed_loop, case_data.model, include_report=False, on_step=on_step)
    calibration = (load_rigor_report() or {}).get("calibration")
    response = build_case_response(result, code, mode, provider_label, model_label, calibration)
    response["notice"] = DEMO_NOTICE if mode == "SIMULATION" else None
    response["governance_label"] = label
    return response


# ---------------------------------------------------------------- background jobs with live progress
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()
MAX_JOBS = 200
# Bounded so a burst of requests queues instead of spawning unlimited live-API threads.
_job_pool = ThreadPoolExecutor(max_workers=int(os.getenv("GOVBENCH_JOB_WORKERS", "4")))


@app.post("/api/jobs/run-case")
def start_case_job(case_data: CustomCaseInput):
    """Starts an interactive run in the background; poll GET /api/jobs/{id} for per-agent progress."""
    code, variant_key, _ = resolve_governance(case_data.governance_level)
    planned = [layer + (" Agent" if layer in ("Research", "Diagnosis", "Verifier") else "")
               for layer in ClinicalGovernancePipeline.AVAILABLE_VARIANTS[variant_key]["layers"] if layer != "Report"]
    job_id = uuid.uuid4().hex
    job = {"id": job_id, "status": "running", "started": time.time(), "finished": None,
           "planned": planned, "steps": {}, "result": None, "error": None}
    with _jobs_lock:
        _jobs[job_id] = job
        finished = sorted((k for k, j in _jobs.items() if j["status"] != "running"), key=lambda k: _jobs[k]["started"])
        for old in finished[: max(0, len(_jobs) - MAX_JOBS)]:
            _jobs.pop(old, None)

    def on_step(event: str, agent: str, step) -> None:
        with _jobs_lock:
            entry = job["steps"].setdefault(agent, {"agent": agent, "status": "running", "started": time.time()})
            if event == "done":
                entry.update(status="done", latency_s=round(step.latency_ms / 1000.0, 1), tokens=step.total_tokens)

    def work() -> None:
        try:
            result = run_interactive_case(case_data, on_step=on_step)
            with _jobs_lock:
                job.update(status="done", result=result, finished=time.time())
        except HTTPException as exc:
            with _jobs_lock:
                job.update(status="error", error=exc.detail, finished=time.time())
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            with _jobs_lock:
                job.update(status="error", error=f"Unexpected error: {exc}", finished=time.time())

    _job_pool.submit(work)
    return {"job_id": job_id, "planned": planned}


@app.get("/api/jobs/{job_id}")
def get_case_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown or expired job")
        end = job["finished"] or time.time()
        return {"id": job_id, "status": job["status"], "elapsed_s": round(end - job["started"], 1),
                "planned": job["planned"], "steps": list(job["steps"].values()),
                "result": job["result"], "error": job["error"]}


# ---------------------------------------------------------------- experiments on benchmark cases
EXPERIMENT_DB_PATH = Path(os.getenv("GOVBENCH_EXPERIMENT_DB", BASE_DIR / "results" / "ui_experiments.db"))
_scorer = ClinicalEvaluationScorer()


class ExperimentCaseInput(BaseModel):
    case_id: str = Field(..., max_length=120)
    governance_level: str = "G4"
    provider: Literal["groq", "nvidia", "nim", "gemini", "openrouter", "simulation", "mock", "offline"] = "simulation"
    closed_loop: bool = True


@app.post("/api/experiments/run-case")
def run_experiment_case(inp: ExperimentCaseInput):
    """Runs one benchmark case, scores it against its gold label, and stores it in the experiments DB."""
    case = next((c for c in _load_cases() if c["id"] == inp.case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Unknown case {inp.case_id}")
    code, variant_key, label = resolve_governance(inp.governance_level)
    choice = inp.provider.lower()
    result, mode, provider_label, model_label = execute_pipeline(
        case, variant_key, choice, choice not in ("simulation", "mock", "offline"), inp.closed_loop)
    scored = _scorer.score_run(result, case)
    run_id = BenchmarkDB(str(EXPERIMENT_DB_PATH)).log_run(scored)
    support = build_case_response(scored, code, mode, provider_label, model_label)["decision_support"]
    gold_valid = is_valid_gold_label(case.get("gold_diagnosis"))
    return {
        "run_id": run_id,
        "case_id": case["id"],
        "dataset": case["id"].split("_")[0],
        "specialty": case.get("specialty"),
        "governance": label,
        "variant_id": scored.variant_id,
        "mode": mode,
        "model": model_label,
        "gold_diagnosis": case.get("gold_diagnosis"),
        "gold_valid": gold_valid,
        "primary_diagnosis": scored.primary_diagnosis,
        "accuracy": scored.diagnostic_accuracy_score if gold_valid else None,
        "alerts": len(support["alerts"]),
        "high_alerts": len(support["escalate_now"]),
        "hallucination_flagged": bool(scored.hallucinations_detected),
        "revision_applied": scored.revision_applied,
        "initial_diagnosis": scored.initial_primary_diagnosis,
        "parse_failures": scored.parse_failures,
        "latency_s": round(sum(s.latency_ms for s in scored.agent_steps) / 1000.0, 2),
        "tokens": scored.total_tokens,
        "cost_usd": scored.total_cost_usd,
    }


@app.get("/api/experiments/runs")
def list_experiment_runs(limit: int = 200):
    if not EXPERIMENT_DB_PATH.exists():
        return {"total": 0, "runs": []}
    with sqlite3.connect(str(EXPERIMENT_DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, case_id, variant_id, model, provider, primary_diagnosis, diagnostic_accuracy_score, "
            "gold_label_valid, safety_violations_detected, hallucinations_detected, revision_applied, total_tokens, "
            "total_cost_usd, timestamp FROM runs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    return {"total": total, "runs": [dict(r) for r in rows]}


# ---------------------------------------------------------------- clinician review
def _recovered(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (parse_llm_json(v.get("raw_text", "")) if is_parse_failure(v) else v) for k, v in raw.items()}


@app.get("/api/reviews/queue")
def get_review_queue(reviewer_id: str, limit: int = 5):
    """Blinded review items: the variant is hidden so reviewers cannot favour governed outputs."""
    reviewer_id = reviewer_id.strip()[:80]
    if not reviewer_id:
        raise HTTPException(status_code=422, detail="reviewer_id is required")
    BenchmarkDB(str(DB_PATH))  # ensures the clinician_reviews table exists
    cases = {c["id"]: c for c in _load_cases()}
    with sqlite3.connect(str(DB_PATH)) as conn:
        done = {r[0] for r in conn.execute("SELECT run_id FROM clinician_reviews WHERE reviewer_id = ?", (reviewer_id,))}
        # Closed-loop rows are excluded: their alerts refer to the pre-revision diagnosis.
        rows = conn.execute("SELECT id, case_id, raw_outputs_json FROM runs WHERE variant_id NOT LIKE '%-CL'").fetchall()
    pending = [r for r in rows if r[0] not in done and r[1] in cases]
    pending.sort(key=lambda r: hashlib.sha256(f"{reviewer_id}:{r[0]}".encode()).hexdigest())
    items = []
    for run_id, case_id, raw_json in pending[: max(1, min(limit, 20))]:
        raw = _recovered(json.loads(raw_json or "{}"))
        diagnosis = raw.get("diagnosis", {}) or {}
        items.append({
            "run_id": run_id,
            "case_id": case_id,
            "case_text": cases[case_id].get("question", ""),
            "primary_diagnosis": diagnosis.get("primary_diagnosis"),
            "differentials": [
                {"condition": d.get("condition"), "justification": d.get("justification", "")}
                for d in diagnosis.get("differential_diagnoses", []) or [] if isinstance(d, dict)
            ],
            "next_steps": diagnosis.get("recommended_next_steps", []) or [],
            # Source is omitted: it would reveal which governance variant produced the output.
            "alerts": [{"index": i, "severity": a["severity"], "category": a["category"], "description": a["description"]}
                       for i, a in enumerate(collect_alerts(raw))],
        })
    return {"reviewer_id": reviewer_id, "remaining": len(pending), "items": items}


class AlertRating(BaseModel):
    index: int = Field(..., ge=0)
    verdict: Literal["valid", "invalid", "unsure"]


class ClinicianReviewInput(BaseModel):
    run_id: int
    case_id: str = Field(..., max_length=120)
    reviewer_id: str = Field(..., min_length=1, max_length=80)
    reviewer_role: Literal["physician", "resident", "nurse", "physician_assistant", "pharmacist", "other"] = "physician"
    diagnosis_verdict: Literal["correct", "acceptable", "incorrect", "unsure"]
    quality_rating: int = Field(..., ge=1, le=5)
    alert_ratings: List[AlertRating] = []
    missed_hazards: str = Field("", max_length=2000)
    comments: str = Field("", max_length=2000)


@app.post("/api/reviews")
def submit_review(review: ClinicianReviewInput):
    BenchmarkDB(str(DB_PATH))
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute("SELECT case_id FROM runs WHERE id = ?", (review.run_id,)).fetchone()
    if row is None or row[0] != review.case_id:
        raise HTTPException(status_code=404, detail="Run not found for this case")
    payload = review.model_dump()
    payload["created_at"] = time.time()
    BenchmarkDB(str(DB_PATH)).save_clinician_review(payload)
    return {"saved": True}


@app.get("/api/reviews/summary")
def review_summary():
    df = BenchmarkDB(str(DB_PATH)).get_clinician_reviews_df()
    if df.empty:
        return {"n_reviews": 0, "n_reviewers": 0, "alert_precision": None, "verdicts": {}}
    ratings = [a for s in df["alert_ratings"] for a in json.loads(s or "[]") if a.get("verdict") in ("valid", "invalid")]
    return {
        "n_reviews": int(len(df)),
        "n_reviewers": int(df["reviewer_id"].nunique()),
        "alert_precision": round(sum(a["verdict"] == "valid" for a in ratings) / len(ratings), 3) if ratings else None,
        "n_alerts_rated": len(ratings),
        "verdicts": df["diagnosis_verdict"].value_counts().to_dict(),
        "mean_quality_rating": round(float(df["quality_rating"].mean()), 2),
    }


# ---------------------------------------------------------------- reports
@app.get("/api/reports/latex")
def get_latex_report():
    tex_path = BASE_DIR / "paper" / "tables" / "rigor_variants.tex"
    if not tex_path.exists():
        tex_path = BASE_DIR / "paper" / "tables" / "variant_summary.tex"
    if tex_path.exists():
        return PlainTextResponse(tex_path.read_text(encoding="utf-8"), media_type="text/plain")
    return PlainTextResponse("% LaTeX table not generated yet", media_type="text/plain")


@app.get("/api/reports/csv")
def get_csv_report():
    import pandas as pd

    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM runs", conn)
    conn.close()
    return PlainTextResponse(df.to_csv(index=False), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=govbench_benchmark_runs.csv"})


if FRONTEND_DIR.exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    frontend_root = FRONTEND_DIR.resolve()

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        file_path = (FRONTEND_DIR / full_path).resolve()
        if full_path and file_path.is_file() and frontend_root in file_path.parents:
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
