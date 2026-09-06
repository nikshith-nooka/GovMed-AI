"""Unit tests for the 7 specialized clinical agents and governance modules."""

import pytest
from src.llm.client import UnifiedLLMClient
from src.agents import (
    ResearchAgent,
    DiagnosisAgent,
    ReportAgent,
    VerifierAgent,
    SafetyValidatorAgent,
    HITLSimulatorAgent,
    ConsistencyCheckerAgent,
)


@pytest.fixture
def mock_client():
    return UnifiedLLMClient(provider="mock", force_mock=True)


@pytest.fixture
def sample_case():
    return {
        "id": "test_case_001",
        "question": "A 55-year-old male presents with acute crushing chest pain radiating to the left arm and jaw.",
        "options": {"A": "Myocardial Infarction", "B": "GERD"},
        "gold_diagnosis": "Myocardial Infarction",
    }


def test_research_agent(mock_client, sample_case):
    agent = ResearchAgent(mock_client)
    findings, step_log = agent.execute(sample_case)
    assert isinstance(findings, dict)
    assert step_log.agent_name == "Research Agent"
    assert step_log.total_tokens > 0


def test_diagnosis_agent(mock_client):
    agent = DiagnosisAgent(mock_client)
    findings = {"chief_complaint": "Chest pain", "pertinent_positives": ["Diaphoresis"]}
    dx_out, step_log = agent.execute(findings)
    assert "primary_diagnosis" in dx_out
    assert len(dx_out.get("differential_diagnoses", [])) > 0


def test_report_agent(mock_client):
    agent = ReportAgent(mock_client)
    findings = {"chief_complaint": "Chest pain"}
    dx_out = {"primary_diagnosis": "Acute Coronary Syndrome"}
    report, step_log = agent.execute(findings, dx_out)
    assert isinstance(report, dict)
    assert "assessment" in report


def test_verifier_agent(mock_client, sample_case):
    agent = VerifierAgent(mock_client)
    dx_out = {"primary_diagnosis": "Acute Coronary Syndrome"}
    res, step_log = agent.execute(sample_case, dx_out)
    assert "verification_status" in res


def test_safety_validator_agent(mock_client, sample_case):
    agent = SafetyValidatorAgent(mock_client)
    dx_out = {"primary_diagnosis": "Acute Coronary Syndrome"}
    res, step_log = agent.execute(sample_case, dx_out)
    assert "safety_status" in res


def test_hitl_simulator_agent(mock_client, sample_case):
    agent = HITLSimulatorAgent(mock_client)
    dx_out = {"primary_diagnosis": "Acute Coronary Syndrome"}
    res, step_log = agent.execute(sample_case, dx_out)
    assert "decision" in res
    assert "simulated_physician_minutes" in res


def test_consistency_checker_agent(mock_client):
    agent = ConsistencyCheckerAgent(mock_client)
    findings = {"chief_complaint": "Chest pain"}
    dx_out = {"primary_diagnosis": "Acute Coronary Syndrome"}
    res, step_log = agent.execute(findings, dx_out)
    assert "consistency_status" in res
