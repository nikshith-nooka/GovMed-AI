# Paper Final Audit — NCRTHT 2026 submission

Date: 2026-10-18 · Branch `paper/final-refinement`, created from `analysis/holm-scope-wording` (`8f7fb2f`), which
already contains the Holm-scope wording in the rigor reports. **Nothing is committed or pushed.**

> **Status update (2026-10-18, repository audit):** this work was later committed as `21b353d` on the local
> `paper/final-refinement` branch and pushed as the patch-identical `6d38bb9` (`nikshith/paper/final-refinement`),
> which is an ancestor of `main` (`2ff62d6`). The documents moved to `docs/audit/` in `2ff62d6`. A PDF compiled from
> the `2ff62d6` source has the same 4 pages, US Letter size and extracted text as `paper_out/NCRTHT2026_submission.pdf`.
> The author questions in §7 are still open, except that a `LICENSE` file (MIT) now exists (Q6, second part).
Source: `paper/main_ncrtht2026.tex` · PDF: `paper_out/NCRTHT2026_submission.pdf` (a copy of
`paper/main_ncrtht2026.pdf`) · Previous PDF: `paper_out/NCRTHT2026_submission_prev_2026-10-18.pdf`

Companion documents: `docs/audit/PAPER_NUMBER_VALIDATION.md` (every number) and `docs/audit/PAPER_STYLE_CHANGES.md` (visual and
format changes).

## Verdict: READY AFTER AUTHOR CONFIRMATION

The numbers, statistics, figures and references are verified, and the PDF meets every requirement the conference
actually publishes (IEEE double column, ≤ 4 pages). Submission still needs the author decisions listed in Section 7.
The CFP does not state paper size, anonymization or file limits, and the cost rate and data-redistribution rights are
not documented in the repository.

## 1. Conference requirements (https://easychair.org/cfp/NCRTHT-2026, fetched 2026-10-18)

| Requirement | Official statement | This PDF | Status |
|---|---|---|---|
| Format | "IEEE double column format" | IEEEtran `conference`, matching the template in `Conference-LaTeX-template_10-17-19/` | ✓ |
| Length | "limited to 4 pages" | 4 pages | ✓ |
| Submission | EasyChair, https://easychair.org/conferences/?conf=ncrtht2026 | — | author action |
| Deadlines | paper 2026-10-30; notification 11-10; camera-ready 11-20 | — | — |
| Paper size | **not stated** | US Letter (template default); an A4 Word template is also in the repo folder | unresolved, Q4 |
| Anonymization / blind review | **not stated** | authors named | unresolved, Q5 |
| PDF/font rules, file size | **not stated** | all fonts embedded and subset, no Type 3, 98 KB | ✓ for generic IEEE |
| Reference style | not stated beyond IEEE | IEEE numeric style | ✓ |
| Proceedings | "Conference Proceedings with ISBN"; DOI possible | — | — |

## 2. Research and statistical corrections made

1. **Safety-validator claim (abstract and §V-B).** "Raised an alert on every run" became "on every run of each
   configuration that included it", and §V-B names the three configurations (G3 closed, G4 open, G4 closed; 300/300
   each, verified in the raw DB).
2. **Multiplicity.** The abstract and §V-A now give both p-values: McNemar p = 0.040 unadjusted, and p = 0.55 after
   Holm correction across the family of 30 paired tests. §IV defines that family (the McNemar accuracy tests plus the
   paired Wilcoxon tests of secondary quality metrics, each configuration vs G0). The within-family Holm value (0.0396)
   covers a family of one test, so the paper does not quote it.
3. **Sign test.** p = 0.027 is now labelled unadjusted, and the paper states that it is not significant after Holm
   correction across the four closed-loop sign tests (adjusted 0.109).
4. **Revision denominators.** "Of 235 scorable revisions" became an explicit account: 238 revised, 235 scorable before
   and after (three had an empty first answer), 21 wrong→right, 39 right→wrong, the rest unchanged. The Table I
   footnote defines Revised and Fix/break.
5. **Workflow description (§III, Fig. 1).** Corrected against `src/pipeline/orchestrator.py`:
   - The consistency checker reads the *extracted findings*, not the case.
   - The attending reviewer runs after the checks and reads the safety findings.
   - After a revision, **only the verifier and safety validator** re-check, and their findings cannot trigger a
     second revision. The old caption said "the enabled checks run again".
   - Deterministic rule flags are added to every final answer.
   - The paper now records that no revision failed to parse (0 of 545).
6. **Cost.** "At an assumed price" now states the rate ($0.10 / $0.20 per M input/output tokens) and calls it an
   illustrative assumption from the code, not a quoted provider price. This is also listed as a limitation.
7. **Temperatures.** Now given per role (0.1 extraction/checks, 0.2 diagnosis/revision/review), verified from the
   `agent_steps` table.
8. **Power statement.** The bare "0.0579" now has its definition: mean discordance 12.9 %, 80 % power, α = 0.05,
   which gives 5.8 points.
9. **Unsupported superlative.** The attending reviewer is no longer called "the most selective check". It revised
   34.7 % of questions, while the safety validator in G3 revised 31.3 %. It is now "the only check whose revisions fixed
   more answers than they broke … though not significantly".
10. **AUROC definition (Table II note).** The signal is the first check's alert, and the label is whether the *final*
    answer is wrong. This is stated rather than changed (see Q3).
