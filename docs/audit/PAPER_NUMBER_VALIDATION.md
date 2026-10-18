# Paper Number Validation — NCRTHT 2026 version

Date: 2026-10-18 · Branch: `paper/final-refinement` (from `analysis/holm-scope-wording` @ `8f7fb2f`)
Source: `paper/main_ncrtht2026.tex` · Raw data: `results/medqa_paired.db` (paired study), `results/medqa_fast.db`
(earlier unpaired pass), `results/benchmark_results.db` (earlier 150-case evaluation).

## 1. Automated checks

| Command | Result |
|---|---|
| `uv run python -m scripts.check_paper_numbers --tex paper/main_ncrtht2026.tex --report results/rigor_report_medqa_paired.json,results/rigor_report_medqa.json,results/rigor_report.json` | **96/96** decimals and percentages matched |
| same, with `--integers` | **137/138**; the one unmatched value is `1,273`, the MedQA test-split size, which `benchmarks/medqa_300.meta.json` backs (`"split_size": 1273`) |
| `uv run python -m scripts.check_paper_numbers --tex paper/main.tex --report …` (long version, unchanged) | 169/169 |

The checker does not cover the lines marked `% numcheck:ignore`. They hold decoding settings (temperature 0.1/0.2,
1,500 max tokens) and the assumed token rates ($0.10/$0.20 per M). Section 3 below verifies each of them by hand.

## 2. Independent recomputation from the raw paired database

These values were recomputed with SQL and Python directly on `results/medqa_paired.db`, not through the analysis
code.

| Quantity | Raw DB | Paper | Match |
|---|---|---|---|
| Runs / distinct questions per configuration | 300 / 300 for each of 6 configurations (1,800) | 300, 1,800 | ✓ |
| Duplicate (case, configuration) rows | 0 | — | ✓ |
| Correct answers G0 / G4 open / G1 / G2 / G3 / G4 closed | 129 / 129 / 120 / 134 / 121 / 112 of 300 | 43.0 / 43.0 / 40.0 / 44.7 / 40.3 / 37.3 % | ✓ |
| No-option answers (empty + unparseable) | 7 + 7 + 11 + 9 + 5 + 13 = 52 | 52 of 1,800 | ✓ |
| Revisions applied (G1 / G2 / G3 / G4 closed) | 109 / 104 / 94 / 238 (= 36.3 / 34.7 / 31.3 / 79.3 %) | Table I "Revised" | ✓ |
| Revisions triggered but not applied (failed revision parse) | 0 in every configuration | "none occurred" | ✓ |
| Pairing: closed-loop first answer = G0 answer | 300/300 for each of G1–G4 closed and G4 open | "verified for all 1,200" | ✓ |
| Mean tokens per question | 2200.9 / 7570.4 / 4817.8 / 4153.2 / 4479.2 / 11362.7 | Table I | ✓ |
| Median summed agent-step latency (s) | 21.2 / 60.7 / 52.8 / 41.8 / 43.5 / 142.5 | Table I | ✓ |
| Safety validator ≥1 alert | 300/300 in G3 closed, G4 open and G4 closed | "every run of each configuration that included it" | ✓ |
| Model / provider | `meta/llama-3.2-11b-vision-instruct` / `nvidia` on every run and step | ✓ | ✓ |
| Temperatures (from `agent_steps`) | 0.1 research, verifier, safety, consistency (and re-checks); 0.2 diagnosis, revision, attending | "0.1 for extraction and checks, 0.2 for diagnosis, revision and review" | ✓ (text was made more specific) |
| Report agent | no Report Agent steps in the DB (report stage disabled) | not claimed | ✓ |
| Run dates | G0/G4 open 2026-10-06; closed loop 2026-10-11 and 2026-10-18 | "closed-loop runs were made on other days" | ✓ |

## 3. Cost per question

`total_cost_usd` is computed in `src/llm/client.py` (`PRICING_TABLE`, line 53) as
`prompt_tokens × $0.10/M + completion_tokens × $0.20/M` for `meta/llama-3.2-11b-vision-instruct`.

- G0: (457,479 × 0.10 + 202,806 × 0.20) / 10⁶ = $0.086319 for 300 questions, or **$0.000288** per question ✓
- G4 closed: $0.422469 / 300 = **$0.001408** ✓

