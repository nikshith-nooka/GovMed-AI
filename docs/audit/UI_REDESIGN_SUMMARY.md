# UI Redesign Summary

The redesign follows Apple's Human Interface Guidelines and the `apple-design` skill (WWDC *Designing Fluid
Interfaces*, *Details of UI Typography*, materials, accessibility). It is an original interface for a research
benchmark, not a copy of any Apple product. Capabilities are preserved, and every number on screen comes from the backend.

## Design system

**Colour.** All colours come from tokens in `client/src/index.css`, so light, dark and accessibility modes follow automatically.

| Role | Light | Dark |
|---|---|---|
| Background / surface | `#F5F5F7` / `#FFFFFF` | `#111113` / `#1C1C1E` |
| Primary / secondary text | `#1D1D1F` / `#6E6E73` | `#F5F5F7` / `#98989D` |
| Border / separator | `#D2D2D7` / `#E5E5EA` | `#38383A` / `#2C2C2E` |
| Accent | `#0071E3` | `#2997FF` |
| Success / warning / error | `#248A3D` / `#B86E00` / `#D70015` | `#30D158` / `#FF9F0A` / `#FF453A` |

- **Charts:** one accent for the primary measure (accuracy, median latency) and two greys for context, readable in both themes.
- **Governance levels:** they stay distinguishable through labels and bar position rather than a rainbow of colours.

**Typography:**
- The system font (SF Pro on Apple devices) with optical sizing. The three web fonts and the decorative serif were removed.
- Headings use negative tracking that tightens with size, and body text keeps its normal spacing.
- Numbers use tabular digits so columns line up.

**Components (`client/src/pages/clinical.css`):**

| Group | Components |
|---|---|
| Layout | page header with eyebrow line, cards, KPI tiles |
| Controls | segmented control (raised selected segment on a neutral track), filter chips, inputs with an accent focus ring, primary / ghost / small buttons, text links |
| Data | tables (sticky-looking header, row hover), selectable list rows with `aria-current` |
| Status and overlays | status pills (success, warning, error, accent, neutral), banners (info, warning, error, neutral), alerts with severity edge, modal with a blurred backdrop, `visually-hidden` helper |

**Materials and motion:**
- **Sidebar:** a translucent light source list in light mode and a dark material in dark mode.
- **Top bar:** sticky and translucent, with content scrolling beneath it.
- **Press feedback:** buttons scale slightly on press.
- **Animation:** only transform, opacity and colour animate.
- **Accessibility preferences:**
  - `prefers-reduced-motion`: no scale effects or chart animation.
  - `prefers-reduced-transparency`: solid surfaces.
  - `prefers-contrast: more`: stronger borders.
- **Keyboard:** every interactive element shows a visible focus ring.

## App shell

- **Sidebar**, grouped by workflow (eight pages, current since pass 3):
  - **Research:** Overview, Benchmark Results, Agent Pipeline.
  - **Data:** Case Library, Experiments, Reports & Reproducibility.
  - **Clinical:** Clinician Workspace, Clinician Review.
  - Page titles match the sidebar labels. The active item uses `aria-current="page"`.
  - Research Findings is no longer a page: it is the **Findings & validity** tab of Benchmark Results, and `/findings`
    redirects to `/results?tab=findings`.
- **Top bar:**
  - case search (⌘K) and a labelled **experiment picker**;
  - theme, API token and review-queue buttons;
  - at phone width, secondary controls step back so the picker and theme toggle stay.

## Pages (passes 1–2)

This table records the first two passes. The current eight-page inventory is the route table under Pass 3.

