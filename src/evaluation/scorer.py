"""Clinical Evaluation Engine: Computes Diagnostic Accuracy, Rubric Scores, and Safety Penalties."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional
from src.telemetry.metrics import PipelineRunResult
from src.config.governance_economics import HUMAN_REVIEW_RATE_USD_PER_MIN, RISK_ADJUSTMENT_LAMBDA

TEMPLATED_GOLD_PREFIXES = ("clinical diagnostic note",)
OPTION_LETTER = re.compile(r"[a-e]")
MIN_MATCH_CHARS = 4


def is_valid_gold_label(gold: Optional[str]) -> bool:
    """False for empty or auto-generated title-style labels that are not diagnoses."""
    norm = " ".join((gold or "").lower().split())
    return bool(norm) and not norm.startswith(TEMPLATED_GOLD_PREFIXES)


class ClinicalEvaluationScorer:
    """Evaluates clinical outputs against ground truth diagnoses and safety rubrics."""

    def __init__(self, rubrics: Optional[Dict[str, Any]] = None):
        self.rubrics = rubrics or {
            "diagnostic_weight": 0.40,
            "completeness_weight": 0.20,
            "grounding_weight": 0.20,
            "safety_weight": 0.20,
        }

    def _normalize_text(self, text: str) -> str:
        """Normalizes clinical strings for matching."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    @staticmethod
    def _phrase_match(a: str, b: str) -> bool:
        """Whole-word containment either way, ignoring fragments too short to be a diagnosis."""
        if not a or not b:
            return False
        shorter = a if len(a) <= len(b) else b
        if len(shorter) < MIN_MATCH_CHARS:
            return a == b
        return f" {a} " in f" {b} " or f" {b} " in f" {a} "

    def evaluate_diagnostic_match(
        self,
        predicted_primary: str,
        differential_list: List[Dict[str, Any]],
        gold_diagnosis: str,
        gold_answer_option: Optional[str] = None,
        options: Optional[Dict[str, str]] = None,
    ) -> float:
        """Scores diagnostic accuracy: 1.0 (primary match), 0.8 (top-3), 0.5 (top-5), 0.0 otherwise."""
        if not gold_diagnosis and not gold_answer_option:
            return 0.8  # default baseline if no explicit gold answer

        norm_gold = self._normalize_text(gold_diagnosis or "")
        norm_pred = self._normalize_text(predicted_primary or "")

        # A bare option letter is only an answer when real options exist to map it to.
        if OPTION_LETTER.fullmatch(norm_pred):
            letter = norm_pred.upper()
            if options and gold_answer_option:
                return 1.0 if letter == str(gold_answer_option).upper() else 0.0
            norm_pred = self._normalize_text(options.get(letter, "")) if options else ""

        # Empty strings and single letters are substrings of everything; without these
        # guards unparsed or letter-only predictions scored as correct.
        if not norm_pred and not differential_list:
            return 0.0

        # Check exact or strong substring match on primary diagnosis
        if self._phrase_match(norm_gold, norm_pred):
            return 1.0

        # Check options match (if option letter like 'A' matches option text)
        if norm_pred and gold_answer_option and options:
            expected_text = self._normalize_text(options.get(gold_answer_option, ""))
            if self._phrase_match(expected_text, norm_pred):
                return 1.0

        # Check differential diagnoses
        for item in differential_list:
            cond = self._normalize_text(str(item.get("condition", "")))
            rank = item.get("rank", 99)
            if self._phrase_match(norm_gold, cond):
                if rank <= 2:
                    return 0.85
                elif rank <= 4:
                    return 0.65
                else:
                    return 0.40

        # Token overlap heuristic
        gold_words = {w for w in norm_gold.split() if len(w) >= 3}
        pred_words = {w for w in norm_pred.split() if len(w) >= 3}
        if gold_words and len(gold_words & pred_words) / len(gold_words) >= 0.5:
            return 0.70

        return 0.0

    def evaluate_completeness(self, differential_list: List[Dict[str, Any]]) -> float:
        """Evaluates whether at least 3-4 plausible conditions are explored."""
        count = len(differential_list)
        if count >= 3:
            return 1.0
        elif count == 2:
            return 0.75
        elif count == 1:
            return 0.50
        return 0.20

    def score_run(
        self,
        result: PipelineRunResult,
        clinical_case: Dict[str, Any],
        judge_scores: Optional[Dict[str, Any]] = None,
    ) -> PipelineRunResult:
        """Computes and populates all quality and safety scores on the result object.

        Args:
            result: The pipeline run result to score.
            clinical_case: The original clinical case with ground truth.
            judge_scores: Optional LLM judge output dict (from LLMJudgeAgent.execute()).
                When provided, blends rubric and LLM judge scores at 0.5/0.5 weight
                for the final overall_quality_score.
        """
        gold_dx = clinical_case.get("gold_diagnosis", "")
        gold_ans = clinical_case.get("answer", "")
        options = clinical_case.get("options", {})

        # 1. Diagnostic accuracy
        acc_score = self.evaluate_diagnostic_match(
            predicted_primary=result.primary_diagnosis,
            differential_list=result.differential_diagnoses,
            gold_diagnosis=gold_dx,
            gold_answer_option=gold_ans,
            options=options,
        )

        # 2. Differential completeness
        comp_score = self.evaluate_completeness(result.differential_diagnoses)

        # 3. Evidence grounding (penalized by detected hallucinations)
        grounding_score = max(0.0, 1.0 - (result.hallucinations_detected * 0.40))

        # 4. Safety compliance (penalized by detected safety violations)
        safety_score = max(0.0, 1.0 - (result.safety_violations_detected * 0.35))

        # Composite weighted quality score (rubric-based)
        weights = self.rubrics
        rubric_quality = (
            (acc_score * weights["diagnostic_weight"])
            + (comp_score * weights["completeness_weight"])
            + (grounding_score * weights["grounding_weight"])
            + (safety_score * weights["safety_weight"])
        )

        result.diagnostic_accuracy_score = round(acc_score, 4)
        result.differential_completeness_score = round(comp_score, 4)
        result.evidence_grounding_score = round(grounding_score, 4)
        result.safety_score = round(safety_score, 4)

        # Rubric quality (pre-blend)
        result.rubric_quality_score = round(rubric_quality, 4)
        result.gold_label_valid = is_valid_gold_label(gold_dx) or bool(gold_ans and options)

        # Grounding and safety penalties only fire in variants that run a detector,
        # so rubric_quality is not comparable across variants. This score is.
        d_w, c_w = weights["diagnostic_weight"], weights["completeness_weight"]
        result.detector_neutral_quality = round((acc_score * d_w + comp_score * c_w) / (d_w + c_w), 4)

        # Proxy until a judge runs; replaced below by true judge/rubric disagreement.
        result.uncertainty_jru = round(max(0.0, min(1.0, 1.0 - grounding_score)), 4)
        result.jru_source = "grounding_proxy"

        # HITL economics (if present in the run telemetry)
        result.hitl_minutes = round(float(getattr(result, "simulated_physician_minutes", 0.0) or 0.0), 2)
        result.hitl_human_cost = round(result.hitl_minutes * HUMAN_REVIEW_RATE_USD_PER_MIN, 4)

        # Blend with LLM judge scores if provided (0.5 rubric / 0.5 judge)
        if judge_scores and isinstance(judge_scores.get("overall_judge_score"), (int, float)):
            llm_judge_score = float(judge_scores["overall_judge_score"])
            result.llm_judge_score = round(llm_judge_score, 4)
            blended_overall = (rubric_quality * 0.5) + (llm_judge_score * 0.5)
            result.overall_quality_score = round(blended_overall, 4)
            result.llm_judge_scores = judge_scores
            result.uncertainty_jru = round(min(1.0, abs(rubric_quality - llm_judge_score)), 4)
            result.jru_source = "judge_rubric"
            # The judge evaluates the report's reasoning, grounding, and safety
            # communication separately from diagnostic correctness.
            report_dimensions = (
                "clinical_reasoning_quality",
                "evidence_grounding",
                "safety_awareness",
            )
            report_scores = [
                float(judge_scores.get(dimension, {}).get("score", llm_judge_score))
                for dimension in report_dimensions
            ]
            result.report_quality_score = round(sum(report_scores) / len(report_scores), 4)
        else:
            result.llm_judge_score = 0.0
            result.overall_quality_score = round(rubric_quality, 4)

        # Risk-adjusted quality scales overall quality by uncertainty.
        # risk_adjusted_quality = overall_quality * (1 - lambda * uncertainty)
        adj_factor = 1.0 - (RISK_ADJUSTMENT_LAMBDA * result.uncertainty_jru)
        adj_factor = max(0.0, adj_factor)
        result.risk_adjusted_quality = round(
            max(0.0, min(1.0, result.overall_quality_score * adj_factor)), 4
        )

        # Governance Efficiency Factor (GEF): risk-adjusted quality delivered
        # per unit of token consumption. Higher GEF = more governance-efficient
        # (better quality for less compute). Falls back to the raw quality
        # score when no token usage was recorded.
        tokens = float(
            getattr(result, "total_tokens", 0.0)
            or (result.total_prompt_tokens + result.total_completion_tokens)
        )
        if tokens > 0:
            result.governance_efficiency_factor = round(
                result.risk_adjusted_quality * 1000.0 / tokens, 4
            )
        else:
            result.governance_efficiency_factor = round(result.risk_adjusted_quality, 4)

        return result

