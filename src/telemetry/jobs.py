"""SQLite persistence for interactive background jobs, so a restart does not lose finished results.

The job's progress and decision-support result are stored; the submitted case text is not, but the result can
echo parts of it. Jobs whose case contained acknowledged identifiers are saved without their result.
Rows older than the retention window are deleted by purge_older_than().
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

RESTART_ERROR = "Server restarted before this job finished (error: server restarted). No result was generated."
_JSON_FIELDS = ("planned", "steps", "events", "result")


class JobStore:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    finished_at REAL,
                    planned TEXT,
                    steps TEXT,
                    events TEXT,
                    result TEXT,
                    error TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=30.0)

    def save(self, job: Dict[str, Any]) -> None:
        """Insert or replace the job's persisted fields."""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO jobs (id, status, created_at, updated_at, finished_at, planned, steps, events, "
                "result, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job["id"], job["status"], job["started"], now, job.get("finished"),
                 json.dumps(job.get("planned") or []), json.dumps(list((job.get("steps") or {}).values())),
                 json.dumps(job.get("events") or []), json.dumps(job.get("result")) if job.get("result") is not None else None,
                 job.get("error") if isinstance(job.get("error"), str) or job.get("error") is None else json.dumps(job["error"])),
            )

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        job = dict(row)
        for key in _JSON_FIELDS:
            job[key] = json.loads(job[key]) if job[key] else ([] if key != "result" else None)
        return job

    def mark_interrupted(self) -> int:
        """Jobs left 'running' by a previous process can never finish; say so instead of hanging."""
        now = time.time()
        with self._connect() as conn:
            return conn.execute("UPDATE jobs SET status = 'error', error = ?, updated_at = ?, finished_at = ? "
                                "WHERE status = 'running'", (RESTART_ERROR, now, now)).rowcount

    def purge_older_than(self, cutoff: float) -> int:
        with self._connect() as conn:
            return conn.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,)).rowcount
