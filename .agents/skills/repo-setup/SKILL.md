---
name: repo-setup
description: Bootstraps repository context, environment dependencies, Python virtualenv tooling, and architecture maps for GovBench-Clinical.
---

# GovBench-Clinical Repository Setup & Context Skill

Use this skill when onboarding, verifying dependencies, or inspecting the GovBench-Clinical architecture.

## 1. Environment & Runtime Context
- **Python Environment**: `.venv/bin/python` (Python 3.11+ managed with `uv` or `pip`)
- **Package Manager**: `uv` / `pip` (defined in `pyproject.toml`)
- **Active Model Provider**: NVIDIA NIM (`DEFAULT_LLM_PROVIDER=nvidia`, Model: `meta/llama-3.2-11b-vision-instruct`)
- **Web App**: FastAPI + React on port `8000` (`uv run uvicorn src.api.server:app --port 8000`; build the client first with `npm run build` in `client/`)
- **Database**: SQLite at `results/benchmark_results.db` (Schema: `runs`, `agent_steps`)

## 2. Directory Architecture Map
- `src/agents/`: Research, diagnosis (and revision), grounding verifier, safety validator, attending simulator, consistency checker, report.
- `src/pipeline/`: Multi-tier governance orchestrator (`orchestrator.py`) supporting V1–V5 ablations with intra-case caching.
- `src/llm/`: Unified client supporting NVIDIA NIM, Groq, Google Gemini, and OpenRouter.
- `src/data/`: Clinical dataset loaders for MedQA-USMLE, PubMedQA, and MedDialog (ChatDoctor).
- `src/evaluation/`: Scorer (exact option scoring for MedQA, whole-word matching otherwise), cross-model LLM judge, statistics.
- `src/analysis/`: Measured re-analysis (`rigor.py`): integrity audit, paired tests, McNemar + Holm, power, AUROC, calibration.
- `src/clinical/`: Decision support, deterministic contraindication rules, PHI detection.
- `src/telemetry/`: SQLite run storage, run metrics and persistent jobs.
- `scripts/`: Benchmark runner, MedQA builder, re-analysis, paper figures, paper number check, injection eval, load test.
- `paper/`: IEEE conference-format manuscript (`main.tex`, inline verified bibliography) and generated tables and figures.

## 3. Standard Verification Commands
- Check virtual environment: `.venv/bin/python --version`
- Run unit test suite: `uv run pytest -q`
- Query active database run count: `.venv/bin/python -c "import sqlite3; c = sqlite3.connect('results/benchmark_results.db'); print('Runs:', c.execute('SELECT COUNT(*) FROM runs').fetchone()[0])"`
