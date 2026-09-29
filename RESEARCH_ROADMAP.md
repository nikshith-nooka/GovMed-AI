# GovBench-Clinical: Audit Results and Road to Publication

Generated from `results/rigor_report.json` (run `uv run python -m scripts.run_rigor_analysis` to refresh).
All numbers below are measured from the 750 stored runs (150 cases x 5 variants, Llama-3.2-11B on NVIDIA NIM).

## 1. What the audit found

| Issue | Evidence | Consequence |
|---|---|---|
| Post-hoc metrics | `uncertainty_jru`, `llm_judge_score`, `risk_adjusted_quality`, `governance_efficiency_factor`, `hitl_minutes` are empty in `results/benchmark_results.db.bak` and were written by `scripts/backfill_metrics.py` from hard-coded per-variant multipliers. `llm_judge_score = quality - 0.05*JRU` in >95% of rows. | JRU, Q_adj, GEF and the "LLM-as-judge" claim cannot be reported. |
| Substring scoring | 216 runs with an unparsed (empty) diagnosis scored 1.0; 395 runs whose diagnosis is a bare letter ("A") scored 0.90, because `""` and `"a"` are substrings of the gold text; wrong answers also received a 0.15 floor. | Accuracy is **0.293**, not the reported 0.739. |
| JSON parse failures | Diagnosis 29%, research 15%, verifier 25%, safety 9% of outputs failed strict JSON (literal newlines in strings). All but 25 research outputs are recoverable. | Governance flags were silently lost on failed parses. |
| Invalid gold labels | 79/150 gold labels are templated titles ("Clinical Diagnostic Note for ..."); MedQA questions were rewritten without their options. | Only 71 cases are scorable (accuracy 0.38 on them). |
| Open-loop governance | Primary diagnosis differs from V1 in at most 2.7% of cases; HITL asked for revision in 125/150 V5 runs, yet nothing is revised. | Governance cannot improve accuracy by design. No accuracy difference vs V1 (paired Wilcoxon p >= 0.18). |
| Audit Paradox is an artifact | 95-97% of each governed variant's quality drop comes from the rubric penalizing that variant's own detectors (V1 has none to be penalized by). | The paradox measures the scorer, not safety. |
| Alerts do not discriminate | Safety validator alerts on 100% of runs. As detectors of misdiagnosis, every signal has AUROC 0.40-0.56 (0.5 = chance). Same validator on the same cached diagnosis (V4 vs V5) gives identical alert counts in only 72.7% of cases. | "283 contraindications intercepted" counts LLM output, not validated hazards. |
| Calibration | Model-reported diagnosis probability: ECE 0.29, Brier 0.33. | Must never be shown to clinicians as "confidence". |
| Latency | Reported latency excludes the shared research and diagnosis steps. True end-to-end p50/p95: V1 45/112 s, V5 111/256 s. Report Agent is the bottleneck (mean 29 s, max 539 s). | Paper latency numbers are ~35% too low. |
| Silent substitution | On missing keys or exhausted retries the LLM client returned mock output as if it were live; the API returned a canned answer (e.g. "Acute Coronary Syndrome", 96.5%) on any failure. | No stored runs were affected (0 mock markers), but the UI could mislead clinicians. |

## 2. What changed in the code

