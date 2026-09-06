---
name: paper-compiler
description: Synchronizes empirical benchmark metrics with LaTeX tables and builds the academic paper (paper/main.tex) for IEEE Transactions on Medical Informatics.
---

# Academic Paper Sync & Compilation Skill

Use this skill to update empirical results in `paper/main.tex` and compile the manuscript into a publication-ready PDF.

## 1. Export Empirical Benchmark Metrics
To dump the latest statistical tables, Pareto frontier data, and LaTeX macros from `results/benchmark_results.db`:
```bash
.venv/bin/python scripts/export_results.py
```

## 2. LaTeX Build Workflow
From the `paper/` directory:
```bash
cd paper
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

## 3. Paper Structure Guidelines
- **Target Journal**: IEEE Transactions on Medical Informatics (IEEE TMI / TBME).
- **Core Contribution**: The first quantitative evaluation of the marginal cost-effectiveness, latency overhead, and safety intervention rate of multi-agent governance layers in clinical reasoning.
- **Key Phenomenon Documented**: The *"Audit Paradox"* (governed pipelines honestly surface and penalize ungrounded diagnoses and contraindicated prescriptions that blind baseline pipelines ignore).
