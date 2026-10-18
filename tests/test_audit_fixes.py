"""Regression tests for the 2026-10-10 audit fixes (docs/audit/REPAIR_LOG.md)."""

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


def test_experiment_registry_lists_known_reports_and_rejects_anything_else():
    from fastapi.testclient import TestClient

    from src.api.server import app

    client = TestClient(app)
    listing = client.get("/api/research/experiments").json()
    keys = {e["key"] for e in listing["experiments"]}
    assert {"open150", "medqa_paired", "medqa_unpaired"} <= keys and listing["default"] == "open150"
    for bad in ("../../etc/passwd", "rigor_report", "MEDQA_PAIRED"):
        assert client.get("/api/research/findings", params={"experiment": bad}).status_code == 400
        assert client.get("/api/reports/latex", params={"experiment": bad}).status_code == 400


def test_each_experiment_serves_its_own_report():
    from fastapi.testclient import TestClient

    from src.api.server import EXPERIMENTS, app, report_path

    client = TestClient(app)
    for key in EXPERIMENTS:
        path = report_path(key)
        if not path.exists():
            continue
        expected = json.loads(path.read_text(encoding="utf-8"))
        served = client.get("/api/research/findings", params={"experiment": key}).json()
        assert served["n_runs_analyzed"] == expected["n_runs_analyzed"]
        assert [v["variant_id"] for v in served["variants"]] == [v["variant_id"] for v in expected["variants"]]
    # No parameter keeps the original behaviour (the 150-case report), so existing clients are unaffected.
    assert client.get("/api/research/findings").json()["n_runs_analyzed"] == json.loads(
        report_path("open150").read_text(encoding="utf-8"))["n_runs_analyzed"]


# ---------------------------------------------------------------- experiment-aware stats and CSV export
def _fixture_experiment(tmp_path, name, variants, cases=2):
    """A synthetic run database with known contents: `cases` x `variants`, stub model, no real data."""
    db_file = tmp_path / f"{name}.db"
    db = BenchmarkDB(str(db_file))
    pipeline = ClinicalGovernancePipeline(StubClient())
    for i in range(cases):
        case = {**CASE, "id": f"{name}_{i}"}
        for variant in variants:
            db.log_run(ClinicalEvaluationScorer().score_run(pipeline.run(dict(case), variant, include_report=False), case))
    return db_file


def _csv_rows(text):
    import csv
    import io

    return list(csv.DictReader(io.StringIO(text)))


