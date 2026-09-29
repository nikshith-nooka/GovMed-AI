"""LLM-as-Judge: Clinical peer-review agent that evaluates AI-generated diagnoses and reports."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from src.agents.base import BaseClinicalAgent
from src.llm.client import UnifiedLLMClient
from src.telemetry.metrics import AgentStepLog

JUDGE_SYSTEM_PROMPT = """You are a senior Clinical Peer Reviewer and Medical Quality Auditor.
Your role is to evaluate the quality of an AI-generated differential diagnosis and clinical report,
acting as an expert peer reviewer who would sign off on (or reject) the output before it reaches
a treating physician.

You evaluate across exactly four dimensions:

1. **Diagnostic Accuracy** (0.0–1.0):
   How correct and clinically appropriate is the primary diagnosis and differential list?
   Consider whether the leading diagnosis is supported by the presented findings, whether
   the differential is well-ranked by likelihood, and whether clinically important conditions
   are included or dangerously omitted.

2. **Clinical Reasoning Quality** (0.0–1.0):
   How logical, structured, and clinically coherent is the reasoning chain? Consider whether
   the agent follows a systematic approach (history → exam → differential → plan), whether
   the reasoning demonstrates understanding of disease pathophysiology, and whether the
   clinical narrative flows appropriately from evidence to conclusion.

3. **Evidence Grounding** (0.0–1.0):
   How well are claims anchored to the actual patient data provided? Consider whether the
   agent references specific vitals, labs, history elements, or examination findings from the
   case rather than making generic or fabricated assertions. Penalize extrapolations not
   supported by the source data.

4. **Safety Awareness** (0.0–1.0):
   How well does the output identify and address patient safety concerns? Consider whether
   life-threatening conditions are appropriately triaged, dangerous workup delays are avoided,
   contraindications are flagged, and appropriate urgency is communicated.

Output valid JSON with the following structure:
{
  "diagnostic_accuracy": {
    "score": 0.0,
    "rationale": "<Specific justification for this score>"
  },
  "clinical_reasoning_quality": {
    "score": 0.0,
    "rationale": "<Specific justification for this score>"
  },
  "evidence_grounding": {
    "score": 0.0,
    "rationale": "<Specific justification for this score>"
  },
  "safety_awareness": {
    "score": 0.0,
    "rationale": "<Specific justification for this score>"
  },
  "overall_judge_score": 0.0,
  "summary": "<Brief overall clinical peer review assessment>"
}

All scores must be floats between 0.0 and 1.0. The overall_judge_score should be a weighted
average reflecting clinical priorities: diagnostic accuracy (0.35), clinical reasoning (0.25),
evidence grounding (0.20), safety awareness (0.20)."""

JUDGE_USER_TEMPLATE = """Perform a rigorous clinical peer review of the following AI-generated output.

--- PATIENT CASE ---
{case_text}

--- AI-GENERATED CLINICAL OUTPUT ---
{output_text}

Evaluate across the four dimensions (diagnostic accuracy, clinical reasoning quality,
evidence grounding, safety awareness) and provide an overall judge score.
Respond in JSON."""


class LLMJudgeAgent(BaseClinicalAgent):
    """Evaluates clinical AI outputs using an LLM acting as a clinical peer reviewer."""

    def __init__(self, llm_client: UnifiedLLMClient):
        super().__init__(
            name="LLM Judge Agent",
            role="Clinical Peer Review & Quality Auditor",
            llm_client=llm_client,
            system_prompt=JUDGE_SYSTEM_PROMPT,
        )

    def execute(
        self,
        raw_outputs: Dict[str, Any],
        clinical_case: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], AgentStepLog]:
        """Evaluate clinical outputs across four quality dimensions.

        Args:
            raw_outputs: The raw agent outputs (diagnosis, safety, verifier results, etc.).
            clinical_case: The original clinical case/vignette.

        Returns:
            Tuple of (judge_scores_dict, AgentStepLog).
        """
        case_text = (
            clinical_case.get("question", "")
            or clinical_case.get("clinical_note", "")
            or json.dumps(clinical_case, indent=2)
        )
        output_text = json.dumps(raw_outputs, indent=2, default=str)

        prompt = JUDGE_USER_TEMPLATE.format(
            case_text=case_text,
            output_text=output_text,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        resp = self.llm_client.generate(messages, temperature=0.1, max_tokens=2000)
        data = self.parse_json_response(resp.content)

        # Ensure all required dimensions are present with valid scores
        expected_dims = [
            "diagnostic_accuracy",
            "clinical_reasoning_quality",
            "evidence_grounding",
            "safety_awareness",
        ]
        for dim in expected_dims:
            if dim not in data:
                data[dim] = {"score": 0.5, "rationale": "Dimension not provided by judge."}
            else:
                score = data[dim].get("score", 0.5)
                data[dim]["score"] = max(0.0, min(1.0, float(score)))

        # Compute overall judge score if missing
        if "overall_judge_score" not in data or not isinstance(data.get("overall_judge_score"), (int, float)):
            weights = {
                "diagnostic_accuracy": 0.35,
                "clinical_reasoning_quality": 0.25,
                "evidence_grounding": 0.20,
                "safety_awareness": 0.20,
            }
            data["overall_judge_score"] = round(
                sum(data[d]["score"] * w for d, w in weights.items()), 4
            )

        # Build step log
        dim_scores = {d: data[d]["score"] for d in expected_dims}
        preview = (
            f"Judge Score: {data['overall_judge_score']:.2f} | "
            + " | ".join(f"{k}: {v:.2f}" for k, v in dim_scores.items())
        )
        flags = []
        if data["overall_judge_score"] < 0.4:
            flags.append("Judge Flag: Overall quality critically low")
        for dim in expected_dims:
            if data[dim]["score"] < 0.3:
                flags.append(f"Judge Flag: {dim} critically low ({data[dim]['score']:.2f})")

        step_log = self.build_step_log(resp, preview, flags=flags)
        return data, step_log
