"""Pętla refresh sesji przez Camoufox (frontend-driven token refresh).

Tożsamość jest spójna między uruchomieniami dzięki trwałemu profilowi
(persistent_context + user_data_dir) i identycznym parametrom Camoufox.

Strategia (wzorowana na harvest_cookies_firefox.py + refresh_cookies_headless.py):
1. Headless auto-refresh z trwałego profilu (bez interakcji użytkownika).
2. Jeśli profil nie jest zalogowany — otwiera przeglądarkę (headed), prosi
   użytkownika o ręczne zalogowanie, czeka i eksportuje cookies do profilu.
Tylko gdy oba zawiodą, stan ustawiany jest na NEEDS_LOGIN.
"""
import json
import threading
import time

from camoufox import Camoufox

from .config import profile_lock
from .session_state import SessionState, SessionStatus

LOGIN_URL = "https://www.vinted.pl/"
LOGIN_PAGE_URL = "https://www.vinted.pl/member/register/select_type?ref_url=%2F"
TIMEOUT_S = 90
MANUAL_LOGIN_TIMEOUT_S = 300
POLL_S = 2

# O9: wykrywanie zbliżającego się wygaśnięcia access_token_web. JWT exp claim
# sprawdzamy przy każdym run_once; jeśli <900s (15 min), wymuszamy refresh PRZED
# zakupem. Eliminuje sytuację, gdzie checkout leci z tokenem, który wygaśnie
# w trakcie sekwencji i Vinted zwraca 401.
TOKEN_REFRESH_THRESHOLD_S = 15 * 60

# O9: ile minut MIĘDZY standardowymi refreshami (gdy token daleko od wygaśnięcia).
# Domyślnie 4 (z CLI), ale logika auto-refresh obniży interwał, gdy token zbliża się
# do progu.
DEFAULT_REFRESH_INTERVAL_MIN = 4

# Tożsamość spójna z harvestem (ten sam webgl_config co harvest_cookies_firefox.py).
WEBGL_CONFIG = (
    "Google Inc. (AMD)",
    "ANGLE (AMD, Radeon R9 200 Series Direct3D11 vs_5_0 ps_5_0)",
)


def _eksportuj_cookies(raw_cookies) -> dict[str, str]:
    return {c.get("name", ""): c.get("value", "") for c in raw_cookies if c.get("name")}