def test_stats_and_csv_follow_the_selected_experiment(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import src.api.server as server

    small = _fixture_experiment(tmp_path, "small", ["baseline"], cases=2)
    large = _fixture_experiment(tmp_path, "large", ["baseline", "verifier", "full_governance"], cases=3)
    registry = {
        "open150": {**server.EXPERIMENTS["open150"], "db": small, "report": tmp_path / "none.json"},
        "fixture_large": {"label": "fixture", "status": "test", "db": large, "report": tmp_path / "none.json",
                          "tables": tmp_path},
    }
    monkeypatch.setattr(server, "EXPERIMENTS", registry)
    client = TestClient(server.app)

    s_small = client.get("/api/stats", params={"experiment": "open150"}).json()
    s_large = client.get("/api/stats", params={"experiment": "fixture_large"}).json()
    assert (s_small["experiment"], s_small["total_runs"], s_small["total_cases"]) == ("open150", 2, 2)
    assert (s_large["experiment"], s_large["total_runs"], s_large["total_cases"]) == ("fixture_large", 9, 3)
    assert {v["variant_id"] for v in s_large["variant_breakdown"]} == {"V1", "V2", "V5"}
    # No report for this fixture, so accuracy says it came from the stored scores, not from another experiment.
    assert s_large["accuracy_source"] == "stored scores"

    rows = _csv_rows(client.get("/api/reports/csv", params={"experiment": "fixture_large"}).text)
    assert len(rows) == 9 and {r["variant_id"] for r in rows} == {"V1", "V2", "V5"}
    assert {r["case_id"] for r in rows} == {"large_0", "large_1", "large_2"}
    assert not set(server.SYNTHETIC_COLUMNS) & set(rows[0])          # unmeasured columns stay out of exports
    disposition = client.get("/api/reports/csv", params={"experiment": "fixture_large"}).headers["content-disposition"]
    assert "govbench_runs_fixture_large.csv" in disposition


def test_stats_and_csv_reject_unknown_experiments():
    from fastapi.testclient import TestClient

    from src.api.server import app

    client = TestClient(app)
    for bad in ("../../etc/passwd", "results/benchmark_results.db", "OPEN150", "x" * 300):
        assert client.get("/api/stats", params={"experiment": bad}).status_code == 400
        assert client.get("/api/reports/csv", params={"experiment": bad}).status_code == 400


def test_superseded_runs_are_exported_but_not_counted(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import src.api.server as server

    db_file = _fixture_experiment(tmp_path, "rerun", ["baseline"], cases=2)
    db = BenchmarkDB(str(db_file))
    rerun = {**CASE, "id": "rerun_0"}
    db.log_run(ClinicalEvaluationScorer().score_run(
        ClinicalGovernancePipeline(StubClient()).run(dict(rerun), "baseline", include_report=False), rerun))
    monkeypatch.setattr(server, "DB_PATH", db_file)
    client = TestClient(server.app)
    stats = client.get("/api/stats").json()
    assert (stats["stored_runs"], stats["total_runs"], stats["superseded_runs"], stats["total_cases"]) == (3, 2, 1, 2)
    rows = _csv_rows(client.get("/api/reports/csv").text)
    assert len(rows) == 3 and sorted(r["superseded"] for r in rows) == ["0", "0", "1"]
    old = next(r for r in rows if r["superseded"] == "1")
    assert old["case_id"] == "rerun_0" and int(old["id"]) == min(int(r["id"]) for r in rows if r["case_id"] == "rerun_0")


def test_default_stats_and_csv_are_unchanged(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import src.api.server as server

    default_db = _fixture_experiment(tmp_path, "default", ["baseline", "verifier"], cases=2)
    monkeypatch.setattr(server, "DB_PATH", default_db)          # what the server used before experiments existed
    client = TestClient(server.app)
    plain = client.get("/api/stats").json()
    explicit = client.get("/api/stats", params={"experiment": "open150"}).json()
    assert plain["total_runs"] == explicit["total_runs"] == 4 and plain["experiment"] == "open150"
    response = client.get("/api/reports/csv")
    assert "filename=govbench_benchmark_runs.csv" in response.headers["content-disposition"]   # old filename kept
    assert len(_csv_rows(response.text)) == 4


def test_empty_and_missing_experiments_are_safe(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import src.api.server as server

    empty = tmp_path / "empty.db"
    BenchmarkDB(str(empty))
    registry = {**server.EXPERIMENTS,
                "empty": {"label": "empty", "status": "test", "db": empty, "report": tmp_path / "none.json", "tables": tmp_path},
                "missing": {"label": "missing", "status": "test", "db": tmp_path / "nope.db",
                            "report": tmp_path / "none.json", "tables": tmp_path}}
    monkeypatch.setattr(server, "EXPERIMENTS", registry)
    client = TestClient(server.app)
    body = client.get("/api/stats", params={"experiment": "empty"}).json()
    assert body["has_data"] is False and body["total_runs"] == 0 and body["experiment"] == "empty"
    assert _csv_rows(client.get("/api/reports/csv", params={"experiment": "empty"}).text) == []
    for path in ("/api/stats", "/api/reports/csv"):
        r = client.get(path, params={"experiment": "missing"})
        assert r.status_code == 503 and "not found" in r.json()["detail"]
    listing = {e["key"]: e for e in client.get("/api/research/experiments").json()["experiments"]}
    assert listing["missing"]["runs_available"] is False and listing["empty"]["runs_available"] is True


def test_real_experiments_charts_and_exports_agree_with_source_records():
    """Read-only check on the stored experiments: every number the dashboard chart and the CSV show comes from the
    experiment's own database."""
    import sqlite3
    from pathlib import Path

    import pytest
    from fastapi.testclient import TestClient

    from src.api.server import EXPERIMENTS, app, db_path, report_path

    client = TestClient(app)
    checked = 0
    for key in EXPERIMENTS:
        if not (db_path(key).exists() and report_path(key).exists()):
            continue
        with sqlite3.connect(db_path(key)) as conn:
            counts = dict(conn.execute("SELECT variant_id, COUNT(*) FROM runs GROUP BY variant_id").fetchall())
            n_runs = sum(counts.values())
        stats = client.get("/api/stats", params={"experiment": key}).json()
        rows = _csv_rows(client.get("/api/reports/csv", params={"experiment": key}).text)
        assert len(rows) == n_runs == stats["stored_runs"]           # every raw record is exported
        current = [r for r in rows if r["superseded"] == "0"]
        assert stats["total_runs"] == len(current) and stats["superseded_runs"] == n_runs - len(current)
        # The chart draws report["variants"]: one bar group per variant, sized by its latest-run count, which must
        # equal the export's non-superseded rows, so chart and CSV describe the same population.
        report = client.get("/api/research/findings", params={"experiment": key}).json()
        latest = {v: sum(r["variant_id"] == v for r in current) for v in counts}
        assert {v["variant_id"]: v["n_runs"] for v in report["variants"]} == latest
        assert stats["total_runs"] == report["n_runs_analyzed"]
        checked += 1
    if not checked:
        pytest.skip("no stored experiment databases in this checkout")
    # The paired MedQA experiment is scored exactly against the answer key, so the chart's accuracy equals the
    # stored per-variant mean of the exact-match score.
    if Path(db_path("medqa_paired")).exists():
        with sqlite3.connect(db_path("medqa_paired")) as conn:
            stored = dict(conn.execute("SELECT variant_id, AVG(diagnostic_accuracy_score) FROM runs GROUP BY variant_id").fetchall())
        report = client.get("/api/research/findings", params={"experiment": "medqa_paired"}).json()
        for v in report["variants"]:
            assert abs(v["accuracy_valid_gold"] - stored[v["variant_id"]]) < 5e-5
