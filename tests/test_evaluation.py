"""Unit tests for evaluation scoring, database logging, and statistics."""

import os
import pytest
from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.evaluation.scorer import ClinicalEvaluationScorer
from src.evaluation.statistics import BenchmarkStatistics
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

    summary = db.get_variant_summary()
    assert len(summary) == 1
    assert summary.iloc[0]["variant_id"] == "V1"


def test_statistics_ci():
    import pandas as pd
    series = pd.Series([0.80, 0.85, 0.82, 0.88, 0.84])
    mean, lower, upper = BenchmarkStatistics.compute_ci_95(series)
    assert 0.80 <= mean <= 0.88
    assert lower < mean < upper