def pobierz_swieze_cookies(profil: str) -> dict[str, str]:
    """Jednorazowo pobiera swieze cookies z trwalego profilu (headless, bez klikania)."""
    with Camoufox(persistent_context=True, headless=True, user_data_dir=profil,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        raw = ctx.cookies()
    return _eksportuj_cookies(raw)


def _czy_zalogowany(page):
    """Zwraca (login, id) z /users/current w kontekście przeglądarki lub (None, None)."""
    data = page.evaluate(
        """async () => {
            const r = await fetch('/api/v2/users/current', {headers: {'Accept': 'application/json'}});
            return JSON.stringify({status: r.status, body: await r.text()});
        }"""
    )
    obj = json.loads(data)
    if obj.get("status") != 200:
        return (None, None)
    body = json.loads(obj.get("body", "{}"))
    user = body.get("user") or {}
    login = user.get("login") or body.get("login")
    uid = user.get("id") or body.get("id")
    if login and uid:
        return (login, uid)
    return (None, None)


def _token_expires_in(cookies: dict[str, str]) -> float | None:
    """O9: ile sekund do wygaśnięcia access_token_web (None = brak/unparsable).

    JWT ma 3 części base64url rozdzielone kropką. Interesuje nas tylko
    payload (index 1) z claimem 'exp' (Unix timestamp w sekundach).
    Bez walidacji signature — to lokalna informacja planistyczna, nie trust.
    """
    import base64
    at = cookies.get("access_token_web", "")
    parts = at.split(".")
    if len(parts) < 2:
        return None
    try:
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return float(exp) - time.time()
    except Exception:
        return None


class RefreshLoop:
    def __init__(self, profile: str, interval_min: int = 4) -> None:
        self.profile = profile
        self.interval = interval_min * 60

    def _open(self, headless: bool):
        kwargs = dict(
            persistent_context=True,
            headless=headless,
            user_data_dir=self.profile,
            os="windows",
            fingerprint_preset=True,
            humanize=True,
            webgl_config=WEBGL_CONFIG,
        )
        return Camoufox(**kwargs)

    def _wait_for_login(self, page, timeout_s: int):
        start = time.time()
        while time.time() - start < timeout_s:
            account = _czy_zalogowany(page)
            if account[0]:
                return account
            time.sleep(POLL_S)
        return (None, None)

    def _try_refresh(self, state: SessionState, headless: bool) -> bool:
        """Jedna próba odświeżenia (headless auto albo headed z ręcznym logowaniem)."""
        state.set_status(SessionStatus.REFRESHING)
        try:
            with profile_lock(self.profile), self._open(headless) as ctx:
                page = ctx.new_page()
                if headless:
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
                    for fr in getattr(page, "frames", []):
                        if "captcha-delivery.com" in (getattr(fr, "url", "") or ""):
                            print("[refresh] wykryto slider DataDome w headless, próba rozwiązania...", flush=True)
                            try:
                                from .slider_solver import rozwiaz_slider
                                rozwiaz_slider(page)
                            except Exception as e:
                                print(f"[refresh] błąd slider_solver: {e}", flush=True)
                            break
                    account = self._wait_for_login(page, TIMEOUT_S)
                else:
                    print(f"Otwieram stronę logowania: {LOGIN_PAGE_URL}", flush=True)
                    page.goto(LOGIN_PAGE_URL, wait_until="domcontentloaded", timeout=60000)
                    for fr in getattr(page, "frames", []):
                        if "captcha-delivery.com" in (getattr(fr, "url", "") or ""):
                            print("[refresh] wykryto slider DataDome, próba rozwiązania...", flush=True)
                            try:
                                from .slider_solver import rozwiaz_slider
                                rozwiaz_slider(page)
                            except Exception as e:
                                print(f"[refresh] błąd slider_solver: {e}", flush=True)
                            break
                    print("\nZALOGUJ SIĘ RĘCZNIE w otwartym oknie przeglądarki.", flush=True)
                    print(f"Czekam maksymalnie {MANUAL_LOGIN_TIMEOUT_S}s na zalogowanie...\n", flush=True)
                    account = self._wait_for_login(page, MANUAL_LOGIN_TIMEOUT_S)

                if not account[0]:
                    return False

                cookies = _eksportuj_cookies(ctx.cookies())
                state.set_cookies(cookies, account[0])
                state.set_status(SessionStatus.READY)
                print(f"[vintedbot] sesja gotowa: {account[0]} (id {account[1]})", flush=True)
                return True
        except Exception as exc:
            state.record_error(f"refresh error: {exc}")
            return False

    def run_once(self, state: SessionState, force: bool = False) -> bool:
        """Jedna próba refresh.

        O9: `force=True` wymusza refresh niezależnie od interwału (np. gdy
        access_token_web blisko wygaśnięcia). Bez force — standardowy cykl.
        """
        # 1. Headless auto-refresh z trwałego profilu.
        if self._try_refresh(state, headless=True):
            return True
        # 2. Fallback: headed, wymagane ręczne zalogowanie.
        if self._try_refresh(state, headless=False):
            return True
        # 3. Oba zawiodły.
        state.set_status(SessionStatus.NEEDS_LOGIN)
        return False

    def _should_force_refresh(self, state: SessionState) -> bool:
        """O9: zwraca True gdy token blisko wygaśnięcia (<TOKEN_REFRESH_THRESHOLD_S)."""
        with state._lock:
            cookies = dict(state.cookies)
        if not cookies:
            return False
        expires_in = _token_expires_in(cookies)
        if expires_in is None:
            return False
        return expires_in < TOKEN_REFRESH_THRESHOLD_S

    def _current_sleep_s(self, state: SessionState) -> float:
        """O9: dynamiczny interwał sleep. Gdy token blisko wygaśnięcia, śpimy krócej."""
        if self._should_force_refresh(state):
            # Token blisko wygaśnięcia — odśwież co 60s zamiast co 4 min.
            return 60.0
        return float(self.interval)

    def run(self, state: SessionState, stop_event: threading.Event) -> None:
        """Pętla z dynamicznym interwałem (O9): skraca cykl gdy token blisko wygaśnięcia."""
        while not stop_event.is_set():
            self.run_once(state, force=self._should_force_refresh(state))
            sleep_s = self._current_sleep_s(state)
            stop_event.wait(sleep_s)