"""Consistency Checker Agent: Verifies logical alignment between findings, differential ranking, and workup."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

CONSISTENCY_SYSTEM_PROMPT = """You are a Clinical Logic & Consistency Auditor.
Verify that the proposed differential diagnosis logically matches the patient's positive symptoms and that the recommended tests match the highest priority conditions.
Identify any internal contradictions.

Output valid JSON with the following structure:
{
  "consistency_status": "CONSISTENT | MINOR_INCONSISTENCY | SEVERE_CONTRADICTION",
  "consistency_score": 0.95,
  "inconsistencies_found": [],
  "logical_validity": true
}
"""


class ConsistencyCheckerAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="Consistency Checker",
            role="Diagnostic Logic & Coherence Auditor",
            llm_client=llm_client,
            system_prompt=CONSISTENCY_SYSTEM_PROMPT,
        )

    def execute(
        self,
        extracted_findings: Dict[str, Any],
        diagnostic_output: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        prompt = (
            f"Audit internal diagnostic consistency:\n\n"
            f"Findings: {json.dumps(extracted_findings, indent=2)}\n\n"
            f"Diagnoses: {json.dumps(diagnostic_output, indent=2)}\n\n"
            f"Check for internal contradictions. Respond in JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        resp = self.llm_client.generate(messages, temperature=0.1)
        data = self.parse_json_response(resp.content)
        preview = f"Consistency: {data.get('consistency_status', 'CONSISTENT')} ({data.get('consistency_score', 1.0)})"
        step_log = self.build_step_log(resp, preview)
        return data, step_log
