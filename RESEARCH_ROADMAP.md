# GovBench-Clinical: Audit Results and Road to Publication

All numbers come from `results/rigor_report.json` (regenerate with `uv run govbench-rigor`): 750 stored runs,
150 cases x 5 variants, Llama-3.2-11B on NVIDIA NIM, open-loop governance.

## 1. What the audit found

| Issue | Evidence | Consequence |
|---|---|---|
| Post-hoc metrics | Six columns (`uncertainty_jru`, `llm_judge_score`, `rubric_quality_score`, `risk_adjusted_quality`, `governance_efficiency_factor`, `hitl_minutes`) are empty in `results/benchmark_results.db.bak` and were filled by `scripts/backfill_metrics.py`. | JRU, Q_adj, GEF and the LLM-judge claim are withdrawn. |
| Substring scoring | 216 empty diagnoses scored 1.0; 395 bare option letters scored 0.9; wrong answers received a 0.15 floor. | Accuracy is 0.293, not 0.739 (0.38 on the 71 scorable cases). |
| Invalid gold labels | 79 of 150 gold labels are templated titles; none of the 150 cases kept its answer options. | Only 71 cases are scorable. |
| Open-loop governance | The primary diagnosis differs from V1 in at most 2.7% of cases. | No accuracy difference (Wilcoxon p >= 0.18; exact McNemar 1.0 after Holm). |
| Audit Paradox | 94-96% of each governed variant's quality drop comes from penalising its own detectors. | The paradox measures the scorer, not safety. |
| Alerts | The safety validator alerts on every run; every signal has AUROC 0.40-0.56. | Alert counts are not evidence of safety. |
| Calibration | ECE 0.2873, Brier 0.3254. | Likelihoods are shown as a ranking, never a probability. |
| Power | 1-2 discordant cases of 71; a 5-point difference needs 312-940 pairs. | A larger benchmark with an answer key is required. |

## 2. Status of the review plan

| Item | Status |
|---|---|
| References verified against arXiv / DOI; fabricated entries removed | Done (`paper/main.tex`, 25 verified references) |
| JRU / Q_adj / GEF, p < 0.001, HIPAA and on-premise claims removed | Done |
| Paper rewritten from measured numbers; all 4 authors | Done; `scripts/check_paper_numbers.py` matches every number |
| 300-question MedQA benchmark with options and answer key | Done (`benchmarks/medqa_300.json`) |
| Exact option scoring, McNemar, Holm, effect sizes, power | Done (`src/evaluation/scorer.py`, `src/analysis/rigor.py`) |
| Cross-model judge, seed and per-step temperature recorded, resumable runs, cost estimate | Done (`scripts/run_full_benchmark.py`) |
| Closed loop re-checks the revised diagnosis | Done |
| Prompt-injection fencing and test set, API token, PHI blocking, retention, persistent jobs, rate-limit status | Done |
| Deterministic contraindication rules | Done (`src/clinical/rules.py`, 14 rules) |
| Fixed 50-item clinician protocol, Fleiss' kappa | Done (`benchmarks/clinician_protocol_50.json`, served first in the review queue) |
| **Main experiment:** MedQA 300, open vs closed loop | **Running** (started 2026-09-29, `results/medqa_v2.db`, log `results/medqa_v2.log`) on NVIDIA (about 2,700 runs, ~30M tokens, ~19 h; use `--dry-run` for a fresh estimate) |
| **Second model** | **To run** (Groq GPT-OSS-120B). The Groq free tier allows 200k tokens per day per account, shared by all keys: the full design needs ~148 days there, so use a paid Groq tier (~$5 of tokens) or a reduced design |
| **Clinician ratings** (3 reviewers x the same 50 outputs) | **To collect** in *Clinician Review* |
| Live prompt-injection evaluation | Done (12 attacks, Llama-3.2-11B, G4). Before fixes: 1 leak, 1 suppressed AI alert. After fixes: 0 leaks; the AI safety validator can still be talked out of an alert (1/12), but the rule alert fired in 12/12 and the injection warning in 12/12. Results: `results/injection_eval_nvidia_g4{_before,}.json` |

## 3. Commands for the remaining experiments

```bash
# Main experiment: NVIDIA generator, judged by a different model on NVIDIA NIM
uv run govbench --benchmark benchmarks/medqa_300.json --provider nvidia --judge-provider nvidia \
    --judge-model nvidia/nemotron-3-super-120b-a12b --loop-modes open,closed --seed 42 --db-path results/medqa_v2.db
# Second model (needs a paid Groq tier for the full design; check with --dry-run first)
uv run govbench --benchmark benchmarks/medqa_300.json --provider groq --judge-provider nvidia \
    --loop-modes open,closed --seed 42 --db-path results/medqa_v2.db --dry-run
uv run python -m scripts.run_rigor_analysis --db-path results/medqa_v2.db --cases-path benchmarks/medqa_300.json \
    --reference-db none --out results/rigor_report_medqa.json --tables-dir paper/tables/medqa --clinician-protocol ""
```

After the runs, update the paper's results from the new report and rerun `scripts/check_paper_numbers.py`.

## 4. Target venues

- IEEE ICHI (International Conference on Healthcare Informatics): measurement and evaluation work fits the scope.
- IEEE BHI (Biomedical and Health Informatics): the clinician-facing workbench and safety layer fit here.
- ML4H (Machine Learning for Health) findings track: negative and methodological results are accepted.
- IEEE JBHI short paper, once the MedQA and second-model runs and the clinician ratings are in.

The current manuscript is suitable as a workshop or findings submission. A full conference paper needs the three
experiments marked "To run / To collect" above.