| Route | Page | What changed |
|---|---|---|
| `/` | Dashboard | KPIs restyled; notes derived from the selected experiment (FIN-03); chart in the neutral-plus-accent palette with readable two-line labels |
| `/results` | Benchmark Results (was "Benchmark Analytics") | New Closed-loop revision tab; McNemar accuracy tests with Holm-adjusted p; "<0.001" formatting; latency axis titled "Summed agent-call time (s)" |
| `/findings` | Research Findings | Follows the experiment picker; AUROC bars use tokens |
| `/pipeline` | Governance Pipeline (was "Agent Pipeline & Governance") | Steps laid out left to right; selected step marked with `aria-pressed`; outcome panel adds governance-only latency and model calls; closed-loop fallback labelled (FIN-04) |
| `/clinical-cases` | Case Library (was "Clinical Cases Dataset") | Rebuilt on the design system (it used ~60 inline colours); segmented dataset control, specialty chips, keyboard-accessible rows, honest labels (FIN-06, FIN-07) |
| `/experiments` | Experiments | Restyled through shared tokens; behaviour unchanged |
| `/reports` | Reports & Exports | Rebuilt: both manuscripts with real titles, selected-experiment summary, LaTeX table and CSV export of the selected experiment, separate error states |
| `/clinician` | Clinician Workspace | Restyled through shared tokens; behaviour unchanged |
| `/review` | Clinician Review | Restyled through shared tokens; behaviour unchanged |

## Files

| File | Reason |
|---|---|
| `client/src/index.css` | Palette tokens (light and dark), app-shell layer, phone layout, removal of green dark-mode overrides |
| `client/src/pages/clinical.css` | Rewritten as the component system (tokens only) |
| `client/src/components/Sidebar.jsx` | Grouped navigation, `aria-current`, icons instead of emoji |
| `client/src/components/TopNavbar.jsx` | Experiment picker |
| `client/src/lib/api.js` | Experiment store (`useExperiment`), chart palette, closed-loop labels, responsive chart ticks |
| `client/src/main.jsx` | Chart.js defaults (system font, neutral axes, reduced motion) |
| `client/src/pages/ClinicalCases.jsx`, `Reports.jsx` | Rewritten on the design system |
| `client/src/pages/Dashboard.jsx`, `ResultsComparison.jsx`, `AgentPipeline.jsx`, `ResearchFindings.jsx`, `App.jsx` | Experiment-aware data, new tabs, tokenised colours |
| `client/src/__tests__/*` | New UI tests |
| `client/package.json`, `package-lock.json` | Dev dependencies `vitest`, `@testing-library/react`, `@testing-library/dom`, `jsdom`; `npm test` script |
| `src/api/server.py` | Experiment registry; `?experiment=` on findings, LaTeX, stats and CSV; stats over the analysed population with stored and superseded counts |
| `client/src/App.jsx` | Removed an unused `/api/stats` request |

## Pass 3 (2026-10-18): product refinement, charts and cleanup

### Route inventory

| Route | Page | Status | Reason |
|---|---|---|---|
| `/` | Overview | Kept, rebuilt | Experiment identity, one summary card, two primary charts, headline findings. The navigation tiles (duplicated the sidebar) and example-patient cards (already in the Clinician Workspace) were removed |
| `/results` | Benchmark Results | Kept, extended | New SVG charts in each tab. Tab is in the URL (`?tab=`) |
| `/findings` | Research Findings | **Merged, redirects** to `/results?tab=findings` | Repeated the variant, paired-test and signal tables of Benchmark Results. Its unique sections (headline findings, integrity, measurement validity, clinician validation, limitations, calibration, per-agent latency, strata) are now the "Findings & validity" tab |
| `/pipeline` | Agent Pipeline (was "Governance Pipeline") | Kept, rebuilt | Interactive pipeline diagram replaces the row of agent tiles |
| `/clinical-cases` | Case Library | Kept | Unchanged |
| `/experiments` | Experiments | Kept | Unchanged; the only way to run new scored cases |
| `/reports` | Reports & Reproducibility (was "Reports & Exports") | Kept | Renamed for its content (the page heading was aligned with the sidebar in the 2026-10-18 repository audit) |
| `/clinician` | Clinician Workspace | Kept | Live analysis workflow |
| `/review` | Clinician Review | Kept | Functional blinded-review workflow; the study's missing clinician validation depends on it |

