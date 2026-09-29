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
YES_NO_MAYBE = frozenset({"yes", "no", "maybe"})
# "B", "(B)", "B.", "B) text", "Option B", "Answer: B - text"; a bare capital followed by a space
# ("A 45-year-old...") is not a letter choice.
LETTER_CHOICE = re.compile(
    r"^\s*(?:(?:the\s+)?(?:correct\s+)?(?:option|answer|choice)\s*(?:is)?\s*[:\-]?\s*)?"
    r"[\(\[]?([A-Ea-e])(?:[\)\]\.:\-]|\s*$)\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
KEYWORD_LETTER = re.compile(r"^\s*(?:option|answer|choice)\s*(?:is)?\s*[:\-]?\s*\(?([A-Ea-e])\)?\b\s*(.*)$",
                            re.IGNORECASE | re.DOTALL)

SCORING_OPTION_EXACT = "option_exact"
SCORING_YES_NO_MAYBE = "yesno_exact"
SCORING_FREE_TEXT = "free_text"


def _norm(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return " ".join(text.split())


def parse_option_choice(predicted: str, options: Dict[str, str]) -> Dict[str, Any]:
    """Maps a model answer to exactly one option key, or reports why it cannot.

    Returns {"choice": letter|None, "parse_status": ...} where parse_status is one of
    "letter", "text_exact", "text_contained", "ambiguous", "unparseable", "empty".
    """
    keys = {str(k).upper(): str(v) for k, v in (options or {}).items()}
    raw = str(predicted or "").strip()
    if not _norm(raw):
        return {"choice": None, "parse_status": "empty"}
    norm_opts = {k: _norm(v) for k, v in keys.items()}

    pred = _norm(raw)
    # Full option text first, so an option that itself starts like a letter ("C. difficile
    # colitis") is not read as choice C.
    exact = [k for k, v in norm_opts.items() if v and v == pred]
    if len(exact) == 1:
        return {"choice": exact[0], "parse_status": "text_exact"}
    if len(exact) > 1:
        return {"choice": None, "parse_status": "ambiguous"}

    match = KEYWORD_LETTER.match(raw) or LETTER_CHOICE.match(raw)
    if match and match.group(1).upper() in keys:
        letter, rest = match.group(1).upper(), _norm(match.group(2))
        own = norm_opts[letter]
        if not rest or (own and (f" {own} " in f" {rest} " or f" {rest} " in f" {own} ")):
            return {"choice": letter, "parse_status": "letter"}
        # A letter followed by text that is not that option ("B. <text of C>") contradicts itself.
        return {"choice": None, "parse_status": "ambiguous"}

    # Option text quoted inside a longer answer ("Diagnosis: <option text>"). Keep only
    # maximal matches so "aspiration pneumonia" does not also count "pneumonia".
    contained = [k for k, v in norm_opts.items()
                 if len(v) >= MIN_MATCH_CHARS and f" {v} " in f" {pred} "]
    maximal = [k for k in contained
               if not any(o != k and f" {norm_opts[k]} " in f" {norm_opts[o]} " for o in contained)]
    if len(maximal) == 1:
        return {"choice": maximal[0], "parse_status": "text_contained"}
    if len(maximal) > 1:
        return {"choice": None, "parse_status": "ambiguous"}
    return {"choice": None, "parse_status": "unparseable"}


def parse_yes_no_maybe(predicted: str) -> Dict[str, Any]:
    """PubMedQA answers: exactly one of yes / no / maybe must be asserted."""
    pred = _norm(predicted)
    if not pred:
        return {"choice": None, "parse_status": "empty"}
    words = pred.split()
    lead = words[1] if words[0] in ("conclusion", "answer", "decision") and len(words) > 1 else words[0]
    found = {w for w in words if w in YES_NO_MAYBE}
    if len(found) > 1:
        return {"choice": None, "parse_status": "ambiguous"}
    if lead in YES_NO_MAYBE:
        return {"choice": lead, "parse_status": "letter"}
    if found:
        return {"choice": found.pop(), "parse_status": "text_contained"}
    return {"choice": None, "parse_status": "unparseable"}


def is_yes_no_maybe(options: Optional[Dict[str, str]]) -> bool:
    return bool(options) and {_norm(v) for v in options.values()} == YES_NO_MAYBE


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
            if not isinstance(item, dict):
                continue
            cond = self._normalize_text(str(item.get("condition", "")))
            try:
                rank = int(item.get("rank"))
            except (TypeError, ValueError):
                rank = 99
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

    def score_diagnosis(
        self,
        predicted_primary: str,
        differential_list: List[Dict[str, Any]],
        clinical_case: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Routes to exact option scoring when the case has an answer key, else free-text matching.

        Option cases (MedQA/MedMCQA, and PubMedQA yes/no/maybe) score 1.0 iff the chosen option
        equals the key: no partial credit, no differential credit; an answer that cannot be
        mapped to exactly one option scores 0.0 and is flagged via parse_status.
        """
        options = clinical_case.get("options") or {}
        key = str(clinical_case.get("answer_idx") or clinical_case.get("answer") or "").strip().upper()
        if options and key in {str(k).upper() for k in options}:
            if is_yes_no_maybe(options):
                parsed = parse_yes_no_maybe(predicted_primary)
                gold = _norm(options.get(key, options.get(key.lower(), "")))
                correct = parsed["choice"] is not None and parsed["choice"] == gold
                choice = next((k for k, v in options.items() if _norm(v) == parsed["choice"]), None)
                mode = SCORING_YES_NO_MAYBE
            else:
                parsed = parse_option_choice(predicted_primary, options)
                choice = parsed["choice"]
                correct = choice is not None and choice == key
                mode = SCORING_OPTION_EXACT
            return {"score": 1.0 if correct else 0.0, "scoring_mode": mode, "choice": choice,
                    "parse_status": parsed["parse_status"],
                    "flagged": parsed["choice"] is None}
        score = self.evaluate_diagnostic_match(
            predicted_primary, differential_list, clinical_case.get("gold_diagnosis", ""),
            clinical_case.get("answer"), options,
        )
        return {"score": score, "scoring_mode": SCORING_FREE_TEXT, "choice": None,
                "parse_status": "empty" if not _norm(predicted_primary) else "free_text", "flagged": False}

    def evaluate_completeness(self, differential_list: List[Dict[str, Any]]) -> float:
        """Evaluates whether at least 3-4 plausible conditions are explored."""
        count = sum(isinstance(item, dict) for item in differential_list or [])
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

        # 1. Diagnostic accuracy (exact option scoring when the case has an answer key)
        diag = self.score_diagnosis(result.primary_diagnosis, result.differential_diagnoses, clinical_case)
        acc_score = diag["score"]
        result.scoring_mode = diag["scoring_mode"]
        result.option_choice = diag["choice"] or ""
        result.option_parse_status = diag["parse_status"]

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
            result.judge_provider = str(judge_scores.get("judge_provider", "") or "")
            result.judge_model = str(judge_scores.get("judge_model", "") or "")
            # A judge sharing the generator's weights grades its own output: its disagreement
            # with the rubric is not an independent uncertainty measurement.
            same_model = bool(result.judge_model) and result.judge_model.strip().lower() == str(result.model).strip().lower()
            if judge_scores.get("cross_model") is False or same_model:
                result.jru_source = "same_model_judge"
            else:
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

