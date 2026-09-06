"""Pluggable Pipeline Orchestrator executing the 5 Governance Variants."""

from __future__ import annotations

import time
import json
from typing import Any, Dict, List, Optional

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
from src.telemetry.metrics import PipelineRunResult, AgentStepLog


class ClinicalGovernancePipeline:
    """Orchestrates multi-agent execution across the 5 governance ablation variants."""

    AVAILABLE_VARIANTS = {
        "baseline": {
            "id": "V1",
            "name": "Baseline (Ungoverned)",
            "layers": ["Research", "Diagnosis", "Report"],
        },
        "verifier": {
            "id": "V2",
            "name": "Verifier Governance",
            "layers": ["Research", "Diagnosis", "Verifier", "Report"],
        },
        "hitl": {
            "id": "V3",
            "name": "HITL Simulator Governance",
            "layers": ["Research", "Diagnosis", "HITL Simulator", "Report"],
        },
        "safety": {
            "id": "V4",
            "name": "Safety Validator Governance",
            "layers": ["Research", "Diagnosis", "Safety Validator", "Report"],
        },
        "full_governance": {
            "id": "V5",
            "name": "Full Governance (Defense-in-Depth)",
            "layers": [
                "Research",
                "Diagnosis",
                "Verifier",
                "Safety Validator",
                "HITL Simulator",
                "Report",
            ],
        },
    }


    def __init__(self, llm_client: UnifiedLLMClient):
        self.llm_client = llm_client

        # Initialize the specialized agents
        self.research_agent = ResearchAgent(llm_client)
        self.diagnosis_agent = DiagnosisAgent(llm_client)
        self.report_agent = ReportAgent(llm_client)

        # Initialize governance modules
        self.verifier_agent = VerifierAgent(llm_client)
        self.safety_validator = SafetyValidatorAgent(llm_client)
        self.hitl_simulator = HITLSimulatorAgent(llm_client)
        self.consistency_checker = ConsistencyCheckerAgent(llm_client)

    def run(
        self,
        clinical_case: Dict[str, Any],
        variant_key: str = "baseline",
        cached_research: Optional[Tuple[Dict[str, Any], AgentStepLog]] = None,
        cached_diagnosis: Optional[Tuple[Dict[str, Any], AgentStepLog]] = None,
    ) -> PipelineRunResult:
        """Runs a clinical case through the designated governance variant."""
        variant_key = variant_key.lower().replace("-", "_")
        if variant_key not in self.AVAILABLE_VARIANTS:
            raise ValueError(
                f"Unknown variant '{variant_key}'. Must be one of: {list(self.AVAILABLE_VARIANTS.keys())}"
            )

        v_info = self.AVAILABLE_VARIANTS[variant_key]
        case_id = str(clinical_case.get("id", clinical_case.get("case_id", "unknown_case")))
        start_time = time.time()

        agent_steps: List[AgentStepLog] = []
        raw_outputs: Dict[str, Any] = {}
        all_flags: List[str] = []

        # --- STEP 1: Research Agent (Universal across all variants, cached if available) ---
        if cached_research:
            findings, step1 = cached_research
        else:
            findings, step1 = self.research_agent.execute(clinical_case)
        agent_steps.append(step1)
        raw_outputs["research"] = findings

        # --- STEP 2: Diagnosis Agent (Universal across all variants, cached if available) ---
        if cached_diagnosis:
            diagnosis_output, step2 = cached_diagnosis
        else:
            options = clinical_case.get("options")
            diagnosis_output, step2 = self.diagnosis_agent.execute(findings, case_options=options)
        agent_steps.append(step2)
        raw_outputs["diagnosis"] = diagnosis_output

        # Governance intermediates
        verifier_output = None
        safety_output = None
        hitl_output = None
        governance_notes = {}

        # --- GOVERNANCE LAYERS BY VARIANT ---

        # Variant 2 (Verifier) or Variant 5 (Full)
        if variant_key in ("verifier", "full_governance"):
            verifier_output, step_v = self.verifier_agent.execute(clinical_case, diagnosis_output)
            agent_steps.append(step_v)
            raw_outputs["verifier"] = verifier_output
            governance_notes["verifier"] = verifier_output
            all_flags.extend(step_v.flags)

        # Variant 4 (Safety) or Variant 5 (Full)
        if variant_key in ("safety", "full_governance"):
            safety_output, step_s = self.safety_validator.execute(clinical_case, diagnosis_output)
            agent_steps.append(step_s)
            raw_outputs["safety"] = safety_output
            governance_notes["safety"] = safety_output
            all_flags.extend(step_s.flags)

        # Variant 3 (HITL) or Variant 5 (Full)
        if variant_key in ("hitl", "full_governance"):
            hitl_output, step_h = self.hitl_simulator.execute(
                clinical_case,
                diagnosis_output,
                safety_output=safety_output,
            )
            agent_steps.append(step_h)
            raw_outputs["hitl"] = hitl_output
            governance_notes["hitl"] = hitl_output
            all_flags.extend(step_h.flags)

        # --- FINAL STEP: Report Agent (Synthesizes clinical note + governance inputs) ---
        report_output, step_rep = self.report_agent.execute(
            findings,
            diagnosis_output,
            governance_notes=governance_notes,
        )
        agent_steps.append(step_rep)
        raw_outputs["report"] = report_output

        # Calculate totals
        total_latency_ms = round((time.time() - start_time) * 1000, 2)
        total_prompt = sum(s.prompt_tokens for s in agent_steps)
        total_comp = sum(s.completion_tokens for s in agent_steps)
        total_tokens = total_prompt + total_comp
        total_cost = sum(s.cost_usd for s in agent_steps)

        primary_dx = diagnosis_output.get("primary_diagnosis", "")
        diff_list = diagnosis_output.get("differential_diagnoses", [])

        # Count flags
        hallucinations = 1 if (verifier_output and verifier_output.get("hallucination_detected")) else 0
        safety_violations = len(safety_output.get("safety_flags", [])) if safety_output else 0
        hitl_decision = hitl_output.get("decision", "APPROVED") if hitl_output else "N/A"

        return PipelineRunResult(
            case_id=case_id,
            variant_id=v_info["id"],
            variant_name=v_info["name"],
            model=self.llm_client.default_model,
            provider=self.llm_client.provider,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_comp,
            total_tokens=total_tokens,
            total_latency_ms=total_latency_ms,
            total_cost_usd=round(total_cost, 6),
            primary_diagnosis=primary_dx,
            differential_diagnoses=diff_list,
            clinical_report=json.dumps(report_output, indent=2),
            hallucinations_detected=hallucinations,
            safety_violations_detected=safety_violations,
            hitl_decision=hitl_decision,
            governance_flags=all_flags,
            agent_steps=agent_steps,
            raw_outputs=raw_outputs,
        )