- `src/agents/base.py`: lenient JSON extraction (`strict=False`, embedded-object scan).
- `src/evaluation/scorer.py`: whole-word matching, empty/letter-only predictions score 0, wrong answers score 0 (not 0.15), templated gold labels flagged, `detector_neutral_quality`, JRU is true judge/rubric disagreement when a judge runs (`jru_source` records which).
- `src/pipeline/orchestrator.py` + `DiagnosisAgent.revise`: **closed-loop governance** (`closed_loop=True`, variant ids `-CL`). Verifier hallucinations, HIGH/CRITICAL safety flags, severe inconsistencies and HITL revision requests send the diagnosis back for one revision.
- `src/llm/client.py`: `allow_mock_fallback=False` raises `LiveInferenceUnavailable` instead of simulating; demo generator no longer defaults unknown cases to ACS; HTTP 429 now waits for the quota window instead of burning all retries (Groq free tier: 8k tokens/min per key).
- `src/analysis/rigor.py`, `scripts/run_rigor_analysis.py`: measured re-analysis with paired bootstrap CIs, Wilcoxon signed-rank, AUROC, calibration, per-agent latency, strata, failure taxonomy, integrity audit, clinician-validation stats. Tables in `paper/tables/rigor_*`.
- `src/clinical/decision_support.py`, `src/api/server.py`: real pipeline for demo and live; explicit 502 on live failure; input validation; blinded clinician review endpoints; path-traversal fix; no invented stats.
- UI: every page now reads measured data (Dashboard, Benchmark Analytics, Agent Pipeline, Reports were hardcoded); Experiments runs real cases and saves to `results/ui_experiments.db`; navbar search/⌘K/review bell work. **Clinician Workspace** (physician view + clinical-assistant view with SBAR handoff and escalation list), **Clinician Review** (blinded rating tool), **Research Findings**; Case Runner no longer shows fabricated guidelines, rules, confidence or "attending sign-off".
- `scripts/backfill_metrics.py` refuses to run without `--allow-synthetic`. `scripts/run_full_benchmark.py` gains `--closed-loop`, `--variant-workers`, strict live mode.
- Tests: 21 -> 55 (`tests/test_integrity.py`). `scripts/load_test.py`: 200 concurrent runs, 0 failures.

## 3. A publishable framing

The defensible contribution is not "governance costs X% more". It is a **measurement audit**:

> *When clinical AI governance is open-loop and evaluated with lenient automatic scoring, apparent safety and quality effects are artifacts of the evaluation.* We quantify five failure modes (post-hoc metrics, substring scoring, parse loss, templated labels, self-penalizing rubrics), show that LLM safety validators alert indiscriminately (AUROC ~ chance), and test closed-loop revision plus a clinician-validation protocol as the fix.

Realistic venues: JAMIA / JAMIA Open, npj Digital Medicine, ML4H or CHIL (workshop or findings track). Negative and methodological results are publishable there if the evidence is clean.

## 4. What still has to be done (needs API credits or people)

1. **Objective benchmark.** Rebuild cases from the original MedQA-USMLE (4 options + answer key; `ClinicalDatasetLoader.load_medqa` already reads `GBaker/MedQA-USMLE-4-options`). Target >= 300 cases so 5-point accuracy differences are detectable. Drop PubMedQA/MedDialog from accuracy, or score PubMedQA on yes/no/maybe.
2. **Main experiment:** open vs closed loop on the same cases, into a fresh DB:
   ```
   uv run python -m scripts.run_full_benchmark --total-cases 300 --provider nvidia --db-path results/v2.db --variant-workers 1
   uv run python -m scripts.run_full_benchmark --total-cases 300 --provider nvidia --db-path results/v2.db --variant-workers 1 --closed-loop
   uv run python -m scripts.run_rigor_analysis --db-path results/v2.db --reference-db none
   ```
   The runner now calls the real LLM judge, so JRU is measured.
3. **Second model** (e.g. Llama-3.3-70B on Groq) to test whether findings generalize.
4. **Clinician validation:** 3 reviewers x the same 50 outputs in *Clinician Review*. This yields alert precision, scorer-vs-clinician kappa, and inter-rater agreement.
5. **Paper corrections.** Remove or rewrite `paper/main.tex` lines 91, 163, 195-202, 236-240, 344-349 and 359 (JRU/Q_adj/GEF values, LLM-judge claim, "283 contraindications missed", "complete interception", p < 0.001), and the README "Key Findings" table. Replace them with `paper/tables/rigor_*.tex`.
6. **Latency:** make the Report Agent optional or shorter (largest share of every run); report contention-free latency (`--variant-workers 1`).
7. Decide what to do with the synthetic columns in `results/benchmark_results.db` (the untouched original is `results/benchmark_results.db.bak`).
