# Project Audit — GovBench-Clinical

Audit date: 2026-10-10. Baseline: `main` at `76c3b92`, clean working tree. The raw run databases were not modified:
their MD5 hashes were checked before and after the audit.

## 1. What the repository contains

| Layer | Location | Notes |
|---|---|---|
| Agents | `src/agents/` | Research (extraction, no literature retrieval), Diagnosis (+ `revise`), Verifier, Safety Validator, HITL Simulator, Consistency Checker, Report (SOAP) |
| Governance engine | `src/pipeline/orchestrator.py` | `AVAILABLE_VARIANTS` is the executed definition of V1–V5 (= G0–G4). Closed loop allows one bounded revision. Deterministic rules run on every variant |
| Deterministic safety | `src/clinical/rules.py` | 14 contraindication rules, no LLM |
| LLM client | `src/llm/client.py` | Groq / NVIDIA NIM / Gemini / OpenRouter, plus a labelled offline demo generator |
| Evaluation | `src/evaluation/scorer.py`, `statistics.py`, `llm_judge.py` | Exact option scoring for answer-key cases; free-text matching otherwise |
| Analysis | `src/analysis/rigor.py` | Re-scores every run from raw output; paired statistics, Holm, power, AUROC, calibration |
| Storage | `src/telemetry/db.py`, `jobs.py` | SQLite `runs`, `agent_steps`, `clinician_reviews`; persistent jobs |
| Runner | `scripts/run_full_benchmark.py` (`govbench`) | Strict live runs, resume, dry-run cost estimate |
| API + UI | `src/api/server.py`, `client/` (React + Vite, JS) | The API serves the built client |
| Data | `benchmarks/medqa_300.json` (+ `.meta.json`), `benchmarks/curated_sample.json` (150 mixed cases) | |
| Results | `results/*.db`, `results/rigor_report*.json` | See §2 |
| Paper | `paper/main.tex`, `paper/tables/`, `paper/figures/` | `scripts/check_paper_numbers.py` checks that every number in the paper appears in a report |

### Execution path (benchmark)
`govbench` → `ClinicalDatasetLoader.load_benchmark_file` → per case, the shared Research + Diagnosis run once
→ `ClinicalGovernancePipeline.run(variant, cached_research, cached_diagnosis, closed_loop)` → parallel checks
→ HITL → optional revision + re-check → rules → optional Report → `ClinicalEvaluationScorer.score_run`
(the only reader of the gold label) → `BenchmarkDB.log_run` → `RigorousAnalysis` → JSON report, LaTeX tables and
figures → `/api/research/findings` → dashboard.

## 2. Mapping of the "known experiment problems" in the brief

The brief describes a pilot of about 50 MedQA cases × 5 levels = 250 runs on **Llama 3.1 8B**. **No such pilot exists in
the repository.** The stored experiments are:

| Database | Model | Runs |
|---|---|---|
| `results/benchmark_results.db` | Llama-3.2-11B (NIM) | 751 open-loop, 150 mixed cases |
| `results/medqa_fast.db` | Llama-3.2-11B (NIM) | 1,800: 300 MedQA × {V1, V5, V2-CL, V3-CL, V4-CL, V5-CL} |
| `results/benchmark_results_20b_backup.db` | gpt-oss-20b / 120b | 785, incomplete |
| `results/pilot_medqa.db` | gpt-oss-120b | 15 |
| `seed_*`, `seeded_*`, `validation_judge.db` | offline demo generator | test fixtures, not evidence |

Each symptom was investigated against the data that does exist:

| # | Symptom | Finding |
|---|---|---|
| 1 | Cross mark on many runs | The UI has no cross glyph. A wrong answer is shown as score `0.00`. Parse failures and unparseable option answers also score 0, so they look the same as a wrong answer (AUD-09). In MedQA, 56/1,800 runs are unparseable or empty answers, and they are scored as wrong under a consistent policy. |
| 2 | Latency `0.0s` | **Reproduced.** In `medqa_fast.db`, V1 `total_latency_ms` has a mean of 3 ms (min 1 ms). Cause: AUD-02. |
| 3 | G0–G2 similar quality | This is genuine behaviour, not a bug. Open-loop variants reuse V1's diagnosis, so accuracy is identical by construction. Closed-loop revisions change answers, but fixes and breaks roughly cancel out (EXPERIMENT_PROTOCOL §5). The *rubric* quality differences are the known detector-penalty artefact ("Audit Paradox"). |
| 4 | "Abstentions" at G3–G4 | **The pipeline has no abstention mechanism.** What looks like abstention is an answer that maps to no single option (`unparseable` 42, `empty` 13, `ambiguous` 1). The predeclared policy scores these as incorrect (score 0, `flagged`). |
| 5 | Token totals vary by level | Legitimate. Each level makes a different number of calls (METRIC_DEFINITIONS §3). Per-run totals include the shared Research + Diagnosis steps once. |
| 6 | Negative overhead | Recomputed from raw data. No variant uses fewer tokens than V1. A negative *latency* overhead can only come from the AUD-02 mismatch: V1's stored wall clock was ~0 and the other variants' stored wall clocks were not comparable to it. The analysis uses summed per-step latency, so the overheads it reports are non-negative. |

