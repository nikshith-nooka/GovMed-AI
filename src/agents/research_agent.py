"""Research Agent: Extracts clinical findings, vitals, history, and pertinent clues from vignettes."""

from __future__ import annotations

from typing import Any, Dict, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

RESEARCH_SYSTEM_PROMPT = """You are an expert Clinical Research & Chart Review Agent.
Your job is to read raw clinical case notes/vignettes and extract structured clinical data with high fidelity.
Never invent facts, lab values, or vitals not mentioned in the source note.

Output valid JSON with the following structure:
{
  "chief_complaint": "<patient chief complaint>",
  "demographics": "<age, sex, pertinent background>",
  "history_present_illness": "<narrative timeline of symptoms>",
  "pertinent_positives": ["<symptom 1>", "<exam finding 1>", "<abnormal lab 1>"],
  "pertinent_negatives": ["<symptom ruled out>", "<pertinent normal finding>"],
  "vitals_and_labs": {"<key>": "<value>"},
  "risk_factors": ["<risk 1>", "<risk 2>"]
}
"""


class ResearchAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="Research Agent",
            role="Information Gathering & Clinical Extraction",
            llm_client=llm_client,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
        )

    def execute(self, clinical_case: Dict[str, Any]) -> Tuple[Dict[str, Any], AgentStepLog]:
        case_text = clinical_case.get("question", "") or clinical_case.get("clinical_note", "")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Extract structured clinical findings from this case vignette:\n\n{case_text}\n\nRespond in JSON format.",
            },
        ]
        resp = self.llm_client.generate(messages, temperature=0.1)
        data = self.parse_json_response(resp.content)
        preview = f"CC: {data.get('chief_complaint', 'Extracted')} | Positives: {len(data.get('pertinent_positives', []))}"
        step_log = self.build_step_log(resp, preview)
        return data, step_log
