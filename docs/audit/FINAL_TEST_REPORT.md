# Final Test Report — 2026-10-18

## Current results (repository audit)

Commit under test: `main` at `2ff62d6` plus the audit's uncommitted UI-label and documentation changes (listed in
`FINAL_REPOSITORY_AUDIT.md`). macOS 26 (Darwin 25.6), Node 26.8.1, Vitest 3.2.7, oxlint 1.81.0, Tectonic 0.17.0,
Chrome via DevTools. Every result was observed locally. **GitHub runs no CI for this repository** (no workflow files;
the API reports 0 check runs and 0 Actions runs), so nothing here is a CI result. No live or paid model call was made.

| Check | Command | Exit | Result |
|---|---|---|---|
| Python tests (3.14.0, worktree env) | `uv run pytest -q` | 0 | **183 passed**, 3 third-party warnings |
| Python tests (3.11.15, the Docker version) | `python -m pytest -q` | 0 | **183 passed** |
| UI tests | `cd client && npm test` | 0 | **17 passed** (4 files) |
| UI lint | `npm run lint` | 0 | 0 errors, 3 `set-state-in-effect` warnings (`ClinicalCases.jsx`, `Experiments.jsx`, `ClinicianWorkspace.jsx`; pre-existing) |
| UI build | `npm run build` | 0 | CSS 30.0 kB, JS 477 kB |
| Python defects | `uv run ruff check src scripts tests --select F,E9` | 1 | 1 finding, the known `F841` in the withdrawn `scripts/backfill_metrics.py` |
| Paper numbers, full paper | `uv run python -m scripts.check_paper_numbers` | 0 | 169/169 |
| Paper numbers, 4-page paper | `... --tex paper/main_ncrtht2026.tex` | 0 | 96/96 |
| Same, integers | `... --integers` (three reports) | 1 | 137/138; the unmatched 1,273 is `split_size` in `benchmarks/medqa_300.meta.json` |
| Re-analysis from raw DBs | `run_rigor_analysis` ×3, written to a scratch directory | 0 | all three reports identical except `generated_at`; all 30 paper tables and the clinician protocol byte-identical |
| Paper figures | `make_paper_figures.main()` with output redirected to scratch | 0 | all 6 PNGs pixel-identical to `paper/figures` |
| 4-page PDF | `tectonic -X compile paper/main_ncrtht2026.tex` | 0 | 4 pages, 612 × 792 pt, 0 overfull boxes, 0 undefined references; text identical to `paper_out/NCRTHT2026_submission.pdf` |
| Whitespace | `git diff --check` | 0 | clean |

**Browser (Chrome, audit server with no provider keys):**
- 14 routes, covering the 8 pages, 6 results tabs and `/findings`, in light and dark, at 1280, 820 and 390 px, for `open150` and `medqa_paired`: 168 views.
  - No horizontal overflow, no card or chart wider than the viewport, no crash or error banner.
  - The theme attribute matched in every view.
  - 0 console errors or warnings.
- `/findings` → `/results?tab=findings`.
- Server log: 755 GET 200 and 12 GET 304; the only 400s were the deliberate unknown-key probes. **No POST was sent, so no model call was possible.**
- Paired MedQA values on screen match the report:
  - accuracy 0.430/0.400/0.447/0.403/0.430/0.373 with Wilson intervals;
  - revision 15/24, 13/8, 12/21, 21/39;
  - forest V5-CL −5.7 points (−10.7 to −0.7), p 0.040, Holm 0.555.
- Keyboard focus on a chart mark shows its tooltip.
- Under emulated `prefers-reduced-motion: reduce`, no SVG element animates.
- Chrome's "form field without label" notices refer to inputs named by `aria-label` (search, run filter, variant select). Every field has an accessible name.

**Not tested:** Safari, Firefox, a screen reader, submitting the Experiments or Clinician Workspace forms (live, paid calls), and any live provider.

## Pass 2 (`07e31de`)

The sections below describe the tree of commit `07e31de` (UI tests then numbered 9, the 4-page paper then 86/86).

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

## Pass 3 (`0d9152b`, 2026-10-18)

| Check | Result |
|---|---|
| `uv run pytest -q` (worktree) | **183 passed** |
| `npm test` | **17 passed**: 9 earlier and 8 new. The new tests cover the Wilson interval against a hand calculation, report adapters (missing values stay missing), focusable marks with tooltips, unavailable states on all five chart types, forest-plot p and Holm labels, diverging-bar counts, "not measured" overhead, and pipeline-diagram dimming and keyboard selection |
| Lint | 0 errors, 3 pre-existing warnings |
| Build | built; CSS 30.0 kB, JS 477 kB |
| Paper numbers | 169/169, 86/86 |
| Research files vs `audit/2026-10-10` | identical (`paper/`, `benchmarks/`, raw databases) |
| Browser (Chrome) | All 8 pages in light and dark mode with 0 console errors. `/findings` → `/results?tab=findings`. Charts checked against the report: dot plot 0.430/0.400/0.447/0.403/0.430/0.373; revision 15/24, 13/8, 12/21, 21/39; forest V5-CL −5.7 (−10.7 to −0.7), p 0.040, Holm 0.555. Keyboard focus on a mark gives its spoken label and tooltip; 12 focusable marks on the Overview |
| Phone (390 px) and reduced motion | All 12 views (8 pages, results tabs) fit with no horizontal scroll; charts switch to compact IDs and stay inside their cards |
| Not verified | Safari/Firefox, a screen reader, and submitting the live-model forms (paid calls) |
