---
name: governance-benchmark
description: Runs and analyses the GovBench-Clinical governance benchmark (G0-G4, open and closed loop) on the MedQA answer-key benchmark or the 150-case audited set.
---

# Governance benchmark

## Levels
G0 / V1 no checks · G1 / V2 grounding verifier · G2 / V3 simulated attending (an LLM) · G3 / V4 safety validator ·
G4 / V5 all checks plus the consistency checker. Closed-loop variants carry a `-CL` suffix; a blocking finding
triggers one revision, after which the enabled checks re-run on the revised diagnosis. Research and diagnosis are
computed once per case and shared by every variant.

## Run
```bash
# Always estimate first
uv run govbench --benchmark benchmarks/medqa_300.json --provider groq --judge-provider nvidia \
    --loop-modes open,closed --seed 42 --db-path results/medqa_v2.db --dry-run
# Then run (resumes automatically; variants run one at a time for clean latency)
uv run govbench --benchmark benchmarks/medqa_300.json --provider groq --judge-provider nvidia \
    --loop-modes open,closed --seed 42 --db-path results/medqa_v2.db
```

Rules:
- The judge must be a different model from the generator; same-model verdicts are rejected.
- The offline demo provider is refused; a failed live call skips the run rather than storing simulated output.
- Write new experiments to a new DB; `results/benchmark_results.db` is the audited 750-run record.

## Analyse
```bash
uv run python -m scripts.run_rigor_analysis --db-path results/medqa_v2.db --cases-path benchmarks/medqa_300.json \
    --reference-db none --out results/rigor_report_medqa.json --tables-dir paper/tables/medqa --clinician-protocol ""
```
