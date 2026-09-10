"""Generowanie i buforowanie (pre-warm) tokenu Incognia przez Node.js (AES-GCM)."""
import subprocess
import threading
import time

from .config import NODE_TOKEN_SCRIPT

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_TOKEN_LOCK = threading.Lock()


def wygeneruj_token(sdk_instance_id: str) -> str:
    """Generuje świeży token Incognia przez subprocess Node.js."""
    res = subprocess.run(
        ["node", str(NODE_TOKEN_SCRIPT), sdk_instance_id],
        capture_output=True, text=True, timeout=30,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Node.js error: {res.stderr}")
    return res.stdout.strip()


def pobierz_lub_wygeneruj_token(sdk_instance_id: str, max_age_s: float = 60.0) -> str:
    """Zwraca buforowany token z pamięci jeśli jest świeży, lub generuje nowy (thread-safe)."""
    now = time.monotonic()
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(sdk_instance_id)
        if cached and (now - cached[1]) < max_age_s:
            return cached[0]
    
    # Generowanie poza lockiem aby nie blokować innych wątków
    tok = wygeneruj_token(sdk_instance_id)
    with _TOKEN_LOCK:
        _TOKEN_CACHE[sdk_instance_id] = (tok, time.monotonic())
    return tok


def prewarm_token(sdk_instance_id: str) -> str:
    """Wymusza wygenerowanie i zapisanie świeżego tokenu do pamięci podręcznej."""
    tok = wygeneruj_token(sdk_instance_id)
    with _TOKEN_LOCK:
        _TOKEN_CACHE[sdk_instance_id] = (tok, time.monotonic())
    return tok


def czysc_cache_tokenu():
    """Czyści pamięć podręczną tokenów."""
    with _TOKEN_LOCK:
        _TOKEN_CACHE.clear()


def start_prewarm_worker(sdk_instance_id: str, interval_s: float = 45.0) -> threading.Event:
    """Uruchamia wątek w tle odświeżający token Incognia co interval_s sekund. Zwraca stop_event."""
    stop_event = threading.Event()

    def _worker():
        while not stop_event.is_set():
            try:
                prewarm_token(sdk_instance_id)
            except Exception as e:
                print(f"[incognia prewarm] błąd generowania tokenu w tle: {e}", flush=True)
            stop_event.wait(interval_s)

    t = threading.Thread(target=_worker, daemon=True, name="incognia-prewarm")
    t.start()
    return stop_event