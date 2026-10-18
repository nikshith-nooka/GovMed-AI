# Final Repository Audit — 2026-10-18

Repository: `https://github.com/nikshith-nooka/GovMed-AI` (public, default branch `main`).
Audited commit: `main` at **`2ff62d6`**. The audit's own corrections are uncommitted in the worktree on branch
`release/main-2026-10-18`. **Nothing was committed, merged or pushed by this audit.** Test evidence is in
`FINAL_TEST_REPORT.md` (Current results).

## Verdict: READY FOR REVIEW

The redesigned UI, the paper revision and the research data on `main` were verified against the source records.
- All test suites pass, and the reports, tables and figures regenerate identically from the raw databases.
- No critical issue remains.
- It is not "ready to merge": the audit's corrections still need the owner's review and a commit, and the author
  decisions in §6 are open.

## 1. Git and GitHub state (fetched 2026-10-18)

| Branch | Local | Remote (`nikshith`) | In `main`? |
|---|---|---|---|
| `main` | `76c3b92` (stale: pre-rewrite history, 20 ahead / 34 behind) | `2ff62d6` | — |
| `ui/apple-design` | `0d9152b` | `0d9152b` | yes (ancestor) |
| `paper/final-refinement` | `21b353d` | `6d38bb9` | `6d38bb9` yes; `21b353d` is the patch-identical original (`git range-diff`: `=`) |
| `analysis/holm-scope-wording` | `8f7fb2f` | `8f7fb2f` | yes, via PR #1 merge `63b7017`; same content as `e4da3c7` |
| `audit/2026-10-10` | `54e4ec9` | `54e4ec9` | yes |
| `release/main-2026-10-18` | `2ff62d6` + audit changes | — | worktree used for this audit |
| `backup-before-email-rewrite`, `backup/audit-2026-10-10-pre-rebase` | local only | — | old history, kept |

