"""Session management service — tracks active sessions per account slot."""

from __future__ import annotations

import threading
from typing import Optional

from server.config import MAX_SESSIONS_PER_ACCOUNT
from server.core.deepseek_client import ap


class SessionManager:
    """Manages session count per account slot."""

    def __init__(self) -> None:
        self._session_count: dict[int, int] = {}
        self._lock = threading.Lock()

    def acquire_slot(self, slot: int) -> bool:
        """Try to acquire a session slot. Returns True if successful."""
        with self._lock:
            c = self._session_count.get(slot, 0)
            if c >= MAX_SESSIONS_PER_ACCOUNT:
                return False
            self._session_count[slot] = c + 1
            return True

    def release_slot(self, slot: int) -> None:
        """Release a session slot."""
        with self._lock:
            c = self._session_count.get(slot, 0)
            if c > 0:
                self._session_count[slot] = c - 1

    def get_count(self, slot: int) -> int:
        """Get current session count for a slot."""
        with self._lock:
            return self._session_count.get(slot, 0)

    def _find_slot_with_capacity(self, account_indices: list[int]) -> Optional[int]:
        """From the given list, return first account that has an available session slot."""
        for idx in account_indices:
            with self._lock:
                c = self._session_count.get(idx, 0)
                if c < MAX_SESSIONS_PER_ACCOUNT and ap.is_valid(idx):
                    return idx
        return None


# Global instance
session_manager = SessionManager()