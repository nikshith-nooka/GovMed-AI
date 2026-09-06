---
name: governance-benchmark
description: Executes, monitors, and analyzes the multi-agent clinical governance benchmark across MedQA, PubMedQA, and MedDialog using NVIDIA NIM or Groq.
---

# Clinical Governance Benchmark Runner Skill

Use this skill to run or monitor the full 750-case ablation benchmark across the 5 clinical governance configurations.

## 1. Quick Launch Commands
- **Full 150-Case (750-Run) Benchmark (Parallel 5-Worker Mode)**:
  ```bash
  .venv/bin/python scripts/run_full_benchmark.py --provider nvidia --source 50_each --total-cases 150 --workers 5
  ```
- **Single-Case Live Diagnostics**:
  ```bash
  .venv/bin/python run_benchmark.py --provider nvidia --cases 1 --variant full_governance
  ```
- **Inspect Live Progress**:
  ```bash
  .venv/bin/python scripts/compare_metrics.py
  ```

## 2. The 5 Governance Configurations (V1 to V5)
1. **V1: Baseline (Ungoverned)** — 3-agent core (Triage, Research, Diagnostic).
2. **V2: Verifier Governance** — Adds Verifier / Fact-Checker agent with reflection loop.
3. **V3: HITL Simulator Governance** — Adds Risk-Calibrated Human-in-the-Loop triage simulator.
4. **V4: Safety Validator Governance** — Adds automated pharmacology, contraindication & dosing checks.
5. **V5: Full Governance (Defense-in-Depth)** — Complete 6-agent cascade with all governance layers.

## 3. Dataset Interleaving & Split
- **Source**: `50_each` (150 total cases: 50 MedQA, 50 PubMedQA, 50 MedDialog).
- **Execution Strategy**: Round-robin interleaved across datasets with intra-case caching to minimize redundant LLM token spend.
- **Persistence**: Checkpointed into `results/benchmark_results.db`. Interrupted runs automatically resume without re-running completed cases.
