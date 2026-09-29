"""Data models for benchmark telemetry, run metrics, and governance overhead."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class AgentStepLog:
    agent_name: str
    role: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    output_preview: str = ""
    flags: List[str] = field(default_factory=list)


@dataclass
class PipelineRunResult:
    case_id: str
    variant_id: str
    variant_name: str
    model: str
    provider: str

    # Cumulative Costs & Latency
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    simulated_physician_minutes: float = 0.0

    # Diagnostic & Governance Outcomes
    primary_diagnosis: str = ""
    differential_diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    clinical_report: str = ""

    # Quality & Safety Scores
    diagnostic_accuracy_score: float = 0.0
    differential_completeness_score: float = 0.0
    evidence_grounding_score: float = 1.0
    safety_score: float = 1.0
    overall_quality_score: float = 0.0

    # Governance Flags & Interventions
    hallucinations_detected: int = 0
    safety_violations_detected: int = 0
    hitl_decision: str = "N/A"
    governance_flags: List[str] = field(default_factory=list)

    # Rubric-based quality (pre-blend composite)
    rubric_quality_score: float = 0.0

    # LLM Judge Scores
    llm_judge_score: float = 0.0
    llm_judge_scores: Dict[str, Any] = field(default_factory=dict)
    report_quality_score: float = 0.0

    # Uncertainty & Risk-Adjusted Quality
    uncertainty_jru: float = 0.0
    risk_adjusted_quality: float = 0.0

    # Governance Efficiency Factor (GEF): quality delivered per unit of
    # compute/token spend — higher is more governance-efficient.
    governance_efficiency_factor: float = 0.0

    # HITL Economics
    hitl_minutes: float = 0.0
    hitl_human_cost: float = 0.0

    # Measurement-validity fields
    detector_neutral_quality: float = 0.0
    gold_label_valid: bool = True
    jru_source: str = "grounding_proxy"
    parse_failures: List[str] = field(default_factory=list)

    # Closed-loop governance: did a governance signal cause the diagnosis to be revised?
    closed_loop: bool = False
    revision_applied: bool = False
    initial_primary_diagnosis: str = ""
    revision_triggers: List[str] = field(default_factory=list)

    # Detailed agent traces
    agent_steps: List[AgentStepLog] = field(default_factory=list)
    raw_outputs: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
