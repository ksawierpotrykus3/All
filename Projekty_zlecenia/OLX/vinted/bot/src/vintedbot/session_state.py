"""Maszyna stanów sesji Vinted + walidacja zalogowania przez curl_cffi."""
import json
from .json_utils import json_loads
import threading
import time
from enum import Enum

from curl_cffi import requests as creq

from .config import IMPERSONATE, tls_kwargs

USERS_CURRENT_URL = "https://www.vinted.pl/api/v2/users/current"

# O4: TTL dla cache "users/current" (sekundy). Wywołanie is_ready() robi synchroniczny
# HTTP request — bez cache pętla detekcji (1s polling) zjadała 1 extra GET/s,
# marnując nasz rate-limit budget. 30s to kompromis: wykrywa wygasłą sesję szybko,
# ale eliminuje 29/30 redundantnych requestów.
USERS_CURRENT_CACHE_TTL_S = 30.0


class SessionStatus(Enum):
    UNKNOWN = "unknown"
    READY = "ready"
    REFRESHING = "refreshing"
    NEEDS_LOGIN = "needs_login"


class SessionState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.status = SessionStatus.UNKNOWN
        self.cookies: dict[str, str] = {}
        self.login: str | None = None
        self.user_id: int | None = None
        self.last_refresh_ts = 0.0
        self.reservations = 0
        self.errors: list[str] = []
        # O4: cache ostatniego pozytywnego sprawdzenia zalogowania (login + ts).
        # Invalidacja: set_cookies() resetuje; is_ready() odświeża po wygaśnięciu TTL
        # LUB gdy cached login nie istnieje. Negative cache (status != 200) NIE jest
        # cache'owany — chcemy szybko wykryć, gdy Vinted przywrócił sesję.
        self._ready_cache_login: str | None = None
        self._ready_cache_ts: float = 0.0

    def set_status(self, status: SessionStatus) -> None:
        with self._lock:
            self.status = status

    def record_reservation(self) -> None:
        with self._lock:
            self.reservations += 1

    def record_error(self, msg: str) -> None:
        with self._lock:
            self.errors.append(msg)

    def set_cookies(self, cookies: dict[str, str], login: str | None, user_id: int | None = None) -> None:
        with self._lock:
            self.cookies = cookies
            self.login = login
            self.user_id = user_id
            self.last_refresh_ts = time.time()
            # O4: invalidacja cache — nowe cookies oznaczają potencjalnie nowy login.
            self._ready_cache_login = None
            self._ready_cache_ts = 0.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self.status.value,
                "login": self.login,
                "reservations": self.reservations,
                "errors": list(self.errors),
                "cookies_count": len(self.cookies),
            }

    def is_ready(self) -> bool:
        """Zwraca True jeśli sesja zalogowana. Cache TTL=30s na pozytywne odpowiedzi."""
        with self._lock:
            cookies = dict(self.cookies)
            cached_login = self._ready_cache_login
            cached_ts = self._ready_cache_ts
        if not cookies:
            return False
        # O4: jeśli mamy świeży pozytywny cache, nie robimy HTTP.
        now = time.time()
        if cached_login and (now - cached_ts) < USERS_CURRENT_CACHE_TTL_S:
            return True
        r = creq.get(USERS_CURRENT_URL, headers={"Accept": "application/json"},
                     cookies=cookies, impersonate=IMPERSONATE, timeout=20, **tls_kwargs())
        if r.status_code != 200:
            # Negative cache: nie zapisujemy — następne is_ready() od razu spróbuje znowu.
            return False
        try:
            data = json_loads(r.content)
        except Exception:
            return False
        user = data.get("user") or {}
        login = user.get("login") or data.get("login")
        uid = user.get("id") or data.get("id")
        if login:
            with self._lock:
                self.login = login
                if uid is not None:
                    self.user_id = int(uid)
                # O4: cache trafiony — kolejne wywołania przez TTL nie robią HTTP.
                self._ready_cache_login = login
                self._ready_cache_ts = now
            return True
        return False