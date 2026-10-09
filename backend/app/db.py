import sqlite3
import json
from pathlib import Path

DB_PATH = Path("runs.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

def save_run(run_id: str, data: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO runs (id, data) VALUES (?, ?)", (run_id, json.dumps(data)))

def get_run(run_id: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT data FROM runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
    return None

def get_all_runs() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT data FROM runs ORDER BY timestamp DESC")
        return [json.loads(row[0]) for row in cursor.fetchall()]

init_db()
