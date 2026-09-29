#!/usr/bin/env python3
"""Measurement-valid re-analysis of the benchmark database.

Writes results/rigor_report.json (consumed by the dashboard) and paper-ready
tables under paper/tables/rigor_*.{csv,tex}.

    uv run python -m scripts.run_rigor_analysis
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.rigor import RigorousAnalysis

TABLES = {
    "variants": ("Measured variant summary (valid-gold accuracy, detector-neutral quality, end-to-end latency).",
                 ["variant_id", "accuracy_valid_gold", "detector_neutral_quality", "reported_quality",
                  "tokens_mean", "e2e_latency_p50_s", "e2e_latency_p95_s", "diagnosis_changed_vs_v1_pct"]),
    "paired_tests": ("Paired differences vs. V1 with bootstrap 95\\% CI, Wilcoxon signed-rank p (raw and "
                     "Holm-adjusted) and rank-biserial effect size.",
                     ["metric", "comparison", "n_pairs", "mean_diff", "ci95_low", "ci95_high", "wilcoxon_p",
                      "wilcoxon_p_holm", "rank_biserial"]),
    "accuracy_tests": ("Exact McNemar test on paired binary correctness vs. V1 (raw and Holm-adjusted p), "
                       "accuracy difference and Cohen's $h$ with bootstrap 95\\% CI.",
                       ["comparison", "n_pairs", "only_v1_correct", "only_variant_correct", "accuracy_diff",
                        "accuracy_diff_ci95_low", "accuracy_diff_ci95_high", "cohens_h", "mcnemar_exact_p",
                        "mcnemar_exact_p_holm"]),
    "alert_discrimination": ("Governance signals as detectors of misdiagnosis (accuracy $<$ 0.5).",
                             ["signal", "variant_id", "n", "fire_rate", "sensitivity", "false_positive_rate",
                              "precision", "auroc"]),
    "latency": ("Per-agent latency (seconds) across all runs.",
                ["agent", "calls", "mean_s", "p95_s", "max_s", "mean_share_of_run", "mean_tokens"]),
}


def _finite(obj):
    """JSON has no NaN/Infinity (the API would refuse to serve it); numpy scalars become Python numbers."""
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {str(k): _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def write_table(rows, name: str, out_dir: Path) -> None:
    caption, cols = TABLES[name]
    if not rows:
        return
    df = pd.DataFrame(rows).reindex(columns=cols)
    df.to_csv(out_dir / f"rigor_{name}.csv", index=False)
    latex = df.to_latex(index=False, float_format="%.3f", na_rep="--", escape=True)
    (out_dir / f"rigor_{name}.tex").write_text(
        "\\begin{table}[t]\n\\centering\n\\small\n" + latex
        + f"\\caption{{{caption}}}\n\\label{{tab:rigor_{name}}}\n\\end{{table}}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="results/benchmark_results.db")
    parser.add_argument("--cases-path", default="benchmarks/curated_sample.json,benchmarks/medqa_300.json",
                        help="Comma-separated benchmark case files used to rescore runs (missing ones are skipped)")
    parser.add_argument("--reference-db", default="results/benchmark_results.db.bak",
                        help="Original run DB used to detect post-hoc (synthetic) columns")
    parser.add_argument("--out", default="results/rigor_report.json")
    parser.add_argument("--tables-dir", default="paper/tables")
    parser.add_argument("--clinician-protocol", default="benchmarks/clinician_protocol_50.json",
                        help="Write the fixed blinded stratified review set here ('' to skip)")
    parser.add_argument("--protocol-n", type=int, default=50)
    parser.add_argument("--protocol-seed", type=int, default=42)
    args = parser.parse_args()

    warnings.filterwarnings("ignore", category=RuntimeWarning)
    analysis = RigorousAnalysis(args.db_path, args.cases_path, args.reference_db)
    report = analysis.report()
    if args.clinician_protocol:
        protocol = analysis.clinician_protocol(n=args.protocol_n, seed=args.protocol_seed)
        Path(args.clinician_protocol).parent.mkdir(parents=True, exist_ok=True)
        Path(args.clinician_protocol).write_text(json.dumps(_finite(protocol), indent=2) + "\n", encoding="utf-8")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(_finite(report), indent=2, default=str, allow_nan=False), encoding="utf-8")
    tables_dir = Path(args.tables_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_table(report["variants"], "variants", tables_dir)
    write_table(report["paired_tests"], "paired_tests", tables_dir)
    write_table(report["accuracy_tests"], "accuracy_tests", tables_dir)
    write_table(report["alert_discrimination"], "alert_discrimination", tables_dir)
    write_table(report["latency_by_agent"], "latency", tables_dir)

    print(f"Analyzed {report['n_runs_analyzed']} runs over {report['n_cases']} cases ({', '.join(report['models'])})\n")
    for finding in report["headline_findings"]:
        print(f"  * {finding}")
    print(f"\nReport: {args.out}\nTables: {tables_dir}/rigor_*.{{csv,tex}}")
    if args.clinician_protocol:
        print(f"Clinician protocol ({args.protocol_n} blinded runs): {args.clinician_protocol}")


if __name__ == "__main__":
    main()