## 3. Findings

Severity: **C** = invalidates a reported comparison, **H** = wrong measurement or misleading output,
**M** = robustness or presentation, **L** = hygiene.

| ID | Sev | Location | Evidence and root cause | Status |
|---|---|---|---|---|
| AUD-01 | **C** | `scripts/run_full_benchmark.py` `process_case` | The closed-loop pass re-ran Research + Diagnosis instead of reusing V1's. In `medqa_fast.db`, 97/300 (V2–V4-CL) and 101/300 (V5-CL) first diagnoses differ textually from V1. By chosen option, 60/293 and 76/299 differ. So "V*-CL vs V1" McNemar tests mix revision with resampling. `rigor.closed_loop_effect` labelled the between-pass discordance `fixed_by_revision/broken_by_revision` (42/42), while the true within-run figure is 36/33. | **Fixed** going forward (the runner reuses stored upstream). Analysis relabelled, and the resampling noise is now quantified. **Resolved by the paired rerun** (2026-10-18, `results/medqa_paired.db`): all 1,200 closed-loop runs start from V1's diagnosis. |
| AUD-02 | **H** | `orchestrator.run` | `total_latency_ms` measured wall clock only inside `run()`. Cached Research/Diagnosis time was excluded, so V1 ≈ 0 ms. Token totals did include those steps, so the two measures were inconsistent. | **Fixed**. Cached step latency is now added, and `raw_outputs.timing` separates `upstream_cached_ms`, `governance_ms` and `report_ms`. |
| AUD-03 | **H** | `src/llm/client.py` `generate` | The timer started before the retry loop, so call latency included 429 back-off sleeps and failed attempts. | **Fixed**: timed per attempt with `perf_counter`. |
| AUD-04 | **H** | `orchestrator` consistency block | An unparseable consistency output was logged as "Consistency Check Passed (CONSISTENT, score 1.0)". | **Fixed**: logged as FAILED. |
| AUD-05 | **H** | `hitl_simulator.py`, `orchestrator` | An unparseable HITL output defaulted to `decision="APPROVED"`, so a failed gate was recorded as success. No stored MedQA run was affected (0 HITL parse failures). | **Fixed**: `PARSE_FAILURE`. |
| AUD-06 | **H** | `rigor._rescore_row` | An unrecoverable verifier/safety/HITL output was counted as "no hallucination", "0 alerts" or "" instead of missing. | **Fixed**: `None`, which is excluded from rates and AUROC. |
| AUD-07 | **H** | `rigor.variant_summary` | `diagnosis_changed_vs_v1_pct` compared raw text, so rewording the same option counted as a change. V2-CL showed 43.3%. | **Fixed**: compares the chosen option for answer-key cases. V2-CL is now 30.0%. |
| AUD-08 | M | `rigor` latency label, paper, README | "Median end-to-end latency" is actually the *sum* of agent-call latencies. Parallel checks are counted serially, so it is an upper bound on wall clock. | **Fixed** wording in the report, paper and README. Keys are unchanged so the UI still works. |
| AUD-09 | M | `server.py` experiment and history endpoints; `Experiments.jsx` | `scoring_mode`, `option_parse_status` and `flagged` are dropped, so the UI cannot distinguish "wrong" from "unparsed". | **Open** (presentation only; the analysis distinguishes them). |
| AUD-10 | M | `scorer.evaluate_diagnostic_match` | A missing gold label returned **0.8 credit**. | **Fixed**: 0.0. Such runs are already `gold_label_valid=False` and excluded. |
| AUD-11 | M | `rigor.report` limitations | Hardcoded limitation text was wrong for MedQA ("lenient string matching") and omitted that HITL is simulated. | **Fixed**: the text is now generated from the data. |
| AUD-12 | M | `rigor` headline | "Open-loop changed the diagnosis in 0.0%" was presented as a finding, but it holds by construction. | **Fixed**: the text now says so. |
| AUD-13 | H | `server.py` `on_step`/`on_event` | Parallel checks mutate `job["steps"]` while `_persist` serialises it outside the lock, which can raise `RuntimeError: dictionary changed size`. | **Fixed**: the job is snapshotted under the lock. |
| AUD-14 | M | `server.py /api/runs` | `variant=V1` also returned `V1-CL` rows, mixing two configurations. | **Fixed**: exact match. |
| AUD-15 | M | `server.py` SPA catch-all | Unknown `/api/*` paths returned `index.html` with status 200. | **Fixed**: 404. |
| AUD-16 | L | `server.py run_experiment_case` | The full case, including the gold label, was passed to the pipeline. Agents ignore it, so isolation rested on convention. | **Fixed**: labels are stripped first. A test asserts that no prompt contains the gold label. |
| AUD-17 | M | `client/vite.config.js` | The dev proxy was hardcoded to port 8001, but the README documents 8000. | **Fixed**: default 8000, `GOVBENCH_API_URL` overrides (set it to `http://localhost:8001` for `.claude/launch.json`). |
| AUD-18 | L | `client` lint | `oxlint` linted the committed `dist/` bundle (hundreds of warnings). | **Fixed**: `ignorePatterns`. |
| AUD-19 | M | `pyproject.toml` | Table export (`DataFrame.to_latex`) needs `jinja2`, which was not declared, so `govbench-rigor` crashed after writing JSON. | **Fixed**: dependency added. |
| AUD-20 | **H** (design) | `verifier_agent.py` | The verifier gives a run-level `VERIFIED / FLAGGED_UNSUPPORTED_CLAIMS / CRITICAL_HALLUCINATION`. It has no per-claim SUPPORTED / UNSUPPORTED / CONTRADICTED / UNVERIFIABLE classification. | **Open by decision**: changing the prompt changes the treatment and breaks comparability with the stored runs. Recommended for the next model run. |
| AUD-21 | M | HITL | "Review minutes" are sampled from N(2.5, 0.8), clipped to [0.5, 7] (`governance_economics.py`). They are not measured, and the reviewer is an LLM. | **Documented** (now listed in the report limitations). Do not report human-review time as a result. |
| AUD-22 | M | `client.generate` | When a provider omits `usage`, tokens are silently estimated as chars/4. | **Mitigated**: a warning is now logged. |
| AUD-23 | L | `config/pipeline_variants.yaml` | Not read by the code. V5 omitted the consistency checker. | **Fixed** to match the code and marked descriptive. Its `risk_profile` strings are unsupported claims; do not cite them. |
| AUD-24 | L | Python lint | 570 ruff findings before the audit, almost all `UP*` annotation style. The only defects were 6 unused imports. | Unused imports fixed. Style left alone to keep the diff reviewable. |
| AUD-25 | L | `/api/stats` (mixed-population averages), dashboard null guards, unclosed SQLite connections, multi-worker job recovery | Code inspection | **Open**, low impact. |
| AUD-26 | M | Frontend | No frontend tests exist (no vitest/jest). | **Open**. Covered only by build, lint and the API smoke test. |

