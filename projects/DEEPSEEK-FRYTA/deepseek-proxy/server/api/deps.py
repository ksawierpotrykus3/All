"""deps.py — Dependency injection container (Slim Rewrite).

ProxyService is now self-contained — no injected service arguments needed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator

from server.services.proxy_service import ProxyService


@lru_cache(maxsize=1)
def _get_proxy() -> ProxyService:
    """Singleton ProxyService instance."""
    return ProxyService()


async def get_proxy_service() -> AsyncGenerator[ProxyService, None]:
    """FastAPI dependency: yield ProxyService singleton."""
    yield _get_proxy()
