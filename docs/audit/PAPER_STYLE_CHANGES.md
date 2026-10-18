# Paper Style Changes — NCRTHT 2026 version

Date: 2026-10-18 · Files: `paper/main_ncrtht2026.tex`, `scripts/make_paper_figures.py`, `paper/figures/*`

All figures are regenerated from `results/rigor_report*.json` by `uv run python -m scripts.make_paper_figures`. No
value is typed in by hand, and no data, axis range or statistic changed except as listed below.

## Figures

| Item | Before | After |
|---|---|---|
| Figure fonts (all six figures) | DejaVu Serif embedded as **Type 3** (IEEE PDF checks commonly reject Type 3), and visually unlike the Times body | STIX (Times-compatible, ships with matplotlib) embedded as TrueType (`pdf.fonttype 42`). The final PDF contains no Type 3 fonts, and every font is a subset. |
| Figure width | `0.9\textwidth`, so text was scaled and inconsistent | Drawn at the true IEEE `\textwidth` (7.16 in) and placed at `\textwidth`; figure text is 6.5–8 pt as printed |
| **Fig. 1 (workflow)** | Verifier and consistency arrows bypassed the attending and went to "Rules + decision support"; the feedback arrow started at the attending only; the caption said "the enabled checks run again"; no evaluation step | Redrawn from `src/pipeline/orchestrator.py`: clinical case → research agent → diagnosis agent ("first answer") → three parallel checks → attending reviewer (sim., which reads the safety findings) → "Blocking finding?" gate (fed by every check) → final answer + rule flags → scorer (answer key, dashed to mark isolation). The closed-loop branch is dashed and orange: one revision → re-check by **verifier + safety only** → "no second revision" → final answer. |
| **Fig. 2** | Green vs orange bars with identical grayscale luminance; no uncertainty; ad-hoc labels ("Verifier closed") | Light grey (open loop) vs dark blue (closed loop) for accuracy, with 95 % Wilson intervals and value labels; fixed bars solid and broken bars light and hatched (distinct in grayscale), with counts on the bars; labels match Table I ("G1 closed (verifier)") |
| **Fig. 3** | Caption said "accuracy against **cost**" but the x-axis is tokens; legend order scrambled; labels "Verifier CL" did not match Table I | Caption says "mean tokens per question"; legend in order G0, G4 open, G1–G4 closed; Table I names; x-axes start at 0; markers have dark edges |
| Figures used only by `paper/main.tex` (audit_paradox, alert_auroc, calibration) | DejaVu Type 3 | Font change only; the long version still compiles |

## Tables

| Item | Before | After |
|---|---|---|
| Table I accuracy | Proportions (0.430) while the text used percentages | Percentages (43.0 %), matching the text and Fig. 2 |
| Table I columns | Centered, "Fixed/broken" undefined, "Tokens" unit undefined | Right-aligned numeric columns, `tabcolsep` 4.5 pt; a footnote defines Acc., Revised, Fix/break, Tokens and Lat. |
| Table II precision | Mixed 2 and 3 decimals (0.56, 0.497) | 3 decimals throughout (0.560, 0.497); "100 %" → "100.0 %"; a footnote defines the denominator (300 runs) and the AUROC label |
| Table III | 0.38 | 0.380 (3 decimals, like the rest of the column) |
| Table notes | Body-size text | `\footnotesize`, like the table body |

## Layout and typography

- Removed `\IEEEtriggeratref{12}`. After the edits it forced references 12–20 onto a fifth page. Without it the paper
  is four pages and the last-page columns are balanced (checked visually).
- Abstract p-values are plain text (no inline math) so they survive in Xplore metadata.
- `\mbox{$\alpha = 0.05$}` stops a line break inside the expression.
- Kept: the official IEEEtran class (`conference` option, US Letter), `newtxtext/newtxmath` Times (IEEEtran's `ptm`
  cannot load under XeTeX; the four "Font shape TU/ptm undefined" log warnings come from this substitution and are
  harmless), the template's title, author block and keyword style, and the default font sizes and spacing. No sizes
  or spacing were reduced to save room.

## Rendering checks (final PDF)

- 4 pages, all 8.5 × 11.0 in (US Letter, as in the official template `conference_101719.tex`).
- 0 LaTeX errors, 0 overfull boxes, 0 undefined references or citations. Three underfull hboxes remain in reference
  entries [12] and [19]: long unbreakable tokens, invisible in print.
- Text extraction: the minus signs, arrows, percent signs and α, plus the table captions, figure captions and all 20
  reference numbers, extract correctly; there are no "??" placeholders or replacement characters.
- File size 98 KB.
