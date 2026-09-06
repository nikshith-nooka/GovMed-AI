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
- **Web App**: Streamlit on port `8501` (`.venv/bin/streamlit run app.py`)
- **Database**: SQLite at `results/benchmark_results.db` (Schema: `runs`, `agent_steps`)

## 2. Directory Architecture Map
- `src/agents/`: Multi-agent pipeline modules (Triage, Research, Diagnostic, Verifier, Safety, Synthesis).
- `src/pipeline/`: Multi-tier governance orchestrator (`orchestrator.py`) supporting V1–V5 ablations with intra-case caching.
- `src/llm/`: Unified client supporting NVIDIA NIM, Groq, Google Gemini, and OpenRouter.
- `src/data/`: Clinical dataset loaders for MedQA-USMLE, PubMedQA, and MedDialog (ChatDoctor).
- `src/evaluation/`: Multi-dimensional evaluation scorers (accuracy, evidence grounding, differential completeness, safety).
- `src/telemetry/`: SQLite persistence engine with thread-safe connection pooling and retry handlers.
- `scripts/`: Benchmark runners (`run_full_benchmark.py`), data exporters (`export_results.py`), and metric comparisons.
- `paper/`: IEEE Transactions on Medical Informatics publication LaTeX source (`main.tex`, `references.bib`).

## 3. Standard Verification Commands
- Check virtual environment: `.venv/bin/python --version`
- Run unit test suite: `.venv/bin/pytest tests/`
- Query active database run count: `.venv/bin/python -c "import sqlite3; c = sqlite3.connect('results/benchmark_results.db'); print('Runs:', c.execute('SELECT COUNT(*) FROM runs').fetchone()[0])"`
