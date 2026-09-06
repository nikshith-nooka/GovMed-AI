"""Unit tests for the 5 governance pipeline variants."""

import pytest
from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline


@pytest.fixture
def pipeline():
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    return ClinicalGovernancePipeline(client)


@pytest.fixture
def sample_case():
    return {
        "id": "medqa_test",
        "question": "A 45-year-old female presents with acute pleuritic chest pain and dyspnea after a long flight.",
        "options": {"A": "Pulmonary Embolism", "B": "Anxiety"},
        "gold_diagnosis": "Pulmonary Embolism",
    }


@pytest.mark.parametrize(
    "variant_key,expected_variant_id",
    [
        ("baseline", "V1"),
        ("verifier", "V2"),
        ("hitl", "V3"),
        ("safety", "V4"),
        ("full_governance", "V5"),
    ],
)
def test_pipeline_variant_execution(pipeline, sample_case, variant_key, expected_variant_id):
    result = pipeline.run(sample_case, variant_key=variant_key)
    assert result.variant_id == expected_variant_id
    assert result.total_tokens > 0
    assert result.total_latency_ms >= 0
    assert len(result.agent_steps) >= 3
    assert result.primary_diagnosis != ""
