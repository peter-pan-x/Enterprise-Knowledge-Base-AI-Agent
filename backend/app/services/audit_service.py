import sqlite3
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from app.services.auth_service import DATABASE_PATH


def initialize_audit_storage() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY, event_type TEXT NOT NULL, actor TEXT,
                path TEXT NOT NULL, status_code INTEGER NOT NULL, detail TEXT,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS generation_traces (
                id TEXT PRIMARY KEY, question_hash TEXT NOT NULL, answer_preview TEXT NOT NULL,
                answer_chars INTEGER NOT NULL, source_count INTEGER NOT NULL, latency_ms INTEGER NOT NULL,
                model TEXT NOT NULL, created_at TEXT NOT NULL
            )
        """)


def record_audit_event(event_type: str, path: str, status_code: int, actor: str | None = None, detail: str = "") -> None:
    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute("INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uuid4().hex, event_type, actor, path, status_code, detail[:500], datetime.now(UTC).isoformat()))
    except sqlite3.Error:
        # Audit availability must not block the customer-facing request.
        return


def record_generation_trace(question: str, answer: str, source_count: int, latency_ms: int, model: str) -> None:
    """Store bounded observability data without persisting raw prompts or secrets."""
    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.execute("INSERT INTO generation_traces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid4().hex, hashlib.sha256(question.encode()).hexdigest(), answer[:500], len(answer), source_count,
                 latency_ms, model, datetime.now(UTC).isoformat()))
    except sqlite3.Error:
        return


def list_audit_events(limit: int = 100) -> list[dict]:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def list_generation_traces(limit: int = 100) -> list[dict]:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM generation_traces ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]
