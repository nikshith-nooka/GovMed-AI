# Experiment Protocol

**Research question.** For a fixed clinical multi-agent pipeline, what is the marginal quality and reliability benefit
of each governance layer, and what token, compute, latency and (simulated) human-review overhead does it add?

This is a benchmark and simulation study. It is not a medical device, and it makes no claim of clinical safety.

## 1. Pipeline and governance levels (as executed)

The executed definition is `ClinicalGovernancePipeline.AVAILABLE_VARIANTS` and `run()` in
`src/pipeline/orchestrator.py`. Every agent uses the same model. Temperatures: Research, Verifier, Safety and
Consistency 0.1; Diagnosis, HITL and Report 0.2. At most 1,500 output tokens per call.

| Level | Id | Checks after Diagnosis | LLM calls per run (open loop, report off) | Closed-loop re-check after a revision |
|---|---|---|---|---|
| G0 | V1 | none | 2 (Research, Diagnosis) | — (no closed-loop form) |
| G1 | V2 | Grounding verifier | 3 | verifier |
| G2 | V3 | Simulated attending (LLM, **not a human**) | 3 | none |
| G3 | V4 | Safety validator | 3 | safety validator |
| G4 | V5 | Consistency + verifier + safety (parallel), then attending (reads the safety output) | 6 | verifier + safety |

- The Report agent adds 1 call when enabled (`--no-report` was used for MedQA).
- Closed loop adds 1 Diagnosis-revision call when any trigger fires, plus the re-check calls listed above.
- The 14 deterministic rules (`src/clinical/rules.py`) run on every level with no LLM call.
- **G0–G4 are not a strict hierarchy.** G1, G2 and G3 are alternative single mechanisms. G4 combines all of them and adds the
  consistency checker, which appears at no other level. Marginal effects are therefore "single check vs none" and
  "all checks vs none", not "G(n+1) vs G(n)".

**Revision triggers** (`revision_triggers`): consistency `SEVERE_CONTRADICTION`; verifier `hallucination_detected`
or `CRITICAL_HALLUCINATION`; any safety flag with severity HIGH or CRITICAL; attending `REQUEST_REVISION` or
`REJECTED`. **Bound:** exactly one revision round, with no loop. If the revision cannot be parsed, the original diagnosis is
kept and `revision` is added to `parse_failures`.

**No abstention mechanism exists.** No agent may decline to answer.

## 2. Data

- **MedQA-USMLE 4-option test split** (Jin et al., 2021; HF `GBaker/MedQA-USMLE-4-options`, 1,273 items).
  300 sampled with `random.Random(42).sample(range(1273), 300)`, indices recorded in
  `benchmarks/medqa_300.meta.json`. Original options and answer key are kept. Checks: 300 unique IDs, 300 unique
  questions, answer key consistent with the option text for 300/300, no answer cue in the question text.
  Licence: confirm the licence of the original MedQA release and of the HF mirror before redistributing
  `medqa_300.json`. This audit did not verify it.
- **curated_sample.json** (150 cases: MedQA, PubMedQA, MedDialog). 79 of its gold labels are templated titles and are
  excluded from accuracy (`gold_label_valid`). No options were kept.
- No real patient data is used or required. Synthetic cases appear only in tests.

## 3. Ground-truth isolation

Only `ClinicalEvaluationScorer` and `RigorousAnalysis` read `gold_diagnosis`, `answer`, `answer_idx` and `answer_text`.
Agents receive `question`/`clinical_note` and `options`. The API strips the label fields before running an
experiment case. Enforced by `tests/test_audit_fixes.py::test_ground_truth_never_reaches_any_agent`.

## 4. Scoring policy (predeclared)

- **Answer-key cases:** score 1 iff the answer maps to exactly the key option (`parse_option_choice`). Otherwise 0.
  This includes empty, unparseable and ambiguous answers, which are also `flagged` and counted separately. There is no partial credit.
- **Free-text cases:** whole-word phrase matching with rank credit (METRIC_DEFINITIONS §1). A run counts as correct at
  a score ≥ 0.8.
- **Missing gold label:** no credit, and the case is excluded (`gold_label_valid = False`).

## 5. Pairing and the closed-loop confound (AUD-01)

Every variant of a case is meant to share one Research + Diagnosis output, so that differences come only from
governance. In the stored MedQA experiment the closed-loop pass regenerated them. As a result:

| Comparison | Valid? |
|---|---|
| V5 vs V1 (open) | Yes: identical diagnosis by construction |
| X-CL first diagnosis vs X-CL final (`within_run_*`, sign test) | **Yes: the confound-free revision effect** |
| X-CL vs V1, V5-CL vs V5 (McNemar) | Confounded: includes resampling noise |

The size of that noise is measured from the same data (`resampling_stability`). The regenerated first diagnosis
agreed with V1's option in 78.8% (V2–V4-CL, n = 293) and 73.6% (V5-CL, n = 299) of cases. Correctness flipped in 41 and
48 cases, and accuracy moved by +1.0 and −1.3 points, from resampling alone (McNemar p = 0.76 and 0.67).

Within-run revision outcomes (MedQA, Llama-3.2-11B; exploratory):

| Variant | Revision rate | Fixed | Broken | Sign test p |
|---|---|---|---|---|
| V2-CL verifier | 35.7% | 15 | 15 | 1.0 |
| V3-CL attending | 33.0% | 14 | 6 | 0.115 |
| V4-CL safety | 31.3% | 11 | 16 | 0.442 |
| V5-CL all | 78.0% | 36 | 33 | 0.810 |

The runner now reuses stored upstream outputs (`load_shared_upstream`), so a rerun of the closed-loop pass into the
same database removes the confound.

## 6. Statistics

Paired bootstrap 95% CIs, Wilcoxon signed-rank, and exact McNemar on binary correctness vs V1. Holm–Bonferroni is applied over the
whole family of paired tests. Connor (1987) power for paired McNemar. AUROC of each governance signal as a detector of
a wrong answer. ECE and Brier for the stated top-1 probability. All of these are computed by `src/analysis/rigor.py`
from raw stored outputs.

**Confirmatory vs exploratory.** Neither the 750-run open-loop study nor the MedQA design was pre-registered, so every
result should be read as exploratory. The within-run revision analysis was added after the data were seen (commit
`7c98407`), and the resampling-stability analysis was added in this audit.

## 7. Known deviations from the brief

- No 50-case / Llama 3.1 8B pilot exists. The stored experiments are listed in PROJECT_AUDIT §2.
- Per-claim verification categories (SUPPORTED / UNSUPPORTED / CONTRADICTED / UNVERIFIABLE) are not implemented (AUD-20).
- Human review is simulated, and its minutes are sampled from an assumed distribution, not measured.
- Each case was run once per configuration, with no repeated runs. The resampling comparison above is the only stability
  evidence.