Older aliases (`/dashboard`, `/run-case`, `/cases`, `/governance-levels`, `/ablation`, `/cost-performance`, `/run-experiment`) still resolve. A Settings page was not added: the only settings (theme, API token, experiment) already live in the top bar.

### Charts and their data sources

All new charts are SVG (`client/src/components/charts.jsx`). They are drawn at the container's real width, so text stays readable on phones. Data comes from the selected experiment's `/api/research/findings` through `client/src/lib/research.js`.

| Chart | Where | Source fields | Notes |
|---|---|---|---|
| Diagnostic accuracy by configuration (dot plot, 95% Wilson interval, G0 reference line) | Overview; Results › Variant comparison | `variants[].accuracy_valid_gold`, n = `measurement_validity.cases_with_valid_gold` | Axis fitted to the data (no zero baseline needed for a dot plot) and labelled as such |
| Quality against cost (scatter with intervals, direct labels) | Overview; Results › Cost & latency | `accuracy_valid_gold`, `tokens_mean` | |
| Quality against latency | Results › Cost & latency | `accuracy_valid_gold`, `e2e_latency_p50_s` | Labelled as summed agent-call time (upper bound on wall clock) |
| Governance overhead (small multiples) | Results › Cost & latency | `model_calls_mean`, `tokens_mean`, `governance_latency_p50_s` | Missing values say "not measured" |
| Revision impact (diverging bars) | Results › Closed-loop revision | `revision_by_variant[].within_run_fixed / within_run_broken / sign_test_p` | Shown only when the experiment has closed-loop runs |
| Paired accuracy differences (forest plot) | Results › Paired statistics | `accuracy_tests[].accuracy_diff`, CI, `mcnemar_exact_p`, `mcnemar_exact_p_holm` | Blue marks an uncorrected interval excluding zero; the subtitle states that this is not significance after correction |

**Kept, restyled:** the Chart.js quality, latency and AUROC charts.

**Not built:** an experiment-history chart (there are three analysed experiments, not a run history), and reliability charts for abstention and contradiction (the pipeline has no abstention, and contradictions are not summarised in the report). Inventing data for them was not an option.

**Chart colour:** validated with the dataviz palette checker.

| Theme | Fixed bars | Broken bars | Contrast with surface |
|---|---|---|---|
| Light | `#0071E3` | `#C2571A` | ΔE 28.9 under colour blindness, 33.5 for normal vision, ≥3:1 |
| Dark | `#2997FF` | `#D86B33` | passes on `#1C1C1E` |

The neutral grey for the open loop deliberately reads as grey. It always comes with a different marker shape (square vs circle) and a legend, so colour is never the only cue.

**Accessibility of every chart:**
- Each mark is focusable, with a spoken label and a tooltip on hover and focus.
- Each chart has a text summary and a table of the same numbers on the page.
- The tooltip and grid respond to reduced transparency and increased contrast.

### Images and illustrations

- **Added:** one original, theme-aware SVG diagram of the agent pipeline (`PipelineDiagram`), drawn in code. It has no licence encumbrance, and agents not run at the selected level are dimmed. No photographs or stock images were added.
- **Removed:** 13 image files (about 4.7 MB, including a 1.6 MB stock JPEG of lungs) left over from an earlier design and referenced nowhere (checked with `git grep` across the repository). Their source and licence were undocumented, so removing them also removes a licensing risk.
- **Kept:** `favicon.svg`.

### Cleanup

- **`index.css`:** pruned from 3,347 to 775 lines (366 rules dropped). A rule was dropped only if every class in it appears nowhere in the app source, allowing for the `pill-*` and `sev-*` classes that are built dynamically.
- **Built CSS:** 29.7 kB.
- **Code:** Research Findings became `FindingsPanel.jsx`, with its duplicated tables removed.

## Repository audit (2026-10-18)

- The revision-impact chart, its tooltip, table header and note now say that the sign-test p is **unadjusted**, as the
  paper does. The report holds no Holm value for these four tests.
- Page headings now match the sidebar labels: "Case Library" and "Reports & Reproducibility". The error fallback
  button reads "Return to Overview".
