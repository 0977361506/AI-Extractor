"""SQLite persistence: documents/jobs, progress events (SSE replay), RM corrections, settings, VLM cache."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    total_pages INTEGER NOT NULL DEFAULT 0,
    done_pages INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_doc ON events(document_id, id);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    element_id TEXT NOT NULL,
    path TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    editor TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_corr_doc ON corrections(document_id, id);
CREATE TABLE IF NOT EXISTS vlm_cache (key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS connection_tests (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL, result TEXT NOT NULL);
"""

_DOC_FIELDS = {"status", "total_pages", "done_pages", "error", "job_id", "filename"}


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # settings -------------------------------------------------------------
    def get_setting(self, key: str, default=None):
        rows = self._all("SELECT value FROM settings WHERE key = ?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_setting(self, key: str, value) -> None:
        self._exec(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    # documents ------------------------------------------------------------
    def create_document(self, document_id: str, job_id: str, filename: str, total_pages: int = 0) -> None:
        now = time.time()
        self._exec(
            "INSERT INTO documents(document_id, job_id, filename, total_pages, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (document_id, job_id, filename, total_pages, now, now),
        )

    def update_document(self, document_id: str, **fields) -> None:
        cols = [k for k in fields if k in _DOC_FIELDS]
        if not cols:
            return
        sql = f"UPDATE documents SET {', '.join(f'{c} = ?' for c in cols)}, updated_at = ? WHERE document_id = ?"
        self._exec(sql, (*[fields[c] for c in cols], time.time(), document_id))

    def get_document(self, document_id: str) -> dict | None:
        rows = self._all("SELECT * FROM documents WHERE document_id = ?", (document_id,))
        return rows[0] if rows else None

    def list_documents(self) -> list[dict]:
        return self._all("SELECT * FROM documents ORDER BY created_at DESC")

    def delete_document(self, document_id: str) -> None:
        for table in ("documents", "events", "corrections"):
            self._exec(f"DELETE FROM {table} WHERE document_id = ?", (document_id,))

    # events ---------------------------------------------------------------
    def add_event(self, document_id: str, payload: dict) -> int:
        cur = self._exec(
            "INSERT INTO events(document_id, created_at, payload) VALUES(?,?,?)",
            (document_id, time.time(), json.dumps(payload, ensure_ascii=False)),
        )
        return int(cur.lastrowid)

    def events_after(self, document_id: str, last_id: int) -> list[dict]:
        rows = self._all("SELECT id, payload FROM events WHERE document_id = ? AND id > ? ORDER BY id", (document_id, last_id))
        return [{**json.loads(r["payload"]), "event_id": r["id"]} for r in rows]

    # corrections ----------------------------------------------------------
    def add_correction(self, document_id: str, element_id: str, path: str, old_value, new_value, editor: str) -> int:
        cur = self._exec(
            "INSERT INTO corrections(document_id, element_id, path, old_value, new_value, editor, created_at) VALUES(?,?,?,?,?,?,?)",
            (document_id, element_id, path, json.dumps(old_value, ensure_ascii=False), json.dumps(new_value, ensure_ascii=False), editor, time.time()),
        )
        return int(cur.lastrowid)

    def list_corrections(self, document_id: str) -> list[dict]:
        rows = self._all("SELECT * FROM corrections WHERE document_id = ? ORDER BY id", (document_id,))
        for r in rows:
            r["old_value"] = json.loads(r["old_value"]) if r["old_value"] is not None else None
            r["new_value"] = json.loads(r["new_value"]) if r["new_value"] is not None else None
        return rows

    # VLM cache / connection tests -----------------------------------------
    def cache_get(self, key: str):
        rows = self._all("SELECT response FROM vlm_cache WHERE key = ?", (key,))
        return json.loads(rows[0]["response"]) if rows else None

    def cache_put(self, key: str, response) -> None:
        self._exec(
            "INSERT OR REPLACE INTO vlm_cache(key, response, created_at) VALUES(?,?,?)",
            (key, json.dumps(response, ensure_ascii=False), time.time()),
        )

    def add_connection_test(self, result: dict) -> int:
        cur = self._exec("INSERT INTO connection_tests(created_at, result) VALUES(?,?)", (time.time(), json.dumps(result, ensure_ascii=False)))
        return int(cur.lastrowid)

    def list_connection_tests(self, limit: int = 20) -> list[dict]:
        rows = self._all("SELECT * FROM connection_tests ORDER BY id DESC LIMIT ?", (limit,))
        return [{"id": r["id"], "created_at": r["created_at"], "result": json.loads(r["result"])} for r in rows]
