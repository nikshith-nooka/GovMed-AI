"""Methodology tests: exact option scoring, paired statistics, agreement, power, judge independence,
the MedQA benchmark builder and the paper-number checker. No network access."""

import json

import pandas as pd
import pytest
from scipy import stats

from scripts.build_medqa_benchmark import build, content_hash, validate_case
from scripts.check_paper_numbers import check, extract_numbers
from scripts.run_rigor_analysis import _finite
from src.analysis.rigor import RigorousAnalysis, is_measured_jru
from src.data.loader import OPTION_KEYS, format_medqa_row, seeded_sample_indices
from src.evaluation.llm_judge import LLMJudgeAgent, SameModelJudgeError
from src.evaluation.scorer import (
    SCORING_FREE_TEXT,
    SCORING_OPTION_EXACT,
    SCORING_YES_NO_MAYBE,
    ClinicalEvaluationScorer,
    parse_option_choice,
)
from src.evaluation.statistics import (
    cohens_h,
    cohens_kappa_categorical,
    fleiss_kappa,
    holm_bonferroni,
    mcnemar_exact,
    mcnemar_exact_from_counts,
    mcnemar_mde,
    mcnemar_power,
    mcnemar_required_n,
    rank_biserial,
)
from src.llm.client import UnifiedLLMClient
from src.pipeline.orchestrator import ClinicalGovernancePipeline
from src.telemetry.db import BenchmarkDB

OPTIONS = {"A": "Aspiration pneumonia", "B": "Pneumonia", "C": "Pulmonary embolism", "D": "Asthma"}
MCQ = {"id": "medqa_test_0001", "question": "q", "options": OPTIONS, "answer": "C", "answer_idx": "C",
       "gold_diagnosis": "Pulmonary embolism"}


# ---------------------------------------------------------------- C2 exact option scoring
@pytest.mark.parametrize("answer, choice, status", [
    ("C", "C", "letter"),
    ("(c)", "C", "letter"),
    ("Answer: C", "C", "letter"),
    ("The correct answer is C.", "C", "letter"),
    ("C. Pulmonary embolism", "C", "letter"),
    ("pulmonary embolism.", "C", "text_exact"),
    ("Diagnosis: acute pulmonary embolism", "C", "text_contained"),
    ("Aspiration pneumonia", "A", "text_exact"),          # not also "Pneumonia"
    ("Likely aspiration pneumonia", "A", "text_contained"),  # maximal match only
])
def test_option_choice_parsing(answer, choice, status):
    parsed = parse_option_choice(answer, OPTIONS)
    assert (parsed["choice"], parsed["parse_status"]) == (choice, status)


@pytest.mark.parametrize("answer, status", [
    ("Pulmonary embolism or asthma", "ambiguous"),
    ("B. Pulmonary embolism", "ambiguous"),   # letter contradicts the text
    ("Myocardial infarction", "unparseable"),
    ("A 45-year-old with sepsis", "unparseable"),  # an article, not option A
    ("", "empty"),
    ("   ", "empty"),
])
def test_option_choice_rejects_unmappable_answers(answer, status):
    parsed = parse_option_choice(answer, OPTIONS)
    assert parsed["choice"] is None and parsed["parse_status"] == status


@pytest.mark.parametrize("answer, expected", [
    ("C", 1.0), ("Pulmonary embolism", 1.0), ("B", 0.0), ("Pneumonia", 0.0), ("", 0.0),
    ("Pulmonary embolism or asthma", 0.0),
])
def test_option_exact_scoring_has_no_partial_credit(answer, expected):
    scorer = ClinicalEvaluationScorer()
    # A differential that contains the key must not rescue a wrong primary answer.
    out = scorer.score_diagnosis(answer, [{"rank": 1, "condition": "Pulmonary embolism"}], MCQ)
    assert out["score"] == expected and out["scoring_mode"] == SCORING_OPTION_EXACT
    assert out["flagged"] == (out["choice"] is None)