**Caveat.** The rate is a constant hard-coded in the repository. No source, provider price page or date is recorded,
and the NVIDIA NIM API calls may not have been billed at this rate. The paper now states the rate and calls it an
illustrative assumption, not a quoted price (see author question Q1).

## 4. Statistics

| Result | Value | Family / denominator | Paper wording |
|---|---|---|---|
| G4 closed vs G4 open (= vs G0, since the answers are identical) accuracy difference | −5.67 points, bootstrap 95% CI −10.67 to −0.67 | 300 pairs | −5.7 (−10.7 to −0.7) ✓ |
| Exact McNemar p (unadjusted) | 0.039617 | discordant pairs 22 vs 39 | "p = 0.040 unadjusted" ✓ |
| Holm, closed-vs-open family | 0.039617 | **1 test**, so equal to the raw p | not quoted (it would read as "significant after correction") |
| Holm, full family | **0.554638** | **30 tests**: every paired Wilcoxon (quality metric × configuration vs G0) plus the 5 exact McNemar accuracy tests | "p = 0.55 after Holm correction across the 30 paired tests" ✓ (added) |
| Revision sign test, G4 closed | p = 0.02734 (21 fixed vs 39 broken) | unadjusted | "p = 0.027, unadjusted" ✓ |
| Holm across the 4 closed-loop sign tests | G4 closed 0.02734 × 4 = 0.109; G3 0.488; G1 0.399; G2 0.383 | 4 tests | "not significant after Holm correction across the four sign tests" ✓ (added) |
| G2 closed sign test | 0.38331 (13 vs 8) | unadjusted | "sign test p = 0.38" ✓ (test now named) |
| Minimum detectable difference | 0.0579 at the mean discordance 0.1292, α 0.05, power 0.8 (pooled) | per comparison it ranges 0.0426–0.0726 | "12.9% … 5.8 points" ✓ (the definition was previously missing) |
| AUROC range | 0.497–0.570 (G4 closed: 0.533–0.562) | 300 runs per row | ✓ |
| ECE / Brier | 0.2374 / 0.3021 (n = 297 stated confidences) | baseline | ✓ |

### Revision denominators (Table I "Fix/break")

For G4 closed, 238 runs were revised. Of these, 235 have a non-empty first answer and can be scored before and after
revision (`rigor._within_run_revision`). The other three had an empty first answer.

- 21 went wrong → right, 39 went right → wrong, and the remaining 175 kept their correctness (wrong → wrong or right
  → right; this split was not broken down further).
- A first answer that was unparseable but non-empty counts as wrong, because it maps to no option.
- McNemar's discordant count (22 closed-only-correct) is one higher than the within-run "fixed" count (21). One revised
  run had an empty first answer, so it is excluded from the within-run count but included in the paired comparison.

## 5. Earlier evaluations quoted in the paper

| Quantity | Source | Value | ✓ |
|---|---|---|---|
| Regenerated first answer agreed with G0 | `rigor_report_medqa.json` → `resampling_stability` | 0.7952 (G1–G3 closed, n = 293 scorable pairs), 0.7458 (G4 closed, n = 299) | 79.5 %, 74.6 % ✓ |
| Unpaired G2 closed / G4 closed accuracy | `rigor_report_medqa.json` | 0.4633 / 0.43 | 46.3 %, 43.0 % ✓ |
| 150-case audit (Table III) | `rigor_report.json` | 0.739 / 0.293 / 0.783 / 0.38 / 216 / 395 / 79 | ✓ |

## 6. Superseded runs

`medqa_paired.db` holds 1,800 rows with ids up to 3,000. The 1,200 missing ids are the unpaired `-CL` rows. They were
deleted from this copy before the paired rerun, as documented in `docs/REPRODUCIBILITY.md` and
`docs/EXPERIMENT_PROTOCOL.md`. The originals are kept unchanged in `results/medqa_fast.db`, which the paper uses only
for the "unpaired shortcut" paragraph.

## 7. Data integrity

MD5 checksums of all nine `results/*.db` files are identical before and after this work. No database, analysis code or
rigor report was modified.
