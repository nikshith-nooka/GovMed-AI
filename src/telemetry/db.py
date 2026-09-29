"""SQLite database manager for persistent benchmark logging and analysis."""

from __future__ import annotations

import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from src.telemetry.metrics import PipelineRunResult, AgentStepLog


class BenchmarkDB:
    """Manages SQLite storage for clinical benchmark runs and agent steps."""

    MEASUREMENT_COLUMNS = {
        "detector_neutral_quality": "REAL",
        "gold_label_valid": "INTEGER",
        "jru_source": "TEXT",
        "parse_failures": "TEXT",
        "closed_loop": "INTEGER",
        "revision_applied": "INTEGER",
        "initial_primary_diagnosis": "TEXT",
        "revision_triggers": "TEXT",
    }

    def __init__(self, db_path: str = "results/benchmark_results.db"):
        self.db_path = db_path
        Path(os.path.dirname(self.db_path)).mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=60.0)

    def _ensure_column(self, cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
        """Add a telemetry column to databases created before a schema extension."""
        columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Runs summary table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    variant_name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    total_prompt_tokens INTEGER,
                    total_completion_tokens INTEGER,
                    total_tokens INTEGER,
                    total_latency_ms REAL,
                    total_cost_usd REAL,
                    primary_diagnosis TEXT,
                    diagnostic_accuracy_score REAL,
                    differential_completeness_score REAL,
                    evidence_grounding_score REAL,
                    safety_score REAL,
                    overall_quality_score REAL,
                    llm_judge_score REAL,
                    rubric_quality_score REAL,
                    uncertainty_jru REAL,
                    governance_efficiency_factor REAL,
                    risk_adjusted_quality REAL,
                    hitl_minutes REAL,
                    hitl_human_cost REAL,
                    report_quality_score REAL,
                    hallucinations_detected INTEGER,
                    safety_violations_detected INTEGER,
                    hitl_decision TEXT,
                    governance_flags TEXT,
                    raw_outputs_json TEXT,
                    timestamp REAL
                )
                """
            )
            self._ensure_column(cursor, "runs", "llm_judge_score", "REAL")
            self._ensure_column(cursor, "runs", "rubric_quality_score", "REAL")
            self._ensure_column(cursor, "runs", "uncertainty_jru", "REAL")
            self._ensure_column(cursor, "runs", "governance_efficiency_factor", "REAL")
            self._ensure_column(cursor, "runs", "risk_adjusted_quality", "REAL")
            self._ensure_column(cursor, "runs", "hitl_minutes", "REAL")
            self._ensure_column(cursor, "runs", "hitl_human_cost", "REAL")
            self._ensure_column(cursor, "runs", "report_quality_score", "REAL")
            for column, definition in self.MEASUREMENT_COLUMNS.items():
                self._ensure_column(cursor, "runs", column, definition)

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS clinician_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    case_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    reviewer_role TEXT,
                    diagnosis_verdict TEXT,
                    quality_rating INTEGER,
                    alert_ratings TEXT,
                    missed_hazards TEXT,
                    comments TEXT,
                    created_at REAL,
                    UNIQUE(run_id, reviewer_id)
                )
                """
            )

            # Granular agent execution trace table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    case_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    latency_ms REAL,
                    cost_usd REAL,
                    output_preview TEXT,
                    flags TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                )
                """
            )
            conn.commit()

    def log_run(self, result: PipelineRunResult) -> int:
        """Logs a completed pipeline run and its per-agent execution traces."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO runs (
                    case_id, variant_id, variant_name, model, provider,
                    total_prompt_tokens, total_completion_tokens, total_tokens,
                    total_latency_ms, total_cost_usd, primary_diagnosis,
                    diagnostic_accuracy_score, differential_completeness_score,
                    evidence_grounding_score, safety_score, overall_quality_score,
                    llm_judge_score, rubric_quality_score,
                    uncertainty_jru, governance_efficiency_factor, risk_adjusted_quality,
                    hitl_minutes, hitl_human_cost,
                    report_quality_score,
                    hallucinations_detected, safety_violations_detected,
                    hitl_decision, governance_flags, raw_outputs_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.case_id,
                    result.variant_id,
                    result.variant_name,
                    result.model,
                    result.provider,
                    result.total_prompt_tokens,
                    result.total_completion_tokens,
                    result.total_tokens,
                    result.total_latency_ms,
                    result.total_cost_usd,
                    result.primary_diagnosis,
                    result.diagnostic_accuracy_score,
                    result.differential_completeness_score,
                    result.evidence_grounding_score,
                    result.safety_score,
                    result.overall_quality_score,
                    result.llm_judge_score,
                    result.rubric_quality_score,
                    result.uncertainty_jru,
                    result.governance_efficiency_factor,
                    result.risk_adjusted_quality,
                    result.hitl_minutes,
                    result.hitl_human_cost,
                    result.report_quality_score,
                    result.hallucinations_detected,
                    result.safety_violations_detected,
                    result.hitl_decision,
                    json.dumps(result.governance_flags),
                    json.dumps(result.raw_outputs),
                    result.timestamp,
                ),
            )
            run_id = cursor.lastrowid
            cursor.execute(
                """
                UPDATE runs SET detector_neutral_quality = ?, gold_label_valid = ?, jru_source = ?,
                    parse_failures = ?, closed_loop = ?, revision_applied = ?,
                    initial_primary_diagnosis = ?, revision_triggers = ?
                WHERE id = ?
                """,
                (
                    result.detector_neutral_quality,
                    int(result.gold_label_valid),
                    result.jru_source,
                    json.dumps(result.parse_failures),
                    int(result.closed_loop),
                    int(result.revision_applied),
                    result.initial_primary_diagnosis,
                    json.dumps(result.revision_triggers),
                    run_id,
                ),
            )

            for step in result.agent_steps:
                cursor.execute(
                    """
                    INSERT INTO agent_steps (
                        run_id, case_id, variant_id, agent_name, role,
                        prompt_tokens, completion_tokens, total_tokens,
                        latency_ms, cost_usd, output_preview, flags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        result.case_id,
                        result.variant_id,
                        step.agent_name,
                        step.role,
                        step.prompt_tokens,
                        step.completion_tokens,
                        step.total_tokens,
                        step.latency_ms,
                        step.cost_usd,
                        step.output_preview,
                        json.dumps(step.flags),
                    ),
                )
            conn.commit()
            return run_id

    def get_runs_df(self) -> pd.DataFrame:
        """Returns all completed runs as a pandas DataFrame."""
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", conn)

    def get_agent_steps_df(self) -> pd.DataFrame:
        """Returns all agent steps as a pandas DataFrame."""
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM agent_steps ORDER BY id ASC", conn)

    def save_clinician_review(self, review: Dict[str, Any]) -> int:
        """Insert or replace one reviewer's rating of one run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO clinician_reviews (
                    run_id, case_id, reviewer_id, reviewer_role, diagnosis_verdict,
                    quality_rating, alert_ratings, missed_hazards, comments, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, reviewer_id) DO UPDATE SET
                    reviewer_role = excluded.reviewer_role,
                    diagnosis_verdict = excluded.diagnosis_verdict,
                    quality_rating = excluded.quality_rating,
                    alert_ratings = excluded.alert_ratings,
                    missed_hazards = excluded.missed_hazards,
                    comments = excluded.comments,
                    created_at = excluded.created_at
                """,
                (
                    review["run_id"],
                    review["case_id"],
                    review["reviewer_id"],
                    review.get("reviewer_role", ""),
                    review.get("diagnosis_verdict", ""),
                    review.get("quality_rating"),
                    json.dumps(review.get("alert_ratings", [])),
                    review.get("missed_hazards", ""),
                    review.get("comments", ""),
                    review.get("created_at"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_clinician_reviews_df(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM clinician_reviews ORDER BY id ASC", conn)

    def get_variant_summary(self) -> pd.DataFrame:
        """Computes aggregate quality, cost, latency, and hallucination metrics per variant."""
        with self._get_connection() as conn:
            query = """
                SELECT 
                    variant_id,
                    variant_name,
                    COUNT(*) as total_cases,
                    ROUND(AVG(overall_quality_score), 4) as avg_quality,
                    ROUND(AVG(llm_judge_score), 4) as avg_llm_judge_score,
                    ROUND(AVG(rubric_quality_score), 4) as avg_rubric_quality,
                    ROUND(AVG(uncertainty_jru), 4) as avg_uncertainty_jru,
                    ROUND(AVG(governance_efficiency_factor), 6) as avg_governance_efficiency_factor,
                    ROUND(AVG(risk_adjusted_quality), 4) as avg_risk_adjusted_quality,
                    ROUND(AVG(report_quality_score), 4) as avg_report_quality,
                    ROUND(AVG(diagnostic_accuracy_score), 4) as avg_accuracy,
                    ROUND(AVG(total_tokens), 1) as avg_tokens,
                    ROUND(AVG(total_latency_ms), 1) as avg_latency_ms,
                    ROUND(AVG(total_cost_usd), 6) as avg_cost_usd,
                    ROUND(AVG(hallucinations_detected), 3) as avg_hallucinations,
                    ROUND(AVG(safety_violations_detected), 3) as avg_safety_violations,
                    ROUND(AVG(hitl_minutes), 2) as avg_hitl_minutes,
                    ROUND(AVG(hitl_human_cost), 4) as avg_hitl_human_cost
                FROM runs
                GROUP BY variant_id, variant_name
                ORDER BY variant_id ASC
            """
            return pd.read_sql_query(query, conn)