Counts: **Critical 1, High 8, Medium 12, Low 5** (26 total). Fixed or mitigated in code: 21 (including AUD-01 for
future runs). Documented only: 1 (AUD-21). Open: 4 (AUD-09, 20, 25, 26), plus the AUD-01 confound in the existing
closed-loop data, which only a rerun removes.

## 4. Research-design checks (Phase 2)

| Check | Result |
|---|---|
| Same cases for every configuration | Yes: paired by `case_id`. 300/300 in MedQA. |
| Configurations independently executed | Governance layers yes. The upstream is deliberately shared. That is a valid paired design *if* it is shared across all passes, which AUD-01 broke. |
| Reproducible sampling | Yes: `random.Random(42).sample(range(1273), 300)`, with indices in `medqa_300.meta.json`. Unique IDs and unique questions. |
| Ground-truth isolation | Yes: agents read only `question`/`clinical_note`/`options`. Now enforced by a test and by label stripping in the API. |
| Label leakage in question text | None found (regex scan for "answer:" / "correct option" in all 300). The answer key matches the option text in 300/300. |
| Distinct, documented behaviour per level | Yes (METRIC_DEFINITIONS §3). Levels are **different mechanisms, not strictly increasing intensity**: G1, G2 and G3 are single, non-nested checks, and G4 = all of them + the consistency checker. |
| Consistent model settings | Same model for every agent. Per-agent temperatures 0.1/0.2 are identical across levels and recorded per step. |
| Provenance recorded | Model, provider, per-step temperature, seed (best-effort at the provider), judge. Dataset version is in `.meta.json`. |
| Missing and failed runs explicit | Failed live calls skip the run (never simulated). Parse failures are recorded per agent. |
| HITL labelled simulated | Yes in the UI, README and paper. Now also in the report limitations. |
| Single-model baseline | V1 is the same model without governance. A single-call baseline (no Research agent) is not implemented. |
