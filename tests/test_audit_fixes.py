"""Regression tests for the 2026-10-10 audit fixes (docs/REPAIR_LOG.md)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from scripts.run_full_benchmark import load_shared_upstream
from src.analysis.rigor import RigorousAnalysis
from src.evaluation.scorer import ClinicalEvaluationScorer
from src.llm import client as client_mod
from src.llm.client import LLMResponse, UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.telemetry.db import BenchmarkDB
from src.telemetry.metrics import AgentStepLog

SENTINEL = "ZEBRA-SENTINEL-GOLD"
CASE = {"id": "medqa_test_1", "question": "A 60-year-old man has crushing chest pain for 2 hours.",
        "options": {"A": "Myocardial infarction", "B": "Pneumothorax", "C": "Gout", "D": "Migraine"},
        "answer": "A", "answer_idx": "A", "answer_text": SENTINEL, "gold_diagnosis": SENTINEL,
        "explanation": SENTINEL}


class StubClient(UnifiedLLMClient):
    """Answers by agent; agents named in `garbage` get unparseable text. Records every prompt."""

    def __init__(self, garbage=()):
        super().__init__(provider="mock", force_mock=True)
        self.garbage, self.prompts = set(garbage), []

    def generate(self, messages, temperature=0.2, max_tokens=1500, model_override=None):
        system = messages[0]["content"]
        self.prompts.append(json.dumps(messages))
        agent = next((k for k in ("Consistency", "Attending", "Fact Verifier", "Safety", "Diagnostic Clinician",
                                  "Research", "Documentation") if k in system), "?")
        body = {"Consistency": {"consistency_status": "CONSISTENT", "inconsistencies_found": []},
                "Attending": {"decision": "APPROVED"},
                "Fact Verifier": {"verification_status": "VERIFIED", "hallucination_detected": False},
                "Safety": {"safety_flags": []},
                "Diagnostic Clinician": {"primary_diagnosis": "Myocardial infarction", "differential_diagnoses": []},
                "Research": {"chief_complaint": "chest pain"},
                "Documentation": {"assessment": "x"}}.get(agent, {})
        content = "not json at all" if agent in self.garbage else json.dumps(body)
        return LLMResponse(content=content, prompt_tokens=10, completion_tokens=5, total_tokens=15, latency_ms=7.0,
                           model=self.default_model, provider=self.provider)


def test_ground_truth_never_reaches_any_agent():
    stub = StubClient()
    pipeline = ClinicalGovernancePipeline(stub)
    for variant in ClinicalGovernancePipeline.AVAILABLE_VARIANTS:
        pipeline.run(dict(CASE), variant, closed_loop=True)
    assert stub.prompts and not any(SENTINEL in p for p in stub.prompts)
    assert not any('"answer_idx"' in p or '"gold_diagnosis"' in p for p in stub.prompts)


def test_cached_upstream_latency_is_counted_in_total():
    pipeline = ClinicalGovernancePipeline(StubClient())
    research = ({"chief_complaint": "chest pain"}, AgentStepLog("Research Agent", "r", latency_ms=1500.0))
    diagnosis = ({"primary_diagnosis": "Myocardial infarction"}, AgentStepLog("Diagnosis Agent", "d", latency_ms=2500.0))
    result = pipeline.run(dict(CASE), "baseline", cached_research=research, cached_diagnosis=diagnosis,
                          include_report=False)
    assert result.total_latency_ms >= 4000.0  # was ~0 ms before the fix
    timing = result.raw_outputs["timing"]
    assert timing["upstream_cached_ms"] == 4000.0 and timing["governance_ms"] < 1000.0


def test_failed_checks_are_not_recorded_as_passes():
    pipeline = ClinicalGovernancePipeline(StubClient(garbage={"Consistency", "Attending"}))
    result = pipeline.run(dict(CASE), "full_governance")
    assert result.hitl_decision == "PARSE_FAILURE"
    assert not any("Consistency Check Passed" in f for f in result.governance_flags)
    assert any("Consistency Check FAILED" in f for f in result.governance_flags)
    assert {"consistency", "hitl"} <= set(result.parse_failures)


def test_closed_loop_pass_reuses_stored_open_loop_diagnosis(tmp_path):
    db_path = str(tmp_path / "runs.db")
    pipeline = ClinicalGovernancePipeline(StubClient())
    db = BenchmarkDB(db_path)
    db.log_run(ClinicalEvaluationScorer().score_run(pipeline.run(dict(CASE), "baseline"), CASE))
    stored = load_shared_upstream(db_path, CASE["id"], pipeline.llm_client.default_model)
    assert stored is not None
    (findings, step1), (diagnosis, step2) = stored
    assert diagnosis["primary_diagnosis"] == "Myocardial infarction" and step2.latency_ms == 7.0
    assert step1.agent_name == "Research Agent" and step2.total_tokens == 15
    assert load_shared_upstream(db_path, "other_case", None) is None


def test_missing_gold_label_earns_no_credit():
    assert ClinicalEvaluationScorer().evaluate_diagnostic_match("Gout", [], "") == 0.0


def test_unparseable_verifier_is_missing_not_negative(tmp_path):
    case = {"id": "medqa_x", "question": "q", "options": {"A": "Gout", "B": "Lupus"}, "answer": "A", "answer_idx": "A"}
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([case]))
    db = BenchmarkDB(str(tmp_path / "b.db"))
    pipeline = ClinicalGovernancePipeline(StubClient(garbage={"Fact Verifier"}))
    for variant in ("baseline", "verifier"):
        db.log_run(ClinicalEvaluationScorer().score_run(pipeline.run(dict(case), variant), case))
    runs = RigorousAnalysis(str(tmp_path / "b.db"), str(cases_path), reference_db_path=None).runs
    assert runs.loc[runs["variant_id"] == "V2", "hallucination_flag"].isna().all()


def test_llm_latency_excludes_rate_limit_backoff(monkeypatch):
    clock = SimpleNamespace(t=0.0)
    monkeypatch.setattr(client_mod.time, "perf_counter", lambda: clock.t)
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: setattr(clock, "t", clock.t + s))
    req = httpx.Request("POST", "https://example.invalid")
    replies = iter([httpx.Response(429, headers={"retry-after": "5"}, text="slow down", request=req),
                    httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}],
                                              "usage": {"prompt_tokens": 3, "completion_tokens": 2}}, request=req)])

    class FakeHTTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            clock.t += 0.25  # each request takes 250 ms
            return next(replies)

    monkeypatch.setattr(client_mod.httpx, "Client", FakeHTTP)
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("NVIDIA_API_KEYS", raising=False)
    llm = UnifiedLLMClient(provider="nvidia", allow_mock_fallback=False)
    resp = llm.generate([{"role": "user", "content": "hi"}])
    assert resp.latency_ms == 250.0  # the 5 s back-off and the failed attempt are not model latency


def test_unknown_api_path_is_404_not_the_spa():
    from fastapi.testclient import TestClient

    from src.api.server import FRONTEND_DIR, app

    if not FRONTEND_DIR.exists():  # the catch-all route only exists when the client is built
        return
    assert TestClient(app).get("/api/does-not-exist").status_code == 404


def test_unmappable_answers_agree_when_both_runs_share_them(tmp_path):
    case = {"id": "medqa_y", "question": "q", "options": {"A": "Gout", "B": "Lupus"}, "answer": "A", "answer_idx": "A"}
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([case]))
    db = BenchmarkDB(str(tmp_path / "c.db"))
    pipeline = ClinicalGovernancePipeline(StubClient(garbage={"Fact Verifier"}))
    shared = ({"chief_complaint": "x"}, AgentStepLog("Research Agent", "r"))
    unmappable = ({"primary_diagnosis": "COPD"}, AgentStepLog("Diagnosis Agent", "d"))  # matches no option
    for variant, closed in (("baseline", False), ("verifier", True)):
        result = pipeline.run(dict(case), variant, cached_research=shared, cached_diagnosis=unmappable, closed_loop=closed)
        db.log_run(ClinicalEvaluationScorer().score_run(result, case))
    analysis = RigorousAnalysis(str(tmp_path / "c.db"), str(cases_path), reference_db_path=None)
    (row,) = analysis.resampling_stability()
    assert row["answer_agreement"] == 1.0


def test_every_number_in_both_manuscripts_is_backed_by_a_report():
    from pathlib import Path

    from scripts.check_paper_numbers import main as check_numbers

    for tex in ("paper/main.tex", "paper/main_ncrtht2026.tex"):
        if Path(tex).exists():
            assert check_numbers(["--tex", tex]) == 0, f"{tex} has numbers not found in the reports"


def test_model_calls_and_governance_latency_per_run(tmp_path):
    case = {"id": "medqa_z", "question": "q", "options": {"A": "Gout", "B": "Lupus"}, "answer": "A", "answer_idx": "A"}
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([case]))
    db = BenchmarkDB(str(tmp_path / "d.db"))
    pipeline = ClinicalGovernancePipeline(StubClient())
    for variant in ("baseline", "verifier", "full_governance"):
        db.log_run(ClinicalEvaluationScorer().score_run(pipeline.run(dict(case), variant, include_report=False), case))
    runs = RigorousAnalysis(str(tmp_path / "d.db"), str(cases_path), reference_db_path=None).runs.set_index("variant_id")
    # Hand count: G0 = research + diagnosis; G1 adds the verifier; G4 adds consistency, verifier, safety, attending.
    assert runs.loc["V1", "model_calls"] == 2 and runs.loc["V2", "model_calls"] == 3 and runs.loc["V5", "model_calls"] == 6
    # Every stub call takes 7 ms, so governance latency = 7 ms x non-shared calls.
    assert runs.loc["V1", "governance_latency_s"] == 0.0
    assert abs(runs.loc["V5", "governance_latency_s"] - 4 * 0.007) < 1e-9
