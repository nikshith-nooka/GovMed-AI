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

    def __init__(self, db_path: str = "results/benchmark_results.db"):
        self.db_path = db_path
        Path(os.path.dirname(self.db_path)).mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=60.0)

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
                    hallucinations_detected INTEGER,
                    safety_violations_detected INTEGER,
                    hitl_decision TEXT,
                    governance_flags TEXT,
                    raw_outputs_json TEXT,
                    timestamp REAL
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
                    hallucinations_detected, safety_violations_detected,
                    hitl_decision, governance_flags, raw_outputs_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    result.hallucinations_detected,
                    result.safety_violations_detected,
                    result.hitl_decision,
                    json.dumps(result.governance_flags),
                    json.dumps(result.raw_outputs),
                    result.timestamp,
                ),
            )
            run_id = cursor.lastrowid

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

    def get_variant_summary(self) -> pd.DataFrame:
        """Computes aggregate quality, cost, latency, and hallucination metrics per variant."""
        with self._get_connection() as conn:
            query = """
                SELECT 
                    variant_id,
                    variant_name,
                    COUNT(*) as total_cases,
                    ROUND(AVG(overall_quality_score), 4) as avg_quality,
                    ROUND(AVG(diagnostic_accuracy_score), 4) as avg_accuracy,
                    ROUND(AVG(total_tokens), 1) as avg_tokens,
                    ROUND(AVG(total_latency_ms), 1) as avg_latency_ms,
                    ROUND(AVG(total_cost_usd), 6) as avg_cost_usd,
                    ROUND(AVG(hallucinations_detected), 3) as avg_hallucinations,
                    ROUND(AVG(safety_violations_detected), 3) as avg_safety_violations
                FROM runs
                GROUP BY variant_id, variant_name
                ORDER BY variant_id ASC
            """
            return pd.read_sql_query(query, conn)
