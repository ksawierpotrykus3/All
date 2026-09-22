"""Account selection service — picks best account for a conversation."""

from __future__ import annotations

import time
from typing import Optional

from server.config import MAX_ACCOUNTS
from server.core.deepseek_client import ap
from server.services.session_manager import session_manager
from server.services.rate_limiter import rate_limiter


class AccountSelector:
    """Selects the best account for a conversation based on session load and rate limits."""

    def __init__(self) -> None:
        pass  # Uses module-level services

    def select_account(
        self,
        messages: list[dict],
        state: Optional[dict] = None,
        is_resume: bool = False,
    ) -> int:
        """Select best account for a conversation.
        
        - RESUME: Use account from state (sticky session)
        - NEW: Pick least-loaded account (load balancing)
        """
        now_ac = time.time()

        # RESUME: sticky session — use account from state
        if is_resume and state and "account" in state:
            account_idx = state["account"]
            # If rate limited, try to find alt (but prefer sticking to same account)
            if now_ac < rate_limiter.get_until(account_idx):
                alt = self._find_least_loaded()
                if alt is not None:
                    return alt
            return account_idx

        # NEW SESSION: load balance — pick least-loaded account
        best = self._find_least_loaded()
        if best is not None:
            return best

        # Fallback: any valid account
        valid = [i for i in range(MAX_ACCOUNTS) if ap.is_valid(i)]
        if valid:
            return valid[0]
        return 0

    def _find_least_loaded(self, preferred: Optional[set[int]] = None) -> Optional[int]:
        """Return valid account with fewest active sessions."""
        now_ac = time.time()
        candidates = []
        for i in range(MAX_ACCOUNTS):
            if not ap.is_valid(i):
                continue
            if now_ac < rate_limiter.get_until(i):
                continue
            if preferred is not None and i not in preferred:
                continue
            candidates.append((session_manager.get_count(i), i))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]


# Global instance
account_selector = AccountSelector()

