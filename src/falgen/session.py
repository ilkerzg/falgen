"""SQLite session persistence for chat history."""

import json as json_mod
import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.expanduser("~"), ".cache", "falgen", "chat_sessions.db")


class SessionStore:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);

            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                url TEXT NOT NULL,
                media_type TEXT NOT NULL,
                endpoint_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_media_session ON media(session_id);
        """)
        self._conn.commit()

    def create_session(self, model: str, title: str = "") -> str:
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sessions (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, model, now, now),
        )
        self._conn.commit()
        return session_id

    def save_message(self, session_id: str, message: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        tool_calls = json_mod.dumps(message["tool_calls"]) if message.get("tool_calls") else None
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, message["role"], message.get("content"), tool_calls, message.get("tool_call_id"), now),
        )
        self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        self._conn.commit()

    def load_messages(self, session_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content, tool_calls, tool_call_id FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        messages = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"]}
            if row["tool_calls"]:
                msg["tool_calls"] = json_mod.loads(row["tool_calls"])
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            messages.append(msg)
        return messages

    def update_title(self, session_id: str, title: str) -> None:
        self._conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
        self._conn.commit()

    def update_model(self, session_id: str, model: str) -> None:
        self._conn.execute("UPDATE sessions SET model = ? WHERE id = ?", (model, session_id))
        self._conn.commit()

    def get_session(self, session_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, title, model, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, title, model, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_last_session_id(self) -> str | None:
        row = self._conn.execute(
            "SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def save_media(self, session_id: str, url: str, media_type: str, endpoint_id: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO media (session_id, url, media_type, endpoint_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, url, media_type, endpoint_id, now),
        )
        self._conn.commit()

    def load_media(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT url, media_type, endpoint_id, created_at FROM media WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
