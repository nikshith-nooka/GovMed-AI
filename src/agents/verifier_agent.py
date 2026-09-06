"""Verifier Agent: Cross-references diagnostic assertions against source clinical notes to detect hallucinations."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

VERIFIER_SYSTEM_PROMPT = """You are an adversarial Clinical Fact Verifier and Source Grounding Auditor.
Your singular objective is to cross-examine every claim made by the diagnostic agents against the RAW clinical source note.
Identify:
1. Fabricated patient history or phantom vitals/labs not in the note.
2. Ungrounded assertions or over-extrapolations.
3. Hallucinations in symptoms.

Output valid JSON with the following structure:
{
  "verification_status": "VERIFIED | FLAGGED_UNSUPPORTED_CLAIMS | CRITICAL_HALLUCINATION",
  "hallucination_detected": false,
  "confidence_score": 0.95,
  "supported_claims_count": 5,
  "flagged_claims": [
    {
      "claim": "<Claim made by diagnostic agent>",
      "issue": "<Why this claim is ungrounded or contradictory to source note>",
      "severity": "LOW | MEDIUM | HIGH"
    }
  ],
  "verification_summary": "<Executive summary of clinical factual grounding>"
}
"""


class VerifierAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="Verifier Agent",
            role="Source Note Grounding & Hallucination Auditor",
            llm_client=llm_client,
            system_prompt=VERIFIER_SYSTEM_PROMPT,
        )

    def execute(
        self,
        raw_source_case: Dict[str, Any],
        diagnostic_output: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        case_text = raw_source_case.get("question", "") or raw_source_case.get("clinical_note", "")
        prompt = (
            f"Cross-examine the diagnostic claims against the source note:\n\n"
            f"--- SOURCE CLINICAL NOTE ---\n{case_text}\n\n"
            f"--- DIAGNOSTIC CLAIMS TO AUDIT ---\n{json.dumps(diagnostic_output, indent=2)}\n\n"
            f"Detect any hallucinations or ungrounded statements. Respond in JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        resp = self.llm_client.generate(messages, temperature=0.1)
        data = self.parse_json_response(resp.content)

        flags = []
        if data.get("hallucination_detected", False) or data.get("flagged_claims"):
            for f in data.get("flagged_claims", []):
                flags.append(f"Verifier Flag: {f.get('issue', 'Unverified claim')}")

        preview = f"Status: {data.get('verification_status', 'VERIFIED')} | Flagged: {len(data.get('flagged_claims', []))}"
        step_log = self.build_step_log(resp, preview, flags=flags)
        return data, step_log
