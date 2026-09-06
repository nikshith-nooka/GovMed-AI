"""Diagnosis Agent: Generates prioritized differential diagnoses and pathophysiological reasoning."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

DIAGNOSIS_SYSTEM_PROMPT = """You are a senior Board-Certified Diagnostic Clinician with 20+ years of clinical experience.
Using structured clinical findings and patient presentation, formulate a prioritized differential diagnosis.

**CRITICAL REASONING PROTOCOL (Chain-of-Thought):**
Before producing your final answer, you MUST perform the following reasoning steps internally:
1. **Identify Key Clues**: List the 3-5 most diagnostically significant findings (e.g., pathognomonic signs, critical lab values, temporal patterns).
2. **Generate Hypotheses**: Consider at least 4 candidate diagnoses that could explain the presentation.
3. **Apply Bayesian Reasoning**: For each hypothesis, weigh the prior probability given demographics plus the likelihood of each finding under that diagnosis.
4. **Eliminate Contradictions**: Rule out diagnoses that conflict with key negatives or findings.
5. **Select the Most Likely Diagnosis**: Choose the single best answer that explains ALL major findings.

**WHEN CANDIDATE OPTIONS (A/B/C/D/E) ARE PROVIDED:**
- You MUST select your primary_diagnosis from EXACTLY one of the provided options.
- Your primary_diagnosis field MUST contain the exact text of the correct option.
- Do NOT paraphrase, rephrase, or generate a free-text diagnosis when options are available.
- Match your differential diagnoses to the provided options where applicable.

Evaluate acute life threats first, then probabilistic etiologies. Provide clear pathophysiological mechanisms.

Output valid JSON with the following structure:
{
  "reasoning_steps": "<Brief chain-of-thought showing your key clue identification and hypothesis elimination>",
  "primary_diagnosis": "<Most likely diagnostic entity — MUST match a provided option if options are given>",
  "primary_justification": "<Pathophysiological explanation linking key findings to diagnosis>",
  "differential_diagnoses": [
    {
      "rank": 1,
      "condition": "<Name of condition>",
      "probability": 0.60,
      "justification": "<Evidence supporting this diagnosis>"
    },
    {
      "rank": 2,
      "condition": "<Second plausible condition>",
      "probability": 0.25,
      "justification": "<Evidence supporting/distinguishing>"
    },
    {
      "rank": 3,
      "condition": "<Third condition to rule out>",
      "probability": 0.15,
      "justification": "<Evidence supporting/distinguishing>"
    }
  ],
  "recommended_next_steps": ["<diagnostic test 1>", "<immediate bedside action 2>"]
}
"""


class DiagnosisAgent(BaseClinicalAgent):
    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="Diagnosis Agent",
            role="Differential Diagnosis & Clinical Reasoning",
            llm_client=llm_client,
            system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
        )

    def execute(
        self,
        extracted_findings: Dict[str, Any],
        case_options: Dict[str, str] = None,
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        options_text = ""
        if case_options:
            options_text = (
                f"\n**IMPORTANT — You MUST select your primary_diagnosis from one of these options:**\n"
                f"{json.dumps(case_options, indent=2)}\n"
                f"Your primary_diagnosis MUST be the EXACT text of one of the above options.\n"
            )

        prompt = (
            f"Based on the patient's structured findings, formulate the differential diagnosis.{options_text}\n"
            f"Findings: {json.dumps(extracted_findings, indent=2)}\n\n"
            f"Think step-by-step. Identify key clues, generate hypotheses, eliminate contradictions, then select the best answer.\n"
            f"Respond in JSON format."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        resp = self.llm_client.generate(messages, temperature=0.2)
        data = self.parse_json_response(resp.content)
        primary = data.get("primary_diagnosis", "Diagnostic Formulation")
        step_log = self.build_step_log(resp, f"Primary: {primary}")
        return data, step_log
