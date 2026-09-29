#!/usr/bin/env python3
"""Measurement-valid re-analysis of the benchmark database.

Writes results/rigor_report.json (consumed by the dashboard) and paper-ready
tables under paper/tables/rigor_*.{csv,tex}.

    uv run python -m scripts.run_rigor_analysis
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import pandas as pd

from src.analysis.rigor import RigorousAnalysis

TABLES = {
    "variants": ("Measured variant summary (valid-gold accuracy, detector-neutral quality, end-to-end latency).",
                 ["variant_id", "accuracy_valid_gold", "detector_neutral_quality", "reported_quality",
                  "tokens_mean", "e2e_latency_p50_s", "e2e_latency_p95_s", "diagnosis_changed_vs_v1_pct"]),
    "paired_tests": ("Paired differences vs. V1 with bootstrap 95\\% CI and Wilcoxon signed-rank p.",
                     ["metric", "comparison", "n_pairs", "mean_diff", "ci95_low", "ci95_high", "wilcoxon_p"]),
    "alert_discrimination": ("Governance signals as detectors of misdiagnosis (accuracy $<$ 0.5).",
                             ["signal", "variant_id", "n", "fire_rate", "sensitivity", "false_positive_rate",
                              "precision", "auroc"]),
    "latency": ("Per-agent latency (seconds) across all runs.",
                ["agent", "calls", "mean_s", "p95_s", "max_s", "mean_share_of_run", "mean_tokens"]),
}


def write_table(rows, name: str, out_dir: Path) -> None:
    caption, cols = TABLES[name]
    df = pd.DataFrame(rows)[cols]
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
    parser.add_argument("--cases-path", default="benchmarks/curated_sample.json")
    parser.add_argument("--reference-db", default="results/benchmark_results.db.bak",
                        help="Original run DB used to detect post-hoc (synthetic) columns")
    parser.add_argument("--out", default="results/rigor_report.json")
    parser.add_argument("--tables-dir", default="paper/tables")
    args = parser.parse_args()

    warnings.filterwarnings("ignore", category=RuntimeWarning)
    report = RigorousAnalysis(args.db_path, args.cases_path, args.reference_db).report()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    tables_dir = Path(args.tables_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_table(report["variants"], "variants", tables_dir)
    write_table(report["paired_tests"], "paired_tests", tables_dir)
    write_table(report["alert_discrimination"], "alert_discrimination", tables_dir)
    write_table(report["latency_by_agent"], "latency", tables_dir)

    print(f"Analyzed {report['n_runs_analyzed']} runs over {report['n_cases']} cases ({', '.join(report['models'])})\n")
    for finding in report["headline_findings"]:
        print(f"  * {finding}")
    print(f"\nReport: {args.out}\nTables: {tables_dir}/rigor_*.{{csv,tex}}")


if __name__ == "__main__":
    main()
