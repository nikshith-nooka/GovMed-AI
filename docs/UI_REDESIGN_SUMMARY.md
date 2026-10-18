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

- **Sidebar**, grouped by workflow:
  - **Research:** Dashboard, Benchmark Results, Research Findings, Governance Pipeline.
  - **Data:** Case Library, Experiments, Reports & Exports.
  - **Clinical:** Clinician Workspace, Clinician Review.
  - The active item uses `aria-current="page"`.
- **Top bar:**
  - case search (⌘K) and a labelled **experiment picker**;
  - theme, API token and review-queue buttons;
  - at phone width, secondary controls step back so the picker and theme toggle stay.

## Pages

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
