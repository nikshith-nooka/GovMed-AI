"""Pluggable Pipeline Orchestrator executing the 5 Governance Variants."""

from __future__ import annotations

import time
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.agents.base import is_parse_failure
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
                "Consistency Checker",
                "Verifier",
                "Safety Validator",
                "HITL Simulator",
                "Report",
            ],
        },
    }


    BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}

    @classmethod
    def revision_triggers(
        cls,
        consistency: Optional[Dict[str, Any]],
        verifier: Optional[Dict[str, Any]],
        safety: Optional[Dict[str, Any]],
        hitl: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Governance signals serious enough to justify revising the diagnosis."""
        triggers: List[str] = []
        if consistency and consistency.get("consistency_status") == "SEVERE_CONTRADICTION":
            for item in consistency.get("inconsistencies_found", []) or ["severe contradiction"]:
                triggers.append(f"Consistency checker: {item}")
        if verifier and (
            verifier.get("hallucination_detected")
            or verifier.get("verification_status") == "CRITICAL_HALLUCINATION"
        ):
            claims = verifier.get("flagged_claims", []) or [{"claim": "unspecified", "issue": "ungrounded claim"}]
            for claim in claims:
                if isinstance(claim, dict):
                    triggers.append(f"Verifier: '{claim.get('claim', '')}' - {claim.get('issue', '')}")
        if safety:
            for flag in safety.get("safety_flags", []) or []:
                if isinstance(flag, dict) and str(flag.get("severity", "")).upper() in cls.BLOCKING_SEVERITIES:
                    triggers.append(f"Safety validator [{flag.get('severity')}]: {flag.get('description', '')}")
        if hitl and str(hitl.get("decision", "")).upper() in {"REQUEST_REVISION", "REJECTED"}:
            triggers.append(f"Attending review ({hitl.get('decision')}): {hitl.get('critique', '')}")
            for amendment in hitl.get("required_amendments", []) or []:
                triggers.append(f"Required amendment: {amendment}")
        return triggers

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
        closed_loop: bool = False,
        include_report: bool = True,
        on_step: Optional[Callable[[str, str, Optional[AgentStepLog]], None]] = None,
    ) -> PipelineRunResult:
        """Runs a clinical case through the designated governance variant.

        closed_loop=True feeds governance concerns back to the Diagnosis Agent for one
        revision round; otherwise governance is advisory and never changes the diagnosis.
        """
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

        notify = on_step or (lambda *args: None)

        def timed(name: str, fn, *args):
            notify("start", name, None)
            output, step = fn(*args)
            notify("done", name, step)
            return output, step

        # --- STEP 1: Research Agent (Universal across all variants, cached if available) ---
        if cached_research:
            findings, step1 = cached_research
        else:
            findings, step1 = timed("Research Agent", self.research_agent.execute, clinical_case)
        agent_steps.append(step1)
        raw_outputs["research"] = findings

        # --- STEP 2: Diagnosis Agent (Universal across all variants, cached if available) ---
        if cached_diagnosis:
            diagnosis_output, step2 = cached_diagnosis
        else:
            options = clinical_case.get("options")
            diagnosis_output, step2 = timed("Diagnosis Agent", self.diagnosis_agent.execute, findings, options)
        agent_steps.append(step2)
        raw_outputs["diagnosis"] = diagnosis_output

        # Consistency, verifier and safety only read the case and diagnosis, so run them concurrently.
        parallel_checks = []
        if variant_key == "full_governance":
            parallel_checks.append(("consistency", "Consistency Checker", self.consistency_checker.execute, (findings, diagnosis_output)))
        if variant_key in ("verifier", "full_governance"):
            parallel_checks.append(("verifier", "Verifier Agent", self.verifier_agent.execute, (clinical_case, diagnosis_output)))
        if variant_key in ("safety", "full_governance"):
            parallel_checks.append(("safety", "Safety Validator", self.safety_validator.execute, (clinical_case, diagnosis_output)))
        check_results: Dict[str, Tuple[Dict[str, Any], AgentStepLog]] = {}
        if parallel_checks:
            with ThreadPoolExecutor(max_workers=len(parallel_checks)) as pool:
                futures = {key: pool.submit(timed, name, fn, *args) for key, name, fn, args in parallel_checks}
                check_results = {key: future.result() for key, future in futures.items()}

        # Governance intermediates
        consistency_output = None
        verifier_output = None
        safety_output = None
        hitl_output = None
        governance_notes = {}

        # --- GOVERNANCE LAYERS BY VARIANT ---

        # Variant 5 (Full): Consistency Checker audits logical alignment between
        # findings and the diagnosis BEFORE the adversarial verifier runs.
        if "consistency" in check_results:
            consistency_output, step_c = check_results["consistency"]
            agent_steps.append(step_c)
            raw_outputs["consistency"] = consistency_output
            governance_notes["consistency"] = consistency_output
            # Track the consistency audit outcome as a governance flag.
            if consistency_output:
                c_status = consistency_output.get("consistency_status", "CONSISTENT")
                c_score = consistency_output.get("consistency_score", 1.0)
                if consistency_output.get("inconsistencies_found"):
                    severity = "SEVERE_CONTRADICTION" if c_status == "SEVERE_CONTRADICTION" else "MINOR_INCONSISTENCY"
                    all_flags.append(f"Consistency Flag: {severity} ({len(consistency_output.get('inconsistencies_found', []))} issue(s), score {c_score})")
                else:
                    all_flags.append(f"Consistency Check Passed ({c_status}, score {c_score})")
            all_flags.extend(step_c.flags)

        # Variant 2 (Verifier) or Variant 5 (Full)
        if "verifier" in check_results:
            verifier_output, step_v = check_results["verifier"]
            agent_steps.append(step_v)
            raw_outputs["verifier"] = verifier_output
            governance_notes["verifier"] = verifier_output
            all_flags.extend(step_v.flags)

        # Variant 4 (Safety) or Variant 5 (Full)
        if "safety" in check_results:
            safety_output, step_s = check_results["safety"]
            agent_steps.append(step_s)
            raw_outputs["safety"] = safety_output
            governance_notes["safety"] = safety_output
            all_flags.extend(step_s.flags)

        # Variant 3 (HITL) or Variant 5 (Full)
        if variant_key in ("hitl", "full_governance"):
            hitl_output, step_h = timed("HITL Simulator", self.hitl_simulator.execute,
                                        clinical_case, diagnosis_output, safety_output)
            agent_steps.append(step_h)
            raw_outputs["hitl"] = hitl_output
            governance_notes["hitl"] = hitl_output
            all_flags.extend(step_h.flags)

        initial_primary = str(diagnosis_output.get("primary_diagnosis", "") or "")
        revision_triggers: List[str] = []
        revision_applied = False
        is_closed_loop = closed_loop and variant_key != "baseline"
        if is_closed_loop:
            revision_triggers = self.revision_triggers(consistency_output, verifier_output, safety_output, hitl_output)
            if revision_triggers:
                revised, step_rev = timed("Diagnosis Agent (Revision)", self.diagnosis_agent.revise,
                                          findings, diagnosis_output, revision_triggers, clinical_case.get("options"))
                agent_steps.append(step_rev)
                raw_outputs["diagnosis_initial"] = diagnosis_output
                raw_outputs["revision"] = {"triggers": revision_triggers, "output": revised}
                if not is_parse_failure(revised) and revised.get("primary_diagnosis"):
                    diagnosis_output = revised
                    raw_outputs["diagnosis"] = revised
                    revision_applied = True
                    all_flags.append(f"Closed-loop revision: {initial_primary} -> {revised.get('primary_diagnosis')}")

        # --- FINAL STEP: Report Agent (Synthesizes clinical note + governance inputs) ---
        report_output: Dict[str, Any] = {}
        if include_report:
            report_output, step_rep = timed("Report Agent", self.report_agent.execute,
                                            findings, diagnosis_output, governance_notes)
            agent_steps.append(step_rep)
            raw_outputs["report"] = report_output

        # Calculate totals
        total_latency_ms = round((time.time() - start_time) * 1000, 2)
        total_prompt = sum(s.prompt_tokens for s in agent_steps)
        total_comp = sum(s.completion_tokens for s in agent_steps)
        total_tokens = total_prompt + total_comp
        total_cost = sum(s.cost_usd for s in agent_steps)

        # Sum HITL review time across variants that include it
        total_hitl_minutes = hitl_output.get("simulated_physician_minutes", 0.0) if hitl_output else 0.0

        primary_dx = diagnosis_output.get("primary_diagnosis", "")
        diff_list = diagnosis_output.get("differential_diagnoses", [])

        # Count flags
        hallucinations = 1 if (verifier_output and verifier_output.get("hallucination_detected")) else 0
        safety_violations = len(safety_output.get("safety_flags", [])) if safety_output else 0
        hitl_decision = hitl_output.get("decision", "APPROVED") if hitl_output else "N/A"

        parse_failures = [name for name, output in raw_outputs.items() if is_parse_failure(output)]
        if revision_triggers and not revision_applied:
            parse_failures.append("revision")

        return PipelineRunResult(
            case_id=case_id,
            variant_id=v_info["id"] + ("-CL" if is_closed_loop else ""),
            variant_name=v_info["name"] + (" + Closed-Loop Revision" if is_closed_loop else ""),
            closed_loop=is_closed_loop,
            revision_applied=revision_applied,
            initial_primary_diagnosis=initial_primary,
            revision_triggers=revision_triggers,
            parse_failures=parse_failures,
            model=self.llm_client.default_model,
            provider=self.llm_client.provider,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_comp,
            total_tokens=total_tokens,
            total_latency_ms=total_latency_ms,
            total_cost_usd=round(total_cost, 6),
            simulated_physician_minutes=round(total_hitl_minutes, 2),
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
