"""Report Agent: Synthesizes findings, diagnoses, and governance notes into clinical SOAP documentation."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

REPORT_SYSTEM_PROMPT = """You are a Clinical Documentation Specialist.
Synthesize the extracted patient findings, differential diagnosis, and any governance oversight inputs into a structured clinical document conforming to the standard SOAP (Subjective, Objective, Assessment, Plan) format.

Output valid JSON with the following structure:
{
  "report_title": "<Clinical Diagnostic Note>",
  "subjective": "<Concise patient symptoms, timeline, past history>",
  "objective": "<Vitals, physical examination, diagnostic data>",
  "assessment": "<Primary diagnosis, clinical certainty, differential analysis>",
  "plan": "<Immediate therapeutic and diagnostic action plan>",
  "governance_summary": "<Summary of verification and safety checkpoints passed>"
}
"""


class ReportAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="Report Agent",
            role="Structured Clinical Documentation (SOAP)",
            llm_client=llm_client,
            system_prompt=REPORT_SYSTEM_PROMPT,
        )

    def execute(
        self,
        extracted_findings: Dict[str, Any],
        diagnostic_output: Dict[str, Any],
        governance_notes: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        prompt = (
            f"Generate structured clinical SOAP note from:\n"
            f"Extracted Findings: {json.dumps(extracted_findings, indent=2)}\n"
            f"Diagnostic Assessment: {json.dumps(diagnostic_output, indent=2)}\n"
            f"Governance/Safety Inputs: {json.dumps(governance_notes or {}, indent=2)}\n\n"
            f"Respond in JSON format."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        resp = self.llm_client.generate(messages, temperature=0.2)
        data = self.parse_json_response(resp.content)
        assessment_val = data.get('assessment', '')
        preview = f"SOAP Assessment: {str(assessment_val)[:100]}"
        step_log = self.build_step_log(resp, preview)
        return data, step_log
