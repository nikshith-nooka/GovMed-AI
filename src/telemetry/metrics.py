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

    # Detailed agent traces
    agent_steps: List[AgentStepLog] = field(default_factory=list)
    raw_outputs: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
