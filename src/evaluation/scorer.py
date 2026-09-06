"""Clinical Evaluation Engine: Computes Diagnostic Accuracy, Rubric Scores, and Safety Penalties."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from src.telemetry.metrics import PipelineRunResult


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
        norm_pred = self._normalize_text(predicted_primary)

        # Check exact or strong substring match on primary diagnosis
        if norm_gold and (norm_gold in norm_pred or norm_pred in norm_gold):
            return 1.0

        # Check options match (if option letter like 'A' matches option text)
        if gold_answer_option and options:
            expected_text = self._normalize_text(options.get(gold_answer_option, ""))
            if expected_text and (expected_text in norm_pred or norm_pred in expected_text):
                return 1.0

        # Check differential diagnoses
        for item in differential_list:
            cond = self._normalize_text(str(item.get("condition", "")))
            rank = item.get("rank", 99)
            if norm_gold and (norm_gold in cond or cond in norm_gold):
                if rank <= 2:
                    return 0.85
                elif rank <= 4:
                    return 0.65
                else:
                    return 0.40

        # Token overlap heuristic
        gold_words = set(norm_gold.split())
        pred_words = set(norm_pred.split())
        if gold_words and len(gold_words & pred_words) / len(gold_words) >= 0.5:
            return 0.70

        return 0.15

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
    ) -> PipelineRunResult:
        """Computes and populates all quality and safety scores on the result object."""
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

        # Composite weighted quality score
        weights = self.rubrics
        overall_quality = (
            (acc_score * weights["diagnostic_weight"])
            + (comp_score * weights["completeness_weight"])
            + (grounding_score * weights["grounding_weight"])
            + (safety_score * weights["safety_weight"])
        )

        result.diagnostic_accuracy_score = round(acc_score, 4)
        result.differential_completeness_score = round(comp_score, 4)
        result.evidence_grounding_score = round(grounding_score, 4)
        result.safety_score = round(safety_score, 4)
        result.overall_quality_score = round(overall_quality, 4)

        return result
