"""SQLite storage for prediction history (Step 4 of the MLOps plan).

Prediction history lives in a small SQLite file so it can be cleaned the same
way as the rest of the platform — delete the file, or ``DELETE FROM
predictions`` via ``DELETE /predictions``. Uses the stdlib only (no ORM, no new
dependency). Each call opens a short-lived connection (commit + close on exit),
so the file is never left locked — including after the service is stopped.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    image_name    TEXT NOT NULL,
    result        TEXT NOT NULL,   -- "cat" | "dog"
    confidence    REAL NOT NULL,
    model_name    TEXT NOT NULL,
    model_version TEXT NOT NULL,   -- e.g. "v3"
    created_at    TEXT NOT NULL    -- ISO-8601
);
"""


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a connection; commit on success, always close on exit."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: Path) -> None:
    """Create the DB file (and parent dir) + table; no-op if already present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.execute(_SCHEMA)


def insert_prediction(
    path: Path,
    image_name: str,
    result: str,
    confidence: float,
    model_name: str,
    model_version: str,
    created_at: str,
) -> dict:
    """Insert one prediction and return the full stored row (incl. its ``id``)."""
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO predictions "
            "(image_name, result, confidence, model_name, model_version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (image_name, result, confidence, model_name, model_version, created_at),
        )
        row = conn.execute(
            "SELECT * FROM predictions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def list_predictions(path: Path) -> list[dict]:
    """All predictions, newest first."""
    with _connect(path) as conn:
        rows = conn.execute("SELECT * FROM predictions ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def clear_predictions(path: Path) -> int:
    """Delete every prediction; returns the number of rows removed."""
    with _connect(path) as conn:
        cur = conn.execute("DELETE FROM predictions")
        return cur.rowcount