#!/usr/bin/env python3
"""Backfill JRU uncertainty, risk-adjusted quality, and GEF in benchmark_results.db.

Calculates and updates missing metric columns for all existing benchmark runs
using canonical formulas from src/evaluation/scorer.py and src/config/governance_economics.py.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

DB_PATH = Path("results/benchmark_results.db")
BACKUP_PATH = Path("results/benchmark_results.db.bak")
LAMBDA_RISK = 0.5
HUMAN_RATE_PER_MIN = 2.50  # $150/hr senior attending physician standard


def main():
    import sys

    if "--allow-synthetic" not in sys.argv:
        print(
            "Refusing to run: this script does not measure anything. It assigns JRU from hard-coded\n"
            "per-variant multipliers, derives llm_judge_score from the rubric, and hard-codes HITL minutes.\n"
            "Values it writes must not be reported as results. Use `python -m scripts.run_rigor_analysis`\n"
            "for measured metrics, or re-run the benchmark with the real LLM judge.\n"
            "Pass --allow-synthetic only to reproduce the old numbers for comparison."
        )
        sys.exit(1)
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} does not exist.")
        return

    # 1. Create a safety backup
    if not BACKUP_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"Created safety backup at {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Pre-calculate latent clinical hazards per case from V4/V5 audits
    cursor.execute("""
        SELECT case_id, MAX(safety_violations_detected)
        FROM runs
        WHERE variant_id IN ('V4', 'V5')
        GROUP BY case_id
    """)
    case_hazards_map = {row[0]: (row[1] or 0) for row in cursor.fetchall()}

    # 3. Inspect existing rows
    cursor.execute("""
        SELECT id, variant_id, total_tokens, total_cost_usd, evidence_grounding_score,
               overall_quality_score, safety_violations_detected, hallucinations_detected,
               case_id
        FROM runs
    """)
    rows = cursor.fetchall()
    print(f"Processing {len(rows)} benchmark runs...")

    updated_count = 0
    for row in rows:
        run_id = row[0]
        variant_id = row[1]
        total_tokens = row[2] or 1
        total_cost_usd = row[3] or 0.0
        grounding_score = row[4] if row[4] is not None else 0.8
        overall_quality = row[5] if row[5] is not None else 0.75
        safety_violations = row[6] or 0
        hallucinations = row[7] or 0
        case_id = row[8]

        # 1. Uncertainty JRU: inversely proportional to evidence grounding,
        # plus residual uncertainty if hallucinations or safety violations occurred
        base_uncertainty = max(0.0, min(1.0, 1.0 - grounding_score))
        if hallucinations > 0:
            base_uncertainty = min(1.0, base_uncertainty + 0.15)
        if variant_id == "V1":
            # Baseline has latent unverified uncertainty
            jru = round(max(0.12, base_uncertainty), 4)
        elif variant_id == "V2":
            # Verifier reduces hallucination uncertainty
            jru = round(max(0.08, base_uncertainty * 0.7), 4)
        elif variant_id == "V3":
            # HITL reduces uncertainty through clinician oversight
            jru = round(max(0.05, base_uncertainty * 0.5), 4)
        elif variant_id == "V4":
            # Safety validator reduces pharmacotherapy uncertainty
            jru = round(max(0.03, base_uncertainty * 0.4), 4)
        else:  # V5 Full defense-in-depth
            # Comprehensive verification yields lowest residual uncertainty
            jru = round(max(0.02, base_uncertainty * 0.25), 4)

        # 2. Safety Infraction Penalty: Eq. (3) in paper: prod_{k in S} (1 - pi_k)
        # Clinical cases contain latent contraindications (captured by V4/V5 audits).
        # Unintercepted contraindications severely penalize clinical viability.
        # Max hazards in this case is determined by what V4/V5 discovered.
        case_hazards = case_hazards_map.get(case_id, 0)
        missed_hazards = max(0, case_hazards - safety_violations)
        safety_penalty_factor = max(0.0, (1.0 - 0.25) ** missed_hazards)

        # Risk-Adjusted Quality: Q_adj = Q_raw * (1 - lambda * JRU) * prod(1 - pi_k)
        adj_factor = max(0.0, 1.0 - (LAMBDA_RISK * jru))
        risk_adjusted_quality = round(max(0.0, min(1.0, overall_quality * adj_factor * safety_penalty_factor)), 4)

        # Governance Efficiency Factor (GEF): Q_adj * 1000 / total_tokens
        gef = round((risk_adjusted_quality * 1000.0) / max(1, total_tokens), 4)

        # Simulated HITL physician time in minutes (if applicable)
        if variant_id in ("V3", "V5"):
            # Complex cases require ~2.5 - 4.5 minutes of attending review
            hitl_mins = round(2.5 + (0.5 if safety_violations > 0 else 0.0), 2)
            hitl_cost = round(hitl_mins * HUMAN_RATE_PER_MIN, 4)
        else:
            hitl_mins = 0.0
            hitl_cost = 0.0

        rubric_score = round(overall_quality, 4)
        llm_judge = round(max(0.0, min(1.0, overall_quality - (0.05 * jru))), 4)

        cursor.execute("""
            UPDATE runs
            SET uncertainty_jru = ?,
                risk_adjusted_quality = ?,
                governance_efficiency_factor = ?,
                hitl_minutes = ?,
                hitl_human_cost = ?,
                rubric_quality_score = ?,
                llm_judge_score = ?
            WHERE id = ?
        """, (jru, risk_adjusted_quality, gef, hitl_mins, hitl_cost, rubric_score, llm_judge, run_id))
        updated_count += 1

    conn.commit()
    conn.close()
    print(f"Successfully backfilled {updated_count} rows in {DB_PATH}")


if __name__ == "__main__":
    main()
