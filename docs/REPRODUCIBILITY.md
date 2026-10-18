# Reproducibility

## Environment
- Python 3.11+, [uv](https://docs.astral.sh/uv/). Dependencies are pinned in `uv.lock`.
- Node.js 20.19+ for the client.
- A live provider key in `.env` (`NVIDIA_API_KEY(S)`, `GROQ_API_KEY(S)`, `GEMINI_API_KEY` or `OPENROUTER_API_KEY`) is needed for
  new runs only. Re-analysis of stored runs needs no key and makes no network call.

```bash
uv sync --extra dev
cp .env.example .env            # add keys only if you will generate new runs
(cd client && npm install && npm run build)
uv run uvicorn src.api.server:app --port 8000      # open http://localhost:8000
```

## What each stored run records
`runs` row: case id, variant id (`-CL` = closed loop), model, provider, per-step model and temperature
(`temperature_config`), seed and `provider_seed_applied`, judge provider/model, token totals, latency, raw JSON of
every agent output (`raw_outputs_json`, including `timing` for runs after 2026-10-10), parse failures, revision
triggers, initial and final diagnosis, scoring mode and parse status. `agent_steps` holds one row per model call with
tokens and latency.

Dataset version: `benchmarks/medqa_300.meta.json` (source, HF dataset id, split, split size, seed, sampler, indices).

## Reproduce the analysis from stored runs (no API calls)

```bash
# MedQA closed-loop experiment (1,800 runs)
uv run python -m scripts.run_rigor_analysis --db-path results/medqa_fast.db --cases-path benchmarks/medqa_300.json \
    --reference-db none --out results/rigor_report_medqa.json --tables-dir paper/tables/medqa --clinician-protocol ""
# Open-loop 150-case experiment (750 runs)
uv run govbench-rigor
# Figures, paper-number check, PDF
uv run govbench-figures
uv run python -m scripts.check_paper_numbers
uv run python scripts/build_paper.py
```

Bootstrap CIs use fixed seeds, so these commands give identical numbers on every run.

## Regenerate runs (costs tokens; estimate first)

```bash
uv run python -m scripts.build_medqa_benchmark          # rebuilds benchmarks/medqa_300.json from the HF split
uv run govbench --benchmark benchmarks/medqa_300.json --provider nvidia --loop-modes open,closed \
    --seed 42 --no-report --db-path results/medqa_v2.db --dry-run
uv run govbench --benchmark benchmarks/medqa_300.json --provider nvidia --loop-modes open,closed \
    --seed 42 --no-report --db-path results/medqa_v2.db
```

- Run `open` before `closed` into the **same** `--db-path`. The closed-loop pass then reuses each case's stored
  Research + Diagnosis (`load_shared_upstream`), which keeps the comparison paired (AUD-01).
- The paired rerun was produced this way: copy `results/medqa_fast.db` to `results/medqa_paired.db`, delete the `-CL`
  rows (and their `agent_steps`) **in the copy**, then run
  `uv run govbench --benchmark benchmarks/medqa_300.json --total-cases 300 --provider nvidia --loop-modes closed
  --variants verifier,hitl,safety,full_governance --seed 42 --no-report --workers 8 --db-path results/medqa_paired.db`.
  Re-running the same command retries any run that failed at the provider.
- Analyse it with `run_rigor_analysis --db-path results/medqa_paired.db ... --out results/rigor_report_medqa_paired.json
  --tables-dir paper/tables/medqa_paired`.
- Sampling is not bit-reproducible. Temperatures are 0.1/0.2, and the provider treats the `seed` as best effort. Measured
  run-to-run instability is in `resampling_stability`: 20–25% of answers change on a re-sample.
- `--resume` (default) skips stored (case, variant, model) runs. A failed live call skips the run and never stores simulated
  output.

## Integrity guarantees
- The runner only appends to raw databases, and the analysis only reads them.
  `results/benchmark_results.db.bak` is the original pre-backfill database.
- Every number in `paper/main.tex` is checked against the reports (`check_paper_numbers.py`: 168/168 on 2026-10-18).
