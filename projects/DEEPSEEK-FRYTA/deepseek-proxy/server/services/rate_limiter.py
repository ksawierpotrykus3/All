"""Rate limiter service — manages rate limit state per account slot."""

from __future__ import annotations

import threading
import time

from server.config import MAX_ACCOUNTS


# Module-level list for dashboard compatibility (read directly by metric_writer.py)
rate_limited_until: list[float] = [0.0] * MAX_ACCOUNTS
_rate_limit_lock = threading.Lock()


class RateLimiter:
    """Thread-safe rate limit management per account slot."""

    def __init__(self) -> None:
        pass  # Uses module-level globals for dashboard compatibility

    def is_limited(self, slot: int) -> bool:
        """Check if account slot is currently rate limited."""
        if slot < 0 or slot >= MAX_ACCOUNTS:
            return False
        with _rate_limit_lock:
            return time.time() < rate_limited_until[slot]

    def set_limited(self, slot: int, until: float) -> None:
        """Mark account slot as rate limited until given timestamp."""
        if slot < 0 or slot >= MAX_ACCOUNTS:
            return
        with _rate_limit_lock:
            rate_limited_until[slot] = until

    def reset(self, slot: int) -> None:
        """Reset rate limit for account slot (allow immediately)."""
        if slot < 0 or slot >= MAX_ACCOUNTS:
            return
        with _rate_limit_lock:
            rate_limited_until[slot] = 0.0

    def get_until(self, slot: int) -> float:
        """Get rate limit expiry timestamp for slot."""
        if slot < 0 or slot >= MAX_ACCOUNTS:
            return 0.0
        with _rate_limit_lock:
            return rate_limited_until[slot]

    def get_all(self) -> list[float]:
        """Get all rate limit timestamps (for dashboard)."""
        with _rate_limit_lock:
            return list(rate_limited_until)


# Global instance
rate_limiter = RateLimiter()