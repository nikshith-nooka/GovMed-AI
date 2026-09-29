"""Unit tests for evaluation scoring, database logging, and statistics."""

import os
import pandas as pd
import pytest
from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.evaluation.scorer import ClinicalEvaluationScorer
from src.evaluation.statistics import BenchmarkStatistics
from src.evaluation.llm_judge import LLMJudgeAgent
from src.telemetry.db import BenchmarkDB


def test_scorer_and_db(tmp_path):
    db_file = str(tmp_path / "test_benchmark.db")
    db = BenchmarkDB(db_path=db_file)
    scorer = ClinicalEvaluationScorer()
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    pipeline = ClinicalGovernancePipeline(client)

    case = {
        "id": "case_101",
        "question": "Acute retrosternal chest pain and diaphoresis.",
        "gold_diagnosis": "Acute Coronary Syndrome",
        "answer": "A",
        "options": {"A": "Acute Coronary Syndrome", "B": "Asthma"},
    }

    run_res = pipeline.run(case, variant_key="baseline")
    scored = scorer.score_run(run_res, case)

    assert scored.diagnostic_accuracy_score >= 0.8
    assert scored.overall_quality_score > 0.0

    # Test database persistence
    run_id = db.log_run(scored)
    assert run_id > 0

    df = db.get_runs_df()
    assert len(df) == 1
    assert df.iloc[0]["case_id"] == "case_101"

    # JRU & GEF columns exist on the schema and are populated (non-null) after
    # a real mock pipeline run.
    for col in ("uncertainty_jru", "governance_efficiency_factor", "risk_adjusted_quality"):
        assert col in df.columns, f"missing telemetry column: {col}"
        assert not pd.isna(df.iloc[0][col]), f"{col} should be populated (non-null)"
    assert 0.0 <= df.iloc[0]["uncertainty_jru"] <= 1.0
    assert df.iloc[0]["governance_efficiency_factor"] >= 0.0

    summary = db.get_variant_summary()
    assert len(summary) == 1
    assert summary.iloc[0]["variant_id"] == "V1"



def test_llm_judge_scoring_and_persistence(tmp_path):
    """Judge output is blended into quality and saved with the run telemetry."""
    db = BenchmarkDB(db_path=str(tmp_path / "judge_benchmark.db"))
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    pipeline = ClinicalGovernancePipeline(client)
    scorer = ClinicalEvaluationScorer()
    judge = LLMJudgeAgent(client)
    case = {
        "id": "judge_case",
        "question": "A patient has acute chest pain and diaphoresis.",
        "gold_diagnosis": "Acute Coronary Syndrome",
        "options": {"A": "Acute Coronary Syndrome"},
        "answer": "A",
    }

    result = pipeline.run(case)
    judge_scores, judge_step = judge.execute(result.raw_outputs, case)
    result.agent_steps.append(judge_step)
    result.raw_outputs["llm_judge"] = judge_scores
    scored = scorer.score_run(result, case, judge_scores=judge_scores)

    assert scored.llm_judge_scores["overall_judge_score"] == judge_scores["overall_judge_score"]
    assert 0.0 <= scored.report_quality_score <= 1.0
    db.log_run(scored)
    saved = db.get_runs_df().iloc[0]
    assert saved["llm_judge_score"] == pytest.approx(judge_scores["overall_judge_score"])
    assert saved["report_quality_score"] == pytest.approx(scored.report_quality_score)


