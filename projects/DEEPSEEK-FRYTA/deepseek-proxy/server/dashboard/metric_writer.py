"""Thread-safe SQLite WAL writer for dashboard metrics."""

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from server.config.settings import settings as _settings

DB_PATH = Path(__file__).resolve().parent.parent.parent / _settings.dashboard_db_path


class MetricWriter:
    """Thread-safe writer that stores conversation metrics in SQLite (WAL mode).

    Each thread gets its own connection via ``threading.local()`` so callers
    can safely use the same writer instance across async workers or threads.
    """

    def __init__(self, db_path: str | Path = DB_PATH) -> None:
        self._db_path = str(db_path)
        self._local: threading.local = threading.local()
        self._lock = threading.Lock()
        self._init_db()
        self._seed_account_sessions()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Return the current thread's connection (create if first access)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create all tables and indexes if they do not exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                chat_id TEXT,
                account_slot INTEGER NOT NULL,
                user_uuid TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT 'deepseek-v4-pro',
                status TEXT NOT NULL DEFAULT 'active',
                started_at REAL NOT NULL,
                ended_at REAL,
                total_tokens INTEGER DEFAULT 0,
                total_duration_ms INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_user_uuid
                ON conversations(user_uuid);
            CREATE INDEX IF NOT EXISTS idx_conversations_account_slot
                ON conversations(account_slot);
            CREATE INDEX IF NOT EXISTS idx_conversations_status
                ON conversations(status);
            CREATE INDEX IF NOT EXISTS idx_conversations_started_at
                ON conversations(started_at);

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                timestamp REAL NOT NULL,
                ttft_ms REAL,
                tokens_per_sec REAL,
                tokens_total INTEGER DEFAULT 0,
                latency_ms REAL,
                events_count INTEGER DEFAULT 0,
                stream_active INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_conversation_id
                ON metrics(conversation_id);

            CREATE TABLE IF NOT EXISTS tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                tool_name TEXT NOT NULL,
                arguments TEXT NOT NULL,
                result TEXT,
                is_valid INTEGER DEFAULT 1,
                repair_tier INTEGER DEFAULT 0,
                parsed_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tool_calls_conversation_id
                ON tool_calls(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_name
                ON tool_calls(tool_name);

            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT REFERENCES conversations(id),
                type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'warning',
                message TEXT NOT NULL,
                details TEXT,
                detected_at REAL NOT NULL,
                acknowledged INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_anomalies_conversation_id
                ON anomalies(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_anomalies_type
                ON anomalies(type);
            CREATE INDEX IF NOT EXISTS idx_anomalies_severity
                ON anomalies(severity);

            CREATE TABLE IF NOT EXISTS account_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'inactive',
                rate_limited_until REAL,
                conversations_count INTEGER DEFAULT 0,
                last_used_at REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login_attempt TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_correlations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correlation_key TEXT NOT NULL,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                label TEXT,
                parent_id TEXT REFERENCES conversations(id),
                depth INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_chat_correlations_correlation_key
                ON chat_correlations(correlation_key);
            CREATE INDEX IF NOT EXISTS idx_chat_correlations_parent_id
                ON chat_correlations(parent_id);
        """)
        conn.commit()

    def _seed_account_sessions(self) -> None:
        """Ensure three account slots (0, 1, 2) exist."""
        conn = self._get_conn()
        for slot in range(3):
            conn.execute(
                "INSERT OR IGNORE INTO account_sessions (slot, status) VALUES (?, 'inactive')",
                (slot,),
            )
        conn.commit()

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def insert_conversation(
        self,
        conv_id: str,
        chat_id: str,
        account_slot: int,
        user_uuid: str,
        model: str = "deepseek-v4-pro",
    ) -> None:
        """Insert a new conversation row (``INSERT OR IGNORE``)."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO conversations
                (id, chat_id, account_slot, user_uuid, model, started_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, chat_id, account_slot, user_uuid, model, time.time()),
        )
        conn.commit()

    def insert_metric(
        self,
        conv_id: str,
        timestamp: float,
        ttft_ms: float | None = None,
        tokens_per_sec: float | None = None,
        tokens_total: int = 0,
        latency_ms: float | None = None,
        events_count: int = 0,
        stream_active: int = 1,
    ) -> None:
        """Insert a metric sample for a conversation."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO metrics
                (conversation_id, timestamp, ttft_ms, tokens_per_sec,
                 tokens_total, latency_ms, events_count, stream_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                timestamp,
                ttft_ms,
                tokens_per_sec,
                tokens_total,
                latency_ms,
                events_count,
                stream_active,
            ),
        )
        conn.commit()

    def finalize_conversation(
        self,
        conv_id: str,
        total_tokens: int,
        duration_ms: int,
        error_message: str | None = None,
    ) -> None:
        """Mark a conversation as completed or errored.

        Sets ``status`` to ``'completed'`` when *error_message* is *None*,
        otherwise ``'error'``.
        """
        conn = self._get_conn()
        status = "error" if error_message else "completed"
        conn.execute(
            """
            UPDATE conversations
            SET status = ?,
                ended_at = ?,
                total_tokens = ?,
                total_duration_ms = ?,
                error_message = ?
            WHERE id = ?
            """,
            (status, time.time(), total_tokens, duration_ms, error_message, conv_id),
        )
        conn.commit()

    def insert_tool_call(
        self,
        conv_id: str,
        tool_name: str,
        arguments: str,
        is_valid: int = 1,
        repair_tier: int = 0,
    ) -> None:
        """Record a tool-call event."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO tool_calls
                (conversation_id, tool_name, arguments, is_valid,
                 repair_tier, parsed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, tool_name, arguments, is_valid, repair_tier, time.time()),
        )
        conn.commit()

    def insert_anomaly(
        self,
        conv_id: str | None,
        type_: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an anomaly/event.

        The optional *details* dict is serialised to JSON.
        """
        conn = self._get_conn()
        details_json = json.dumps(details) if details else None
        conn.execute(
            """
            INSERT INTO anomalies
                (conversation_id, type, severity, message, details, detected_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, type_, severity, message, details_json, time.time()),
        )
        conn.commit()

    def update_account_status(
        self,
        slot: int,
        status: str,
        rate_limited_until: float | None = None,
    ) -> None:
        """Update an account slot's status and optional rate-limit expiry."""
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE account_sessions
            SET status = ?,
                rate_limited_until = ?
            WHERE slot = ?
            """,
            (status, rate_limited_until, slot),
        )
        conn.commit()

    def increment_account_conversations(self, slot: int) -> None:
        """Increment conversation count for an account slot and touch
        ``last_used_at``."""
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE account_sessions
            SET conversations_count = conversations_count + 1,
                last_used_at = ?
            WHERE slot = ?
            """,
            (time.time(), slot),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Correlations
    # ------------------------------------------------------------------

    def find_previous_conversation(self, chat_id: str) -> str | None:
        """Find the previous conversation ``id`` with the same *chat_id*,
        ordered by ``started_at`` descending (skip the most recent one).
        """
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT id FROM conversations
            WHERE chat_id = ?
            ORDER BY started_at DESC
            LIMIT 1 OFFSET 1
            """,
            (chat_id,),
        ).fetchone()
        return row[0] if row else None

    def insert_correlation(
        self,
        correlation_key: str,
        conversation_id: str,
        parent_id: str | None = None,
        label: str | None = None,
        depth: int = 0,
    ) -> None:
        """Record a chat-correlation link between two conversations."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO chat_correlations
                (correlation_key, conversation_id, label, parent_id, depth, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (correlation_key, conversation_id, label, parent_id, depth, datetime.utcnow().isoformat()),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the current thread's database connection."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
