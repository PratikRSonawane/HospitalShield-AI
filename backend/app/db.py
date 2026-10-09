"""Run history: best-effort SQLite persistence (Tier 2).

A database failure only logs a warning; simulations still return. History
is a convenience for planners, never a dependency of the computation.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("hospitalshield.history")

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "run_history.sqlite3"
MAX_ROWS = 200


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=1)
    conn.execute("CREATE TABLE IF NOT EXISTS runs ("
                 "run_id TEXT PRIMARY KEY, payload TEXT, saved_at REAL)")
    return conn


def save_run(run_id: str, payload: dict[str, Any]) -> None:
    """Persist one result; failures are logged and swallowed."""
    try:
        conn = _connect()
        conn.execute("INSERT OR REPLACE INTO runs (run_id, payload, saved_at) VALUES (?, ?, ?)",
                     (run_id, json.dumps(payload, default=str), time.time()))
        conn.execute("DELETE FROM runs WHERE run_id NOT IN "
                     "(SELECT run_id FROM runs ORDER BY saved_at DESC LIMIT ?)", (MAX_ROWS,))
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        logger.warning("run history unavailable: %s", exc)


def get_run(run_id: str) -> dict[str, Any] | None:
    """Fetch one stored result; None when missing or the store fails."""
    try:
        conn = _connect()
        row = conn.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except (sqlite3.Error, json.JSONDecodeError):
        return None


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    """Most recent runs (run_id, scenario, resilience, saved_at)."""
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT run_id, payload, saved_at FROM runs ORDER BY saved_at DESC LIMIT ?",
            (limit,)).fetchall()
        conn.close()
        out = []
        for run_id, payload, saved_at in rows:
            try:
                data = json.loads(payload)
                out.append({
                    "run_id": run_id,
                    "scenario": data.get("scenario", {}).get("scenario"),
                    "resilience_index": (data.get("summary") or {}).get("resilience_index"),
                    "saved_at": saved_at,
                })
            except json.JSONDecodeError:
                continue
        return out
    except sqlite3.Error:
        return []
