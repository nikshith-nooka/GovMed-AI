---
name: paper-compiler
description: Regenerates the measured analysis, figures and tables, checks every number in paper/main.tex against the report, and compiles the IEEE-format manuscript.
---

# Paper build

Every number in `paper/main.tex` must come from `results/rigor_report.json`.

```bash
uv run govbench-rigor                          # results/rigor_report.json + paper/tables/rigor_*.{csv,tex}
uv run python -m scripts.make_paper_figures    # paper/figures/*.pdf from the report
uv run python -m scripts.check_paper_numbers   # fails if the paper states a number the report does not contain
uv run python scripts/build_paper.py           # compiles with the bundled tectonic into paper_out/main.pdf
```

Rules:
- Do not cite a reference that has not been checked against arXiv, a DOI resolver or the publisher.
- Do not report the columns listed under `integrity.synthetic_columns` in the report; they were not measured.
- State limitations (single model, sample size, no clinician validation yet) wherever results are summarised.