11. **Citation fit.** Line 80 now says "add further agents that critique or check its output" instead of "verify,
    critique or approve", which fits MetaGPT, AutoGen and multi-agent debate more fairly.

Unchanged, and verified as correct: the paired design (300/300 first answers identical per configuration), ground-truth
isolation (`tests/test_audit_fixes.py::test_ground_truth_never_reaches_any_agent`), open- vs closed-loop definitions,
simulated attending labelled as simulated, 52 no-option answers counted as wrong, the negative result reported as
exploratory, and no claims of clinical validation or deployment.

## 3. Reference verification (all 20 entries)

Each entry was checked against Crossref/doi.org, arXiv, OpenReview, PMLR, the ACL Anthology and papers.nips.cc. Every
DOI resolves to the cited work, and every author list matches its source. There are no duplicates, and every entry is
cited in the text.

| Entry | Action |
|---|---|
| [14] MDAgents | arXiv → *Advances in NeurIPS*, vol. 37, 2024, pp. 79410–79452 (published version) |
| [7] AutoGen | arXiv → *Proc. COLM* 2024; the published title ends in "Conversations" |
| [17] MT-Bench | Venue written out: *Advances in NeurIPS (Datasets and Benchmarks Track)*, vol. 36, pp. 46595–46623 |
| [15] MedAgentBoard | Accepted at the NeurIPS 2025 D&B Track (OpenReview BPpG4qQaNj); no volume or pages were found online, so it stays as is |
| [20] Holm | No DOI exists (JSTOR 4615733); details confirmed only through secondary indexes because JSTOR blocked automated access |
| All others | OK as written |

## 4. Reproducibility and repository

- The repository link is https://github.com/nikshith-nooka/GovMed-AI, as instructed.
- Model id, provider, decoding settings, seed (42), split size (1,273) and the sampler are recorded in
  `benchmarks/medqa_300.meta.json` and in each DB row.
- **Redistribution:** the repository tracks `benchmarks/medqa_300.json` and databases containing MedQA question text.
  Its MIT declaration (`pyproject.toml`, README) covers the code, and there is no `LICENSE` file. The repository does
  not record MedQA's own terms (Q6).

## 5. Commands executed

```
git switch -c paper/final-refinement analysis/holm-scope-wording
md5 results/*.db                                                     # before and after: identical
sqlite3 results/medqa_paired.db …                                    # independent recomputation (see validation doc)
uv run python -m scripts.make_paper_figures
cd paper && ../tectonic --keep-logs main_ncrtht2026.tex              # 0 errors, 0 overfull
cd paper && ../tectonic main.tex                                     # long version still compiles
uv run python -m scripts.check_paper_numbers --tex paper/main_ncrtht2026.tex \
  --report results/rigor_report_medqa_paired.json,results/rigor_report_medqa.json,results/rigor_report.json   # 96/96
  … --integers                                                       # 137/138 (1,273 is backed by the meta file)
uv run python -m scripts.check_paper_numbers --tex paper/main.tex --report …                                  # 169/169
uv run pytest -q                                                     # 175 passed
uv run --with pymupdf python …                                       # pages, size, fonts, text extraction, renders
```

The earlier report of "86/86" used the same three-report set. The text now holds 96 checked values because new
definitions were added.

## 6. Regression scope

`git diff --stat` touches only `paper/main_ncrtht2026.tex`, `scripts/make_paper_figures.py`, `paper/figures/*` and
these three docs.

- **Unchanged:** the databases (MD5 identical), the rigor reports, `src/`, `client/`, tests, the
  `analysis/holm-scope-wording` branch and the `ui/apple-design` branch (now checked out in a separate worktree by
  another session).
- **Untracked user folders left untouched:** `Conference-LaTeX-template_10-17-19/` and `Word-Letter-A4/`.
- The PDF is git-ignored (`paper_out/`), so "PDF matches committed source" can only be confirmed once the source is
  committed. The PDF was built from the working-tree source above. (Since confirmed against the committed source; see the status update at the top.)

## 7. Questions for the author

- **Q1 — Cost rate.** Where do $0.10 / $0.20 per M tokens for Llama-3.2-11B come from? Is there a provider price page
  and date? If none, keep the "illustrative assumption" wording, or drop the dollar figures and report tokens only.
- **Q2 — Primary analysis.** Confirm that no comparison was pre-registered. The paper calls G4 closed vs open
  exploratory.
- **Q3 — AUROC label.** For closed-loop rows the label is the *final* (possibly revised) answer. Should the first
  answer's correctness be the label instead? It is arguably the cleaner detector target, but this would be a method
  change and needs a rerun of `govbench-rigor`, so it was not made here.
- **Q4 — Paper size.** The CFP does not say. Confirm US Letter, or switch to A4 (`\documentclass[conference,a4paper]`)
  if the organizers ask for it.
- **Q5 — Anonymization.** The CFP does not mention blind review. Confirm that author names may appear in the
  submission.
- **Q6 — Data rights.** Confirm that redistributing the 300 MedQA items (and the DBs holding their text) is
  permitted. Consider adding a `LICENSE` file for the declared MIT code licence.
- **Q7 — Author block.** Confirm the order of the four authors, the affiliations and the e-mail addresses (one
  institutional and three Gmail).
