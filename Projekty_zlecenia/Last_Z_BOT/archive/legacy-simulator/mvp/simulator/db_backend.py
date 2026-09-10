# mvp/simulator/db_backend.py
"""
SQLite Database Backend for Metrics Persistence.

Enables historical metrics storage, cross-session comparisons,
and long-term trend analysis.
"""

import sqlite3
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from threading import Lock


logger = logging.getLogger(__name__)


class DatabaseBackend:
    """SQLite backend for persistent metrics storage."""

    def __init__(self, db_path: str = './simulator_metrics.db'):
        """
        Initialize DatabaseBackend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._lock = Lock()

        # Create/connect to database
        self._create_tables()

        logger.info(f"DatabaseBackend initialized: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self) -> None:
        """Create database schema if not exists."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT UNIQUE,
                    variant_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    iterations INT,
                    accuracy_pct REAL,
                    notes TEXT
                )
            ''')

            # Iterations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iterations (
                    id INTEGER PRIMARY KEY,
                    session_id INT,
                    iteration_num INT,
                    accuracy REAL,
                    latency_ms REAL,
                    cpu_percent REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            ''')

            conn.commit()
            conn.close()

            logger.info("Database schema created successfully")

        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    def create_session(
        self,
        session_id: str,
        variant_name: str,
        notes: str = ''
    ) -> Optional[int]:
        """
        Create new session record.

        Args:
            session_id: Session identifier
            variant_name: Variant name
            notes: Optional notes

        Returns:
            Session primary key or None
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO sessions (session_id, variant_name, notes)
                    VALUES (?, ?, ?)
                ''', (session_id, variant_name, notes))

                conn.commit()
                session_pk = cursor.lastrowid
                conn.close()

                logger.info(f"Session created: {session_id}")
                return session_pk

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None

    def insert_iteration(
        self,
        session_pk: int,
        iteration: int,
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Insert iteration metrics.

        Args:
            session_pk: Session primary key
            iteration: Iteration number
            metrics: Metrics dict

        Returns:
            True if successful
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO iterations
                    (session_id, iteration_num, accuracy, latency_ms, cpu_percent)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    session_pk,
                    iteration,
                    metrics.get('accuracy'),
                    metrics.get('latency_ms'),
                    metrics.get('cpu_percent')
                ))

                conn.commit()
                conn.close()

                return True

        except Exception as e:
            logger.error(f"Error inserting iteration: {e}")
            return False

    def get_session_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get past sessions.

        Args:
            limit: Maximum sessions to return

        Returns:
            List of session dicts
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM sessions
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))

                rows = cursor.fetchall()
                conn.close()

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error retrieving sessions: {e}")
            return []

    def compare_variants(self, variant_names: List[str]) -> Dict[str, List[float]]:
        """
        Compare metrics across variants.

        Args:
            variant_names: List of variant names

        Returns:
            Dict mapping variant names to accuracy values
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                result = {}

                for variant in variant_names:
                    cursor.execute('''
                        SELECT AVG(accuracy) as avg_accuracy
                        FROM iterations i
                        JOIN sessions s ON i.session_id = s.id
                        WHERE s.variant_name = ?
                    ''', (variant,))

                    row = cursor.fetchone()
                    avg = row['avg_accuracy'] if row and row['avg_accuracy'] else 0.0
                    result[variant] = [avg]

                conn.close()
                return result

        except Exception as e:
            logger.error(f"Error comparing variants: {e}")
            return {}

    def export_csv(
        self,
        output_path: str,
        filters: Dict[str, Any] = None
    ) -> bool:
        """
        Export filtered metrics to CSV.

        Args:
            output_path: Output file path
            filters: Optional filter dict

        Returns:
            True if successful
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Query all iterations with session info
                cursor.execute('''
                    SELECT s.session_id, s.variant_name, i.iteration_num,
                           i.accuracy, i.latency_ms, i.cpu_percent, i.created_at
                    FROM iterations i
                    JOIN sessions s ON i.session_id = s.id
                    ORDER BY s.created_at DESC, i.iteration_num
                ''')

                rows = cursor.fetchall()
                conn.close()

                # Write CSV
                with open(output_path, 'w') as f:
                    f.write('session_id,variant,iteration,accuracy,latency_ms,cpu_percent,timestamp\n')
                    for row in rows:
                        f.write(f"{row['session_id']},{row['variant_name']},{row['iteration_num']},")
                        f.write(f"{row['accuracy']},{row['latency_ms']},{row['cpu_percent']},{row['created_at']}\n")

                logger.info(f"CSV exported: {output_path}")
                return True

        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return False

    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """
        Delete sessions older than N days.

        Args:
            days_old: Number of days

        Returns:
            Count of deleted sessions
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Calculate cutoff date
                cutoff = datetime.now() - timedelta(days=days_old)
                cutoff_str = cutoff.isoformat()

                # Delete iterations first (foreign key constraint)
                cursor.execute('''
                    DELETE FROM iterations
                    WHERE session_id IN (
                        SELECT id FROM sessions WHERE created_at < ?
                    )
                ''', (cutoff_str,))

                # Delete sessions
                cursor.execute('''
                    DELETE FROM sessions WHERE created_at < ?
                ''', (cutoff_str,))

                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()

                logger.info(f"Cleaned up {deleted_count} old sessions")
                return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with stats
        """
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Count sessions
                cursor.execute('SELECT COUNT(*) as count FROM sessions')
                session_count = cursor.fetchone()['count']

                # Count iterations
                cursor.execute('SELECT COUNT(*) as count FROM iterations')
                iteration_count = cursor.fetchone()['count']

                conn.close()

                return {
                    'sessions': session_count,
                    'iterations': iteration_count,
                    'db_path': self.db_path,
                    'size_mb': os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0,
                }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
