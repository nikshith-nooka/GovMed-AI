# Metric Definitions

Definitions are taken from the code (`src/evaluation/scorer.py`, `src/analysis/rigor.py`). ↑ means higher is better,
↓ means lower is better. The **Evidence** column says whether the analysis uses the metric as a measurement.

## 1. Diagnostic quality

| Metric | Formula | Denominator / missing values | Dir. | Evidence |
|---|---|---|---|---|
| Accuracy (answer key) | 1 if the parsed option == key, else 0 | All runs with a valid gold label. Unparseable answers count as 0 and are reported separately | ↑ | **Yes** |
| Accuracy (free text) | 1.0 primary phrase match; 0.85 / 0.65 / 0.40 if gold is in the differential at rank ≤2 / ≤4 / lower; 0.70 if ≥50% of gold words (≥3 chars) are in the primary; else 0. "Correct" = score ≥ 0.8 | Valid-gold cases only. No label → 0 and excluded | ↑ | Yes (on 71 cases) |
| Differential completeness | 1.0 (≥3 entries), 0.75 (2), 0.5 (1), 0.2 (0) | — | ↑ | Component only |
| Detector-neutral quality | (0.4·acc + 0.2·completeness) / 0.6 | — | ↑ | Yes |
| Reported (rubric) quality | 0.4·acc + 0.2·completeness + 0.2·grounding + 0.2·safety, where grounding = max(0, 1−0.4·hallucinations) and safety = max(0, 1−0.35·alerts) | Variants without a detector get full grounding/safety credit | ↑ | **No**: penalises each variant's own detectors ("Audit Paradox") |

Precision, recall and F1 are not computed for diagnosis. In single-answer multiple choice they reduce to accuracy.

## 2. Reliability and safety

| Metric | Definition | Notes |
|---|---|---|
| Hallucination flag rate | mean(verifier `hallucination_detected`) over runs with a parseable verifier | Missing when the verifier output cannot be recovered (AUD-06) |
| Safety alerts per run | mean count of `safety_flags` | Fires on 100% of runs, so it has no discriminative value |
| Alert AUROC / sensitivity / FPR / precision | each signal as a detector of a wrong answer (accuracy < 0.5) | 0.5 = chance |
| HITL decision mix | counts of APPROVED / REQUEST_REVISION / REJECTED / PARSE_FAILURE | Simulated reviewer |
| Revision rate | share of closed-loop runs where `revision_applied` | |
| Within-run fixed / broken | revised runs whose first answer was wrong→right / right→wrong; exact two-sided sign test | Confound-free revision effect |
| Resampling stability | agreement of the chosen option, and correctness flips, between V1 and a regenerated first diagnosis | Run-to-run stability (one resample) |
| Diagnosis changed vs V1 | % of cases whose chosen option (answer key) or normalised text (free text) differs from V1 | Fixed in AUD-07 |
| Parse-failure rate | per agent, failed / present | |
| ECE / Brier | 10-bin ECE and Brier of the stated top-1 probability vs correctness (V1) | |
| Contradiction rate | share of consistency-checker `SEVERE_CONTRADICTION` (G4 only) | Stored in raw outputs, not summarised in the report |

## 3. Efficiency and cost

| Metric | Definition | Notes |
|---|---|---|
| Tokens per run | Σ (prompt + completion) over every step of the run, including the shared Research + Diagnosis steps once | Provider-reported usage. A chars/4 estimate is used only if the provider omits usage, and that is now logged |
| Model calls | number of `agent_steps` rows for the run | See EXPERIMENT_PROTOCOL §1 |
| Summed call latency (`e2e_latency_s`) | Σ step `latency_ms` | Parallel checks are summed, so this is an **upper bound** on wall clock. Per-call latency now excludes rate-limit back-off (AUD-03) |
| Wall-clock latency (`total_latency_ms`) | `run()` wall clock + cached upstream latency (runs after 2026-10-10) | Older rows omit the shared steps (V1 ≈ 0); do not use them |
| Governance latency | `raw_outputs.timing.governance_ms`: wall clock of checks, attending, revision and re-check | New runs only |
| Cost | tokens × an assumed price table (`UnifiedLLMClient.PRICING_TABLE`) | The NIM trial did not bill, so the cost is illustrative |
| Overhead of X | metric(X) − metric(V1), paired by case | Recomputed from raw data. No negative token overhead exists |
| HITL minutes | sampled N(2.5, 0.8) clipped to [0.5, 7] | **Simulated**: not evidence of human time |

## 4. Withdrawn and undefined metrics

`uncertainty_jru` (JRU), `risk_adjusted_quality`, `governance_efficiency_factor` (GEF), `llm_judge_score` and
`hitl_minutes`/`hitl_human_cost` are withdrawn. They were filled post hoc by `scripts/backfill_metrics.py` or derived from
the rubric. The analysis detects and excludes them (`integrity_audit`, `jru_measurement`). JRU counts only when a judge
model different from the generator scored the run, and none did.

The acronyms CSS, CMR, HIR, URR, CCS and GE from the audit brief appear nowhere in the code, paper or documentation.
No definition exists to validate them against, so none was invented.