def test_free_text_cases_keep_lenient_scoring():
    scorer = ClinicalEvaluationScorer()
    out = scorer.score_diagnosis("Acute Gouty Arthritis", [], {"gold_diagnosis": "Gouty Arthritis"})
    assert out["scoring_mode"] == SCORING_FREE_TEXT and out["score"] == 1.0


@pytest.mark.parametrize("answer, expected, status", [
    ("Yes", 1.0, "letter"), ("Conclusion: yes, the data support it", 1.0, "letter"),
    ("no", 0.0, "letter"), ("The evidence says maybe", 0.0, "text_contained"),
    ("yes or no", 0.0, "ambiguous"), ("", 0.0, "empty"),
])
def test_pubmedqa_yes_no_maybe_exact(answer, expected, status):
    case = {"options": {"A": "yes", "B": "no", "C": "maybe"}, "answer": "A", "gold_diagnosis": "Conclusion: YES"}
    out = ClinicalEvaluationScorer().score_diagnosis(answer, [], case)
    assert (out["score"], out["parse_status"], out["scoring_mode"]) == (expected, status, SCORING_YES_NO_MAYBE)


def test_scoring_mode_is_persisted(tmp_path):
    db = BenchmarkDB(str(tmp_path / "b.db"))
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    result = ClinicalGovernancePipeline(client).run(MCQ, "baseline")
    result.primary_diagnosis = "C"
    scored = ClinicalEvaluationScorer().score_run(result, MCQ)
    assert scored.diagnostic_accuracy_score == 1.0 and scored.option_choice == "C"
    db.log_run(scored)
    row = db.get_runs_df().iloc[0]
    assert (row["scoring_mode"], row["option_choice"], row["option_parse_status"]) == ("option_exact", "C", "letter")


# ---------------------------------------------------------------- C3 statistics
def test_mcnemar_exact_known_value():
    # b=10, c=2: p = 2 * P(X <= 2 | n=12, 0.5) = 2 * 79/4096
    assert mcnemar_exact_from_counts(10, 2)["p_value"] == pytest.approx(2 * 79 / 4096)
    assert mcnemar_exact_from_counts(0, 0)["p_value"] == 1.0
    a = [True] * 10 + [False] * 2 + [True] * 5
    b = [False] * 10 + [True] * 2 + [True] * 5
    res = mcnemar_exact(a, b)
    assert (res["only_a_correct"], res["only_b_correct"], res["n_pairs"]) == (10, 2, 17)
    assert res["p_value"] == pytest.approx(stats.binomtest(2, 12, 0.5).pvalue)


def test_holm_adjustment():
    adjusted = holm_bonferroni([0.01, 0.04, 0.03, 0.005])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert holm_bonferroni([0.5, None, 0.9]) == pytest.approx([1.0, None, 0.9]) or \
        holm_bonferroni([0.5, None, 0.9])[1] is None
    assert holm_bonferroni([0.2, 0.9])[1] <= 1.0


def test_effect_sizes():
    assert cohens_h(0.5, 0.5) == 0.0
    assert cohens_h(0.2, 0.8) == pytest.approx(-cohens_h(0.8, 0.2))
    assert rank_biserial([1, 2, 3]) == 1.0 and rank_biserial([-1, -2]) == -1.0
    assert rank_biserial([0, 0]) is None
    assert rank_biserial([1, -2, 3]) == pytest.approx((1 + 3 - 2) / 6)


