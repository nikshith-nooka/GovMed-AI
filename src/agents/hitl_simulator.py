"""HITL Simulator Agent: Simulates an attending physician review gate with risk-stratified decisions and time overhead."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

HITL_SYSTEM_PROMPT = """You are an experienced Attending Physician acting as a Human-in-the-Loop (HITL) Clinical Gatekeeper.
You are reviewing an AI-generated diagnostic plan before it is finalized into the patient's record.
Your evaluation must simulate authentic human clinical skepticism and workflow bottlenecks.

Determine:
1. Decision: APPROVED | REQUEST_REVISION | REJECTED
2. Simulated clinician attention time (in minutes, typically 1.5 to 5.0 mins).
3. Critical feedback or required corrections.

Output valid JSON with the following structure:
{
  "decision": "APPROVED | REQUEST_REVISION | REJECTED",
  "reviewer_role": "Attending Physician / Clinical Reviewer",
  "simulated_physician_minutes": 2.5,
  "confidence_in_ai_output": 0.90,
  "critique": "<Detailed physician evaluation>",
  "required_amendments": ["<Amendment 1 if needed>"],
  "gate_passed": true
}
"""


class HITLSimulatorAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="HITL Simulator",
            role="Human-in-the-Loop Attending Gatekeeper",
            llm_client=llm_client,
            system_prompt=HITL_SYSTEM_PROMPT,
        )

    def execute(
        self,
        raw_source_case: Dict[str, Any],
        diagnostic_output: Dict[str, Any],
        safety_output: Dict[str, Any] = None,
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        case_text = raw_source_case.get("question", "") or raw_source_case.get("clinical_note", "")
        prompt = (
            f"Review this diagnostic plan as an Attending Physician Gatekeeper:\n\n"
            f"--- CLINICAL PRESENTATION ---\n{case_text}\n\n"
            f"--- AI DIAGNOSTIC PROPOSAL ---\n{json.dumps(diagnostic_output, indent=2)}\n\n"
            f"--- SAFETY EVALUATION INPUT ---\n{json.dumps(safety_output or {}, indent=2)}\n\n"
            f"Decide whether to Approve, Request Revision, or Reject. Respond in JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        resp = self.llm_client.generate(messages, temperature=0.2)
        data = self.parse_json_response(resp.content)

        decision = data.get("decision", "APPROVED")
        flags = []
        if decision != "APPROVED":
            flags.append(f"HITL Intervention: {decision} - {str(data.get('critique', ''))[:80]}")

        preview = f"HITL: {decision} ({data.get('simulated_physician_minutes', 2.0)} min review)"
        step_log = self.build_step_log(resp, preview, flags=flags)
        return data, step_log