**History of `main` since `54e4ec9`:** `850c933` → `07e31de` → `0d9152b` (UI); `e4da3c7` (Holm wording);
`63b7017` (PR #1 merge, tree identical to `e4da3c7`); `6d38bb9` (paper); `2ff62d6` (release tidy-up).

**Working trees:**
- **Shared `MED` folder:** on `paper/final-refinement` at `21b353d`. It has no tracked changes and 2 untracked template folders. It was inspected read-only.
- **A kilo worktree:** detached at `6d8d535` (September), clean, not touched.
- **Stashes:** none.

**CI:** none. The repository has no `.github/` workflows, and the GitHub API reports 0 check runs, 0 Actions runs and
an empty commit status for `2ff62d6`. Every result in this audit is local.

## 2. What each commit changed (from the diffs)

| Commit | Files | Research files touched |
|---|---|---|
| `850c933` | `client/` only | none |
| `0d9152b` | `client/`, `README.md`, the three UI/audit docs; deleted 8 unreferenced files from `client/public` | none |
| `07e31de` | `client/`, `src/api/server.py` (experiment registry, `?experiment=`, stats over the analysed population), `tests/test_audit_fixes.py` | none: no analysis, scoring or data change |
| `e4da3c7` | `src/analysis/rigor.py` (headline wording) and the 3 reports | reports: only one headline string each and `generated_at` (field-by-field JSON diff) |
| `6d38bb9` | `paper/main_ncrtht2026.tex`, `paper/figures/*`, `scripts/make_paper_figures.py`, 3 paper docs | none |
| `2ff62d6` | LICENSE, docs moved to `docs/audit/`, client README, `.gitignore`, withdrawn note on `backfill_metrics.py`, `.agents/` untracked | none |

`git diff 54e4ec9 main` over `results/ benchmarks/ config/ src/analysis src/evaluation src/pipeline src/agents` shows
only the four `e4da3c7` files.

## 3. Research-data integrity

- **Raw databases:** unchanged since their last data commits. SHA-256:
  - `benchmark_results.db` `e10a723c…` (`484ad74`)
  - `.bak` `36a01135…` (`cdfb515`)
  - `medqa_fast.db` `ad9f0ff0…` (`47709dc`)
  - `medqa_paired.db` `aad0cdad…` (`e4733f9`)

  All 13 tracked files under `results/` and `benchmarks/` match `HEAD`.
- **Reproduction:** `run_rigor_analysis` was rerun for all three experiments into a scratch directory.
  - The reports are identical to the committed ones apart from `generated_at`.
  - The 30 paper tables and the clinician protocol are byte-identical.
  - The paper figures regenerate pixel-identically.
- **Pairing:** all 1,200 closed-loop runs in `medqa_paired.db` start from the G0 run's diagnosis for the same case.
- **Paper claims checked against the database:**
  - 52 no-option answers (9 empty + 43 unparseable);
  - 238 revised V5-CL runs, of which 235 are scorable;
  - revision rate 79.3%;
  - AUROC range 0.497–0.57 over 12 values;
  - mean tokens 2200.9 → 11362.7.
- **Experiment-aware UI:**
  - Charts read `/api/research/findings?experiment=`. No result constant is hard-coded in `client/src`.
  - Stats and CSV follow the selected experiment: 750 analysed of 751 stored (1 superseded) for `open150`, and 1,800 for each MedQA experiment.
  - Unknown or path-like keys get 400.
- **Exports:** the CSV holds run metadata and scores only, with no case text and no answer key (`gold_label_valid` is a flag). Tooltips show configuration labels and aggregates only.
- **Secrets:** no key-shaped strings in tracked files, in the full history or inside the tracked databases. `.env.example` holds placeholders.

## 4. Findings and corrections made by this audit

| ID | Severity | Finding | Action |
|---|---|---|---|
| REP-01 | Medium | The revision-impact chart, its tooltip and table showed the sign-test p without qualification. The report holds no Holm value for it, and the paper calls it unadjusted | Labelled "unadjusted" in the mark label, tooltip, subtitle, table header and note. The test now asserts the label |
| REP-02 | Low | Page headings differed from the sidebar ("Clinical Case Library", "Reports & Exports"), although the code comment and docs say they match | Headings aligned. The error fallback now reads "Return to Overview" |
| REP-03 | Low | `UI_REDESIGN_SUMMARY.md` described the pass-1 sidebar (Dashboard, Research Findings, Governance Pipeline) | Corrected to the current 8 pages and the Findings tab |
| REP-04 | Low | `PAPER_FINAL_AUDIT.md` said nothing was committed or pushed, and that the PDF could not yet be matched to committed source | Status note: `21b353d`/`6d38bb9`, an ancestor of `main`; the PDF matches the `2ff62d6` source |
| REP-05 | Low | Audit reports did not say which commit their results describe; `FINAL_TEST_REPORT.md` showed 9 UI tests and 86/86 as if current | Provenance notes on each report; a current-results section with commit, commands and exit codes |

Not changed (with the reason):
- **3 lint warnings** (`set-state-in-effect`): pre-existing, and the fix changes component state flow.
- **The `F841`** in the withdrawn backfill script: the script is kept as-is for traceability.
- **The API default experiment `open150`:** changing it would alter the API contract that tests pin. The paper's experiment is one click away and is labelled "reported in the paper".
- **The `make_paper_figures.py` log line** says "wrote paper/figures/…" even when `OUT` is redirected. It is cosmetic only.
- **Local `main` is stale.** `git branch -f main nikshith/main` would align it, but it changes a branch, so this is left to the owner.

## 5. Paper workstream

Source `paper/main_ncrtht2026.tex` at `2ff62d6`.
- **Title:** "Do Governance Checks Improve Clinical Question-Answering Accuracy? A Paired Evaluation of Multi-Agent Language Models".
- **Abstract:** its numbers match the paired report.
- **P-values and Holm wording are consistent:**
  - McNemar p = 0.040 unadjusted and 0.55 after Holm over 30 paired tests.
  - The sign test p = 0.027 is unadjusted and "not significant after Holm across the four sign tests". 4 × 0.02734 = 0.109; the number itself is not printed.
- **Number checks:** 96/96 decimals and 137/138 integers (the remaining one is backed by the meta file).
- **Captions:** they match the figure content (Wilson intervals, the dashed G0 line).
- **Compile:** 4 pages, US Letter.
- **PDFs:** `paper_out/NCRTHT2026_submission.pdf` and the ignored `paper/main_ncrtht2026.pdf` both match the source. Older copies are kept beside it: `_prev_2026-10-18` and `_stale_1638`.

## 6. Open author decisions (unchanged; none were resolved by this audit)

- **Q1:** the source of the cost rate.
- **Q2:** confirm there was no pre-registration (the paper calls the comparison exploratory).
- **Q3:** whether the AUROC label should be the final answer or the first answer.
- **Q4:** US Letter or A4.
- **Q5:** whether author names may appear (anonymisation).
- **Q6:** the right to redistribute the 300 MedQA items and the databases holding their text. The MIT LICENSE now exists.
- **Q7:** author order, affiliations and e-mail addresses.

## 7. Files modified by this audit (uncommitted, worktree `release/main-2026-10-18`)

- **UI:**
  - `client/src/components/charts.jsx`
  - `client/src/pages/ResultsComparison.jsx`
  - `client/src/pages/ClinicalCases.jsx`
  - `client/src/pages/Reports.jsx`
  - `client/src/App.jsx`
- **UI tests:**
  - `client/src/__tests__/charts.test.jsx`
  - `client/src/__tests__/ClinicalCases.test.jsx`
  - `client/src/__tests__/Reports.test.jsx`
- **Build:** `client/dist/index.html` and `client/dist/assets/index-*.js` (rebuilt bundle).
- **Docs:**
  - `docs/audit/FINAL_REPOSITORY_AUDIT.md` (new)
  - `docs/audit/FINAL_TEST_REPORT.md`
  - `docs/audit/UI_REDESIGN_SUMMARY.md`
  - `docs/audit/PAPER_FINAL_AUDIT.md`
  - `docs/audit/PAPER_NUMBER_VALIDATION.md`
  - `docs/audit/FINAL_PROJECT_AUDIT.md`
  - `docs/audit/PROJECT_AUDIT.md`
  - `docs/audit/TEST_REPORT.md`
- **Not modified:** no file under `results/`, `benchmarks/`, `paper/`, `src/` or `tests/`, and nothing in the shared `MED` folder.
