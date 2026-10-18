# Test Report — 2026-10-10

> **Provenance:** results of the 2026-10-10 audit, last revised in `a7c1c04` (branch `audit/2026-10-10`). Counts and page
> lists describe that commit; the current ones are in `FINAL_TEST_REPORT.md`.

Every result below was observed in this session on macOS (Darwin 25.6), Python 3.11 (`.venv`) and Node via `npx`.

## 1. Checks run

| Check | Command | Before audit | After audit |
|---|---|---|---|
| Unit + integration tests | `uv run pytest -q` | 164 passed | **175 passed**, 0 failed (3 third-party deprecation warnings) |
| Python lint (defects) | `uv run ruff check src scripts tests --select F,E9` | 11 | 1 (`F841` in the withdrawn `scripts/backfill_metrics.py`) |
| Python lint (all rules) | `uv run ruff check src scripts tests` | 570 | 563 (the rest are `UP*` annotation style, left alone) |
| Formatter | `uv run ruff format --check` | 33 files would change | not applied |
| Type checker | — | not configured (no mypy/pyright in the project) | not run |
| Client lint | `cd client && npm run lint` | hundreds of warnings from `dist/` | 0 errors; warnings only (unused imports, `set-state-in-effect`) |
| Client build | `cd client && npm run build` | built | **built** |
| Client type check | — | JavaScript project, no TypeScript | n/a |
| Paper numbers | `uv run python -m scripts.check_paper_numbers` | 156/156 | **169/169** (full paper) and **87/87** (NCRTHT version); both enforced by a test |
| Analysis pipeline | `govbench-rigor`, MedQA `run_rigor_analysis` | crashed on table export (missing `jinja2`) | **writes JSON + tables** |
| Server smoke test | `uvicorn src.api.server:app --port 8765` + curl | — | `/api/health` 200, `/` 200, `/api/research/findings` 200, `/api/runs?variant=V1` returns V1 only, `/api/nope` 404 |
| Browser walkthrough | chrome-devtools: all 9 pages via the sidebar | — | 0 console errors or warnings; 16/16 API requests 200 |
| API checks | curl: `/api/reports/csv`, `/api/runs?variant=V5`, missing case, demo provider | — | CSV 200; V5 filter returns only V5; unknown case 404; demo provider refused with 400 |
| Raw data integrity | MD5 of `medqa_fast.db`, `benchmark_results.db` before and after | — | **unchanged** |

## 2. Coverage of the requested test areas

| # | Area | Covered by |
|---|---|---|
| 1 | Dataset loading and label mapping | `test_data_loader.py`; `test_methodology.py` (MedQA key == option text for every case) |
| 2 | Ground-truth isolation | **new** `test_ground_truth_never_reaches_any_agent` (all 5 variants, closed loop, sentinel label) |
| 3 | Agent I/O schemas | `test_agents.py`, `test_hardening.py` (schema allow-list, injection fencing) |
| 4 | Governance-level behaviour | `test_pipelines.py`, `test_methodology.py` |
| 5 | Verifier classification | partial: run-level status only (per-claim categories not implemented, AUD-20) |
| 6 | Revision limit and failed revision | `test_methodology.py` (one round, re-check); **new** failed-check tests |
| 7 | Metric formulas (hand-computed) | `test_evaluation.py`, `test_integrity.py`, `test_methodology.py` (McNemar, Holm, option parsing); **new** missing-gold test |
| 8 | Token and latency measurement | **new** `test_cached_upstream_latency_is_counted_in_total`, `test_llm_latency_excludes_rate_limit_backoff` |
| 9 | Errors and incomplete runs | `test_hardening.py` (strict mode, no mock fallback); **new** `test_unparseable_verifier_is_missing_not_negative` |
| 10 | DB persistence | `test_integrity.py`; **new** `test_closed_loop_pass_reuses_stored_open_loop_diagnosis` |
| 11 | API integration | `test_hardening.py` (auth, PHI, jobs); **new** 404 test; manual smoke test |
| 12 | Reproducibility | deterministic bootstrap seeds; report regeneration matches the paper (168/168) |
| 13 | Frontend rendering | browser walkthrough (manual, recorded above); no automated framework (AUD-26) |
| 14 | Report / CSV / JSON export | `test_integrity.py` (report shape); tables regenerated |
| 15 | E2E, one case per level | `test_ground_truth_never_reaches_any_agent` runs every level end to end with a stub model. **No live-model E2E was run.** |

All tests use deterministic stub models. There are no real-model tests in the suite.

## 3. Not verified
- Live runs: the 1,200-run paired closed-loop rerun (2026-10-11 to 2026-10-18) used the NVIDIA NIM API. No live-model
  test is part of the automated suite.
- Frontend interactions beyond page loads (forms were not submitted in the browser, to avoid live model calls).
- Type checking (no checker configured).

## 4. Known open defects (not fixed)
- AUD-20: per-claim verifier categories are not implemented.
- AUD-25 (remainder): SQLite connections are not closed explicitly; job recovery assumes a single uvicorn worker.
- AUD-26: no automated frontend tests (manual browser walkthrough only).