def test_fleiss_kappa_textbook_example():
    # Fleiss (1971) style example used on Wikipedia: 10 subjects, 14 raters, 5 categories, kappa ~ 0.210.
    table = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
             [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    assert fleiss_kappa(table) == pytest.approx(0.210, abs=1e-3)
    with pytest.raises(ValueError):
        fleiss_kappa([[2, 1], [1, 1]])


def test_cohens_kappa_categorical():
    assert cohens_kappa_categorical(list("aabb"), list("aabb")) == 1.0
    # po = 0.5, pe = 0.5 -> 0
    assert cohens_kappa_categorical(list("abab"), list("aabb")) == pytest.approx(0.0)


def test_power_is_monotone_and_consistent():
    powers_n = [mcnemar_power(n, 0.05, 0.2) for n in (50, 100, 300, 1000, 3000)]
    assert powers_n == sorted(powers_n) and powers_n[-1] > 0.99
    powers_d = [mcnemar_power(300, d, 0.2) for d in (0.01, 0.03, 0.05, 0.1)]
    assert powers_d == sorted(powers_d)
    n = mcnemar_required_n(0.05, 0.2)
    assert mcnemar_power(n, 0.05, 0.2) >= 0.8 > mcnemar_power(n - 1, 0.05, 0.2)
    mde_small, mde_big = mcnemar_mde(100, 0.2), mcnemar_mde(1000, 0.2)
    assert mde_big < mde_small and mcnemar_power(1000, mde_big, 0.2) == pytest.approx(0.8, abs=1e-6)
    assert mcnemar_required_n(0.05, 0.02) is None  # difference larger than discordance is impossible
    assert mcnemar_mde(71, 0.02) is None


# ---------------------------------------------------------------- C8 judge independence
def test_same_model_judge_is_rejected():
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    with pytest.raises(SameModelJudgeError):
        LLMJudgeAgent(client, generator_model=client.default_model)
    with pytest.raises(SameModelJudgeError):
        LLMJudgeAgent(client, generator_model=client.default_model.upper())
    assert LLMJudgeAgent(client, generator_model="other/model").cross_model is True


def test_flagged_same_model_judge_is_not_measured_jru():
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    judge = LLMJudgeAgent(client, generator_model=client.default_model, allow_same_model=True)
    result = ClinicalGovernancePipeline(client).run(MCQ, "baseline")
    scores, step = judge.execute(result.raw_outputs, MCQ)
    assert scores["cross_model"] is False and scores["judge_model"] == client.default_model
    assert any("same model" in f for f in step.flags)
    scored = ClinicalEvaluationScorer().score_run(result, MCQ, judge_scores=scores)
    assert scored.jru_source == "same_model_judge" and scored.judge_model == client.default_model

    cross = dict(scores, cross_model=True, judge_model="other/judge")
    rescored = ClinicalEvaluationScorer().score_run(result, MCQ, judge_scores=cross)
    assert rescored.jru_source == "judge_rubric"
    assert is_measured_jru("judge_rubric", "other/judge", client.default_model)
    assert not is_measured_jru("judge_rubric", client.default_model, client.default_model)
    assert not is_measured_jru("judge_rubric", None, client.default_model)
    assert not is_measured_jru("grounding_proxy", "other/judge", client.default_model)


# ---------------------------------------------------------------- C1 MedQA builder
def _fake_rows(n):
    return [{"question": f"Stem {i}?", "options": {k: f"opt {k}{i}" for k in OPTION_KEYS},
             "answer_idx": OPTION_KEYS[i % 4], "answer": f"opt {OPTION_KEYS[i % 4]}{i}", "meta_info": "step1"}
            for i in range(n)]


def test_medqa_builder_schema_and_determinism():
    population = [format_medqa_row(r, i, "test") for i, r in enumerate(_fake_rows(40))]
    cases = build(population, 10, seed=42)
    assert len(cases) == 10 and cases == build(population, 10, seed=42)
    assert build(population, 10, seed=7) != cases
    assert [c["source_index"] for c in cases] == seeded_sample_indices(40, 10, 42)
    for c in cases:
        validate_case(c)
        assert c["id"] == c["case_id"] and c["id"].startswith("medqa_test_")
        assert c["answer"] == c["answer_idx"] and c["options"][c["answer_idx"]] == c["answer_text"] == c["gold_diagnosis"]
        assert c["source"] == "MedQA-USMLE (Jin et al., 2021)" and c["split"] == "test"
        # Every case is scorable by exact option matching.
        assert ClinicalEvaluationScorer().score_diagnosis(c["answer_idx"], [], c)["score"] == 1.0
    assert content_hash(cases) == content_hash(build(population, 10, seed=42))


def test_medqa_row_validation():
    bad = dict(_fake_rows(1)[0], answer="something else")
    with pytest.raises(ValueError):
        format_medqa_row(bad, 0)
    with pytest.raises(ValueError):
        format_medqa_row(dict(_fake_rows(1)[0], answer_idx="E"), 0)
    listed = dict(_fake_rows(1)[0], options=[{"key": k, "value": f"opt {k}0"} for k in OPTION_KEYS])
    assert format_medqa_row(listed, 0)["options"]["A"] == "opt A0"


def test_frozen_medqa_benchmark_file_if_present():
    import pathlib

    path = pathlib.Path("benchmarks/medqa_300.json")
    if not path.exists():
        pytest.skip("benchmarks/medqa_300.json not built")
    cases = json.loads(path.read_text())
    assert len(cases) == 300 and len({c["id"] for c in cases}) == 300
    for c in cases:
        validate_case(c)


# ---------------------------------------------------------------- C3/C7 report integration
@pytest.fixture
def option_benchmark(tmp_path):
    cases = [dict(MCQ, id=f"medqa_test_{i:04d}", case_id=f"medqa_test_{i:04d}") for i in range(8)]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases))
    db = BenchmarkDB(str(tmp_path / "bench.db"))
    client = UnifiedLLMClient(provider="mock", force_mock=True)
    pipeline, scorer = ClinicalGovernancePipeline(client), ClinicalEvaluationScorer()
    for i, case in enumerate(cases):
        for variant in ("baseline", "safety"):
            result = pipeline.run(case, variant)
            result.raw_outputs["diagnosis"] = {"primary_diagnosis": "C" if (i + (variant == "safety")) % 3 else "A",
                                               "differential_diagnoses": []}
            db.log_run(scorer.score_run(result, case))
    return str(tmp_path / "bench.db"), str(cases_path)