def test_jru_gef_schema_and_migration(tmp_path):
    """JRU (uncertainty) and GEF (governance efficiency factor) are tracked,
    persisted, and backfilled gracefully onto legacy database schemas.
    """
    db_file = str(tmp_path / "legacy.db")
    # Simulate a legacy schema without JRU/GEF columns
    import sqlite3
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                variant_name TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL,
                total_prompt_tokens INTEGER,
                total_completion_tokens INTEGER,
                total_tokens INTEGER,
                total_latency_ms REAL,
                total_cost_usd REAL,
                primary_diagnosis TEXT,
                diagnostic_accuracy_score REAL,
                differential_completeness_score REAL,
                evidence_grounding_score REAL,
                safety_score REAL,
                overall_quality_score REAL,
                hallucinations_detected INTEGER,
                safety_violations_detected INTEGER,
                hitl_decision TEXT,
                governance_flags TEXT,
                raw_outputs_json TEXT,
                timestamp REAL
            )
            """
        )
        conn.commit()

    # Initializing BenchmarkDB on the legacy file applies idempotent schema migrations
    db = BenchmarkDB(db_path=db_file)
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    pipeline = ClinicalGovernancePipeline(client)
    scorer = ClinicalEvaluationScorer()

    case = {
        "id": "jru_gef_case",
        "question": "Acute chest pain, elevated troponin, ST elevation.",
        "gold_diagnosis": "Acute Myocardial Infarction",
        "options": {"A": "Acute Myocardial Infarction"},
        "answer": "A",
    }
    result = pipeline.run(case, variant_key="full_governance")
    scored = scorer.score_run(result, case)

    # Scored object must compute both JRU and GEF
    assert hasattr(scored, "uncertainty_jru")
    assert 0.0 <= scored.uncertainty_jru <= 1.0
    assert hasattr(scored, "governance_efficiency_factor")
    assert scored.governance_efficiency_factor >= 0.0
    assert hasattr(scored, "risk_adjusted_quality")
    assert 0.0 <= scored.risk_adjusted_quality <= 1.0

    # Insert into the migrated database must succeed without errors
    run_id = db.log_run(scored)
    assert run_id > 0

    df = db.get_runs_df()
    saved = df.iloc[0]
    assert saved["case_id"] == "jru_gef_case"
    assert saved["uncertainty_jru"] == pytest.approx(scored.uncertainty_jru)
    assert saved["governance_efficiency_factor"] == pytest.approx(scored.governance_efficiency_factor)
    assert saved["risk_adjusted_quality"] == pytest.approx(scored.risk_adjusted_quality)

    # Summary table must aggregate JRU and GEF
    summary = db.get_variant_summary()
    assert "avg_uncertainty_jru" in summary.columns
    assert "avg_governance_efficiency_factor" in summary.columns
    assert not pd.isna(summary.iloc[0]["avg_governance_efficiency_factor"])


def test_statistics_ci():
    import pandas as pd
    series = pd.Series([0.80, 0.85, 0.82, 0.88, 0.84])
    mean, lower, upper = BenchmarkStatistics.compute_ci_95(series)
    assert 0.80 <= mean <= 0.88
    assert lower < mean < upper


def test_governance_efficiency_frontier(tmp_path):
    from src.analysis.frontier import GovernanceEfficiencyFrontier
    db_file = str(tmp_path / "frontier_test.db")
    db = BenchmarkDB(db_path=db_file)
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    pipeline = ClinicalGovernancePipeline(client)
    scorer = ClinicalEvaluationScorer()

    case = {
        "id": "c1",
        "question": "A 50-year-old male with sudden severe chest pain.",
        "gold_diagnosis": "Acute Coronary Syndrome",
        "options": {"A": "Acute Coronary Syndrome"},
        "answer": "A",
    }
    # Run across baseline and full_governance
    r1 = pipeline.run(case, variant_key="baseline")
    scored1 = scorer.score_run(r1, case)
    db.log_run(scored1)

    r2 = pipeline.run(case, variant_key="full_governance")
    scored2 = scorer.score_run(r2, case)
    db.log_run(scored2)

    analyzer = GovernanceEfficiencyFrontier(db_file)
    frontier_df = analyzer.compute_frontier()
    assert len(frontier_df) == 2
    assert "is_pareto_frontier" in frontier_df.columns
    assert "risk_adjusted_quality" in frontier_df.columns
    assert "governance_efficiency_factor" in frontier_df.columns

    # Test export artifacts
    csv_file, tex_file = analyzer.export_frontier_artifacts(str(tmp_path / "tables"))
    assert csv_file.exists()
    assert tex_file.exists()
