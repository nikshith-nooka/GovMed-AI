"""Safety Validator Agent: Evaluates contraindications, drug safety, missed red flags, and emergency priorities."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

SAFETY_SYSTEM_PROMPT = """You are a Clinical Safety & Pharmacotherapy Validator.
Your mandate is patient protection: analyze the proposed differential diagnosis and next steps for:
1. Missed emergency red flags (e.g., unrecognized signs of stroke, dissection, shock).
2. Contraindicated actions or dangerous workup delays.
3. Unsafe diagnostic assumptions.

Output valid JSON with the following structure:
{
  "safety_status": "APPROVED | CAUTION_REQUIRED | CRITICAL_HAZARD",
  "safe_to_proceed": true,
  "safety_score": 0.95,
  "safety_violations_count": 0,
  "safety_flags": [
    {
      "hazard_type": "CONTRAINDICATION | MISSED_RED_FLAG | WORKUP_DELAY",
      "severity": "LOW | MEDIUM | HIGH | CRITICAL",
      "description": "<Clinical hazard description>",
      "mitigation": "<Action required to ensure patient safety>"
    }
  ],
  "safety_summary": "<Executive summary of safety findings>"
}
"""


class SafetyValidatorAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="Safety Validator",
            role="Contraindication & Critical Hazard Validator",
            llm_client=llm_client,
            system_prompt=SAFETY_SYSTEM_PROMPT,
        )

    def execute(
        self,
        raw_source_case: Dict[str, Any],
        diagnostic_output: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        case_text = raw_source_case.get("question", "") or raw_source_case.get("clinical_note", "")
        prompt = (
            f"Perform rigorous clinical safety audit:\n\n"
            f"--- PATIENT PRESENTATION ---\n{case_text}\n\n"
            f"--- PROPOSED DIAGNOSTIC PLAN ---\n{json.dumps(diagnostic_output, indent=2)}\n\n"
            f"Check for contraindications, missed red flags, and immediate safety hazards. Respond in JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        resp = self.llm_client.generate(messages, temperature=0.1)
        data = self.parse_json_response(resp.content)

        flags = []
        violations = data.get("safety_flags", [])
        for v in violations:
            flags.append(f"Safety Hazard [{v.get('severity', 'WARN')}]: {v.get('description', '')}")

        preview = f"Safety: {data.get('safety_status', 'APPROVED')} | Violations: {len(violations)}"
        step_log = self.build_step_log(resp, preview, flags=flags)
        return data, step_log