def test_report_has_mcnemar_holm_power_and_is_json_safe(option_benchmark):
    db_path, cases_path = option_benchmark
    report = RigorousAnalysis(db_path, cases_path, reference_db_path=None).report()
    assert report["measurement_validity"]["runs_by_scoring_mode"] == {"option_exact": 16}
    (acc,) = report["accuracy_tests"]
    assert acc["comparison"] == "V4 - V1" and acc["n_pairs"] == 8
    assert acc["mcnemar_exact_p_holm"] >= acc["mcnemar_exact_p"]
    assert all("wilcoxon_p_holm" in t and "rank_biserial" in t for t in report["paired_tests"])
    assert report["multiple_comparisons"]["family_size"] == len(report["paired_tests"]) + 1
    assert report["power_analysis"]["required_n_for_5pt_diff_by_assumed_discordance"]["0.20"] > 0
    assert report["jru_measurement"]["n_runs_measured"] == 0
    json.dumps(_finite(report), allow_nan=False, default=str)


def test_clinician_validation_states(option_benchmark):
    db_path, cases_path = option_benchmark
    analysis = RigorousAnalysis(db_path, cases_path, reference_db_path=None)
    cv = analysis.clinician_validation()
    assert cv["n_reviews"] == 0 and cv["status"].startswith("insufficient_data")

    run_ids = analysis.runs["run_id"].tolist()[:4]
    verdicts = {"r1": ["correct", "incorrect", "correct", "acceptable"],
                "r2": ["correct", "incorrect", "incorrect", "acceptable"],
                "r3": ["correct", "incorrect", "correct", "correct"]}
    rows = [{"run_id": rid, "case_id": "c", "reviewer_id": r, "diagnosis_verdict": v[i], "quality_rating": 4,
             "alert_ratings": "[]"} for r, v in verdicts.items() for i, rid in enumerate(run_ids)]
    analysis.reviews = pd.DataFrame(rows)
    cv = analysis.clinician_validation()
    assert cv["inter_rater"]["method"] == "fleiss" and cv["inter_rater"]["n_raters"] == 3
    table = [[3, 0, 0], [0, 0, 3], [2, 0, 1], [1, 2, 0]]
    assert cv["inter_rater"]["kappa"] == pytest.approx(round(fleiss_kappa(table), 3))
    assert cv["auto_vs_clinician"]["strict"]["n_items"] == 4 and cv["status"] == "ok"

    analysis.reviews = pd.DataFrame([r for r in rows if r["reviewer_id"] != "r3"])
    cv = analysis.clinician_validation()
    assert cv["inter_rater"]["method"] == "cohen" and cv["inter_rater"]["n_items"] == 4


