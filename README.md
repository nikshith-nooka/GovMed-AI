# GovBench-Clinical

**A measurement-audited benchmark and decision-support workbench for multi-agent clinical AI governance.**

GovBench-Clinical runs clinical cases through a multi-agent LLM pipeline (research → diagnosis → optional governance
checks) and measures what each governance layer (grounding verifier, safety validator, consistency checker,
simulated attending review) actually changes. It also ships a clinician-facing workspace that shows what was checked,
what was **not** checked, and what needs a human decision.

> Decision support only. Outputs are AI-generated, not clinician-reviewed, and must not replace clinical judgment.

---

## Measured results (750 stored runs, 150 cases × 5 variants, Llama-3.2-11B on NVIDIA NIM)

Regenerate with `uv run govbench-rigor`; details in [RESEARCH_ROADMAP.md](RESEARCH_ROADMAP.md) and the in-app
**Research Findings** page.

| Finding | Evidence |
|---|---|
| Open-loop governance does not change decisions | Primary diagnosis differs from the ungoverned baseline in ≤ 2.7% of cases; no accuracy difference (paired Wilcoxon, p ≥ 0.18) |
| The "Audit Paradox" is a scoring artifact | 94–96% of each governed variant's quality drop comes from penalizing its own detectors |
| LLM safety alerts do not discriminate errors | The safety validator alerts on 100% of runs; every governance signal detects misdiagnosis at AUROC 0.40–0.56 (0.5 = chance) |
| Automatic accuracy was inflated | Reported 0.739; after recovering unparsed outputs and fixing substring scoring, 0.293 (0.38 on the 71 cases with real diagnosis labels) |
| Model confidence is uncalibrated | Expected calibration error 0.29 |
| Latency | End-to-end median 45 s (no checks) to 111 s (all checks) on the benchmark model |

Some columns in `results/benchmark_results.db` (`uncertainty_jru`, `llm_judge_score`, `risk_adjusted_quality`,
`governance_efficiency_factor`, `hitl_minutes`) were filled by a post-hoc script rather than measured. The analysis
detects and excludes them; the original run database is `results/benchmark_results.db.bak`.

**Known limitations:** one model; 79 of 150 gold labels are templated titles rather than diagnoses; no clinician
validation yet (collect it with the in-app Clinician Review tool). See the roadmap for the path to publication.

---

## Pipeline

```
Research ─► Diagnosis ─┬─► Consistency checker ─┐
                       ├─► Grounding verifier ──┼─► Simulated attending review ─► (closed loop: revise diagnosis) ─► Report
                       └─► Safety validator ────┘
```

| Level | Variant | Checks |
|---|---|---|
| G0 | V1 | none |
| G1 | V2 | grounding verifier |
| G2 | V3 | simulated attending review (an LLM, not a human) |
| G3 | V4 | safety validator |
| G4 | V5 | all of the above + consistency checker |

The independent checks run in parallel. With **closed loop** on, a serious concern (hallucinated claim, HIGH/CRITICAL
safety flag, severe inconsistency, or a revision request) sends the diagnosis back for one revision.

---

## Quick start

```bash
uv sync --extra dev
cp .env.example .env          # add GROQ_API_KEY(S) / NVIDIA_API_KEY / GEMINI_API_KEY for live runs
cd client && npm install && npm run build && cd ..
uv run uvicorn src.api.server:app --port 8000
# open http://localhost:8000
```

Without an API key the app runs in a clearly labelled demo mode (a keyword-based generator, not a real analysis).
Live calls never fall back to simulated output silently: a failed live call returns an error.

Docker: `docker compose up govbench-dashboard` (serves the app on port 8000).

---

## The app

| Page | What it does |
|---|---|
| **Clinician Workspace** | Analyze a patient with a live model. Physician view (differential, alerts by severity, what was and was not checked, what the checks changed) and clinical-assistant view (escalation list, SBAR handoff, task checklist). Live per-agent progress. |
| **Clinician Review** | Blinded rating of stored AI outputs (diagnosis verdict, quality 1–5, each alert real or not). Produces alert precision and scorer–clinician agreement. |
| **Research Findings** | The measured analysis, integrity audit and limitations. |
| **Benchmark Analytics** | Variant comparison, cost and latency, governance-signal AUROC, paired statistics. |
| **Experiments** | Run benchmark cases at chosen check levels through the real pipeline; scored against gold, saved to `results/ui_experiments.db`, CSV export. |
| **Clinical Cases Dataset** | Browse and filter the 150 cases; open any case in the Workspace. |
| **Agent Pipeline** | Agents per level with measured latency and tokens. |
| **Reports** | LaTeX tables generated from the measured analysis; CSV of stored runs. |

### API

| Endpoint | Purpose |
|---|---|
| `POST /api/jobs/run-case`, `GET /api/jobs/{id}` | Interactive run with live per-agent progress |
| `POST /api/run-custom-case` | Same run, synchronous |
| `POST /api/experiments/run-case`, `GET /api/experiments/runs` | Scored runs on benchmark cases |
| `GET /api/research/findings` | Measured analysis (`results/rigor_report.json`) |
| `GET /api/reviews/queue`, `POST /api/reviews`, `GET /api/reviews/summary` | Clinician validation |
| `GET /api/runs`, `/api/cases`, `/api/stats`, `/api/providers`, `/api/health` | Data and status |
| `GET /api/reports/latex`, `/api/reports/csv` | Exports |

---

## Benchmarking and analysis

```bash
# Full benchmark (strict live mode: failed calls skip the run instead of logging simulated output)
uv run python -m scripts.run_full_benchmark --total-cases 150 --provider nvidia --variant-workers 1
uv run python -m scripts.run_full_benchmark --total-cases 150 --provider nvidia --variant-workers 1 --closed-loop

# Measured re-analysis -> results/rigor_report.json and paper/tables/rigor_*.{csv,tex}
uv run govbench-rigor

# Concurrency smoke test
uv run python -m scripts.load_test --requests 200 --concurrency 16
```

## Tests

```bash
uv run pytest
```

## Project layout

```
src/
  agents/        research, diagnosis (+ revision), verifier, safety validator, HITL simulator, consistency, report
  pipeline/      orchestrator (variants, parallel checks, closed loop, progress callbacks)
  llm/           unified client (Groq, NVIDIA NIM, Gemini, OpenRouter, demo), pooled-key rotation, strict live mode
  evaluation/    scorer, LLM judge, statistics
  analysis/      rigor.py (measured re-analysis), ablation, frontier
  clinical/      decision_support.py (clinician-facing output)
  api/           FastAPI server (also serves client/dist)
  telemetry/     SQLite storage, run metrics
scripts/         benchmark runner, rigor analysis, load test, figures, exports
client/          React + Vite app
benchmarks/      curated_sample.json (150 cases)
results/         benchmark database and analysis report
paper/           manuscript draft (being revised to the measured results; see roadmap)
tests/
```

## License

MIT (declared in `pyproject.toml`).
