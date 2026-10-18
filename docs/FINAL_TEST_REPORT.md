# Final Test Report — 2026-10-18

Every result below was observed in this session (macOS, Python 3.11, Node 26.8, Chrome via DevTools). No live or paid
model call was made. All tests use mocked or synthetic data.

## 1. Automated checks

| Check | Command | Result |
|---|---|---|
| Python unit + integration | `uv run pytest -q` | **183 passed** (175 before these passes + 8 new API tests) |
| UI tests | `cd client && npm test` | **9 passed** (new; Vitest + Testing Library, jsdom) |
| Client build | `npm run build` | built |
| Client lint | `npm run lint` | 0 errors, 3 warnings (pre-existing `set-state-in-effect`) |
| Python defects | `uv run ruff check src scripts tests --select F,E9` | 1 (`F841` in the withdrawn `scripts/backfill_metrics.py`, pre-existing) |
| Paper numbers, full paper | `uv run python -m scripts.check_paper_numbers` | 169/169 |
| Paper numbers, NCRTHT paper | `... --tex paper/main_ncrtht2026.tex` | 86/86 |
| Raw databases | MD5 of `results/*.db` before vs after this pass | unchanged |
| Paper sources | `git diff audit/2026-10-10 -- paper/main*.tex` | identical |
| Submission PDF | page count of `paper_out/NCRTHT2026_submission.pdf` | 4 pages, not rebuilt in this pass |

### New tests

| Test | What it proves |
|---|---|
| `test_experiment_registry_lists_known_reports_and_rejects_anything_else` | `/api/research/experiments` lists the three experiments. Path-traversal and unknown keys get 400 on findings and LaTeX |
| `test_each_experiment_serves_its_own_report` | Each key serves its own report (run count, variant list). Omitting the parameter returns the original 150-case report, so the API contract is unchanged |
| `ClinicalCases`: counts | Scorable-label count and list size come from the data |
| `ClinicalCases`: filters | Dataset, specialty and search narrow the list. The empty state names the active filters. "Clear all filters" restores the list |
| `ClinicalCases`: open in workspace | Rows are buttons with `aria-current`. "Open in Clinician Workspace" sends the case text **but not the gold label** |
| `ClinicalCases`: templated labels | Templated labels are marked "not scorable" |
| Experiment store | Defaults to `open150`, URL-encodes the key, shares the selection across components and remembers it |
| Experiment picker | Lists only available experiments and changes the selection |
| `test_stats_and_csv_follow_the_selected_experiment` | Two synthetic experiment databases (2 and 9 runs) give exactly their own counts, cases, variants and CSV rows. Accuracy never borrows another experiment's report. The CSV filename names the experiment and unmeasured columns are excluded |
| `test_stats_and_csv_reject_unknown_experiments` | Traversal, file paths, wrong case and oversized keys get 400 on both endpoints |
| `test_default_stats_and_csv_are_unchanged` | No parameter = `open150` = the server's default database; old CSV filename kept |
| `test_superseded_runs_are_exported_but_not_counted` | A re-run pair: stats count 2 analysed, 3 stored, 1 superseded; the CSV keeps all 3 and marks the older one |
| `test_empty_and_missing_experiments_are_safe` | Empty database gives `has_data: false` and an empty CSV; a missing database gives 503 with a message (not 500); the listing reports `runs_available` |
| `test_real_experiments_charts_and_exports_agree_with_source_records` | For each stored experiment (read-only): CSV rows = stored rows; non-superseded rows per variant = the chart's per-variant `n_runs`; stats `total_runs` = the report's `n_runs_analyzed`; paired-MedQA chart accuracy = stored per-variant exact-match mean |
| Reports page | Requests the LaTeX, findings and CSV of the experiment chosen in the top bar; an export failure shows its own error |

**Defects found by the new tests:** the 751-vs-750 run mismatch (FIN-13); and a "Clear filters" button inside the list heading made the heading's accessible name
"2 cases Clear filters". It was moved out of the heading.

## 2. Browser checks (Chrome DevTools)

| Check | Result |
|---|---|
| All 9 routes, light and dark | Load with **0 console errors or warnings** |
| API calls | All returned 200 |
| Experiment picker | Switching to "300 MedQA · paired closed loop" updates every results page |
| Charts against source data | Dashboard bars matched the report JSON: accuracy 0.43, 0.40, 0.447, 0.403, 0.43, 0.373 |
| Pipeline page against source data | G1 → V2-CL: accuracy 0.400, tokens 4818, governance latency 28.6 s, 3.73 calls, 109 hallucination flags |
| Case Library interactions | Cardiology chip → 17 cases; nonsense search → empty state naming both filters; Clear → 150; focused row is a `BUTTON` with a visible focus ring; selection sets `aria-current` |
| Server whitelist | `?experiment=../../etc/passwd` returns 400 |
| Stats and CSV per experiment (live server) | default and `open150`: 750 analysed, 751 stored, 1 superseded, CSV 751 rows (1 marked); `medqa_paired` and `medqa_unpaired`: 1,800 each, 0 superseded, 300 per configuration; unknown key 400 |
| LaTeX endpoint | `?experiment=medqa_paired` returns that experiment's table |
| Phone width (390 px), all 9 routes | No horizontal page scroll. The top bar keeps menu, experiment picker and theme; chart labels compress to stacked IDs |
| Reduced motion (earlier pass) | Press scaling disabled. Chart animation is now also off under the preference |

## 3. Not verified

- **Forms:** submitting the Experiments and Clinician Workspace forms makes live, billable model calls, so it was not done.
- **Platforms:** Safari and Firefox were not tested; only Chrome.
- **Screen readers:** no screen reader was run. The accessible names were checked through the accessibility tree.
- **Type checking:** no type checker exists; the client is JavaScript.

## 4. Commands

```bash
uv sync --extra dev && (cd client && npm install && npm run build)
uv run uvicorn src.api.server:app --port 8000      # http://localhost:8000
uv run pytest -q
(cd client && npm test && npm run lint)
uv run python -m scripts.check_paper_numbers --tex paper/main_ncrtht2026.tex
```