def test_clinician_protocol_is_fixed_blinded_and_stratified(option_benchmark):
    db_path, cases_path = option_benchmark
    analysis = RigorousAnalysis(db_path, cases_path, reference_db_path=None)
    protocol = analysis.clinician_protocol(n=6, seed=42)
    assert protocol["n"] == 6 and protocol == analysis.clinician_protocol(n=6, seed=42)
    assert sum(protocol["strata"].values()) == 6
    assert all(set(item) == {"run_id", "case_id"} for item in protocol["items"])  # no variant, no label


def test_closed_loop_effect_counts_fixes_and_breaks(tmp_path):
    cases = [dict(MCQ, id=f"medqa_test_{i:04d}", case_id=f"medqa_test_{i:04d}") for i in range(8)]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases))
    db = BenchmarkDB(str(tmp_path / "bench.db"))
    pipeline = ClinicalGovernancePipeline(UnifiedLLMClient(provider="mock", force_mock=True))
    scorer = ClinicalEvaluationScorer()
    for i, case in enumerate(cases):
        # Open loop right on cases 0-1; closed loop right on 0-5 except 1: 4 fixed, 1 broken.
        for closed, right in ((False, i < 2), (True, i < 6 and i != 1)):
            result = pipeline.run(case, "full_governance", closed_loop=closed)
            result.raw_outputs["diagnosis"] = {"primary_diagnosis": "C" if right else "A", "differential_diagnoses": []}
            db.log_run(scorer.score_run(result, case))
    (row,) = RigorousAnalysis(str(tmp_path / "bench.db"), str(cases_path), reference_db_path=None).closed_loop_effect()
    assert row["comparison"] == "V5-CL - V5" and row["n_pairs"] == 8
    assert (row["fixed_by_revision"], row["broken_by_revision"]) == (4, 1)
    assert row["accuracy_open"] == 0.25 and row["accuracy_closed"] == 0.625
    assert row["mcnemar_exact_p_holm"] >= row["mcnemar_exact_p"]
    assert {"revised_runs_scored", "within_run_fixed", "within_run_broken"} <= set(row)


# ---------------------------------------------------------------- paper number checker
def test_paper_number_checker():
    tex = "\n".join([
        r"\documentclass{article}\setlength{\parskip}{2.5pt}",
        r"\begin{document}",
        r"Accuracy was 0.38 and 42.3\% of runs, in 2024 \cite{jin2021}.",  # 42.3% = 0.423 * 100
        r"Figure \includegraphics[width=0.48\linewidth]{f.png} \label{fig:1.2}",
        r"We used Llama-3.2-11B at $T=0.1$. % numcheck:ignore",
        r"% 9.99 in a comment",
        r"The rate was 7.77 per case.",
        r"\begin{thebibliography}{9} vol. 12.5 \end{thebibliography}",
        r"\end{document}",
    ])
    report = {"a": {"acc": 0.3801}, "b": [0.4234, "text 7.77"], "flag": True}
    assert [n for n, *_ in extract_numbers(r"Accuracy was 0.38 and 42.3\% in 2024")] == ["0.38", r"42.3\%"]
    unmatched = check(tex, report)
    assert [(line, shown) for line, shown, _ in unmatched] == [(7, "7.77")]
