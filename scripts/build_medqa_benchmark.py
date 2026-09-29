#!/usr/bin/env python3
"""Freeze a seeded MedQA-USMLE sample with an objective 4-option answer key.

Samples ``--n`` items (default 300, seed 42) from the original MedQA-USMLE 4-option
test split (Jin et al., 2021; HF mirror GBaker/MedQA-USMLE-4-options) and writes them in
the pipeline case schema, so the benchmark runner can use them directly:

    uv run python -m scripts.build_medqa_benchmark
    uv run govbench --benchmark benchmarks/medqa_300.json --total-cases 300

A provenance sidecar (``<out>.meta.json``) records the dataset id, split size, seed,
sampled indices and a content hash so the sample can be verified later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.loader import (  # noqa: E402
    MEDQA_4OPT_DATASET,
    MEDQA_SOURCE,
    OPTION_KEYS,
    ClinicalDatasetLoader,
    seeded_sample_indices,
)

REQUIRED_FIELDS = ("id", "case_id", "question", "options", "answer", "answer_idx", "answer_text",
                   "gold_diagnosis", "source", "split")


def validate_case(case: Dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if not case.get(f)]
    if missing:
        raise ValueError(f"{case.get('id')}: missing {missing}")
    if tuple(sorted(case["options"])) != OPTION_KEYS:
        raise ValueError(f"{case['id']}: expected options {OPTION_KEYS}, got {sorted(case['options'])}")
    if case["answer_idx"] not in case["options"] or case["options"][case["answer_idx"]] != case["answer_text"]:
        raise ValueError(f"{case['id']}: answer key does not match options")


def build(population: List[Dict[str, Any]], n: int, seed: int) -> List[Dict[str, Any]]:
    """Pure sampling step (no network): used by the CLI and by the tests."""
    indices = seeded_sample_indices(len(population), n, seed)
    cases = [population[i] for i in indices]
    for case in cases:
        validate_case(case)
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("duplicate case ids in sample")
    return cases


def content_hash(cases: List[Dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split", default="test")
    parser.add_argument("--out", default="benchmarks/medqa_300.json")
    args = parser.parse_args(argv)

    population = ClinicalDatasetLoader().load_medqa_usmle4(split=args.split)
    cases = build(population, args.n, args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    answer_dist = {k: sum(c["answer_idx"] == k for c in cases) for k in OPTION_KEYS}
    meta = {
        "source": MEDQA_SOURCE,
        "hf_dataset": MEDQA_4OPT_DATASET,
        "split": args.split,
        "split_size": len(population),
        "n": len(cases),
        "seed": args.seed,
        "sampler": "random.Random(seed).sample(range(split_size), n), sorted",
        "source_indices": [c["source_index"] for c in cases],
        "answer_distribution": answer_dist,
        "sha256": content_hash(cases),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} MedQA-USMLE cases (seed {args.seed}, split {args.split}, "
          f"{len(population)} available) to {out}")
    print(f"Answer key distribution: {answer_dist}  sha256={meta['sha256'][:16]}")


if __name__ == "__main__":
    main()
