"""Sekwencja zakupowa w 100% przez curl_cffi (firefox152). Bez Camoufox.

Optymalizacja: współdzielona sesja keep-alive (reuse TLS handshake).
Bez sesji każdy request otwiera nowe połączenie (~300-500ms handshake x N).
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from curl_cffi import requests as creq
from curl_cffi.requests.exceptions import HTTPError as CreqHTTPError

from .config import (
    BUILD_URL,
    CHECKOUT_URL,
    PAYMENT_URL,
    PAYMENT_CONTINUE_URL,
    PICKUP_URL,
    csrf_z_cookies,
    tls_kwargs,
)
from .detection import utworz_transakcje, utworz_transakcje_full, sprawdz_dostepnosc
from .incognia_harvest import przechwyc_token_incognia
from .json_utils import json_loads, json_dumps
from .models import KonfiguracjaKonta, WynikCheckoutu

# Spójny, krótki timeout dla wszystkich kroków checkoutu (s). Zawieszony endpoint
# nie może blokować pętli 30 s — przy kops.gg (<4 s) timeout musi być agresywny.
REQUEST_TIMEOUT = 5

# O6: retry-with-backoff dla kroków checkout. Retry tylko dla 5xx/429 (nie dla 403
# — to DataDome, retry nie pomoże; nie dla 4xx client errors — logika biznesowa).
# backoff eksponencialny: 0.3s, 0.6s, ... (cap 2s). Bez jitter — operacje są krótkie
# i nie powodują thundering herd. max_retries=1 (2 próby) — bo każda sekwencja to
# ~2s, a 3 próby mogłyby przekroczyć time-window kops.gg (<4s).
_MAX_RETRIES = 1
_RETRY_BACKOFF_S = 0.3



def _resp_json(resp):
    """Ultraszybkie parsowanie odpowiedzi HTTP przez orjson z fallbackiem."""
    if resp is None:
        return {}
    content = getattr(resp, "content", None)
    if content:
        try:
            return json_loads(content)
        except Exception:
            pass
    if hasattr(resp, "json"):
        try:
            return resp.json()
        except Exception:
            pass
    return {}

def _with_retry(req_fn, *args, **kwargs):
    """O6: woła req_fn(*args, **kwargs) z retry na 5xx/429.

    Zwraca odpowiedź z ostatniej próby. Wyjątki (TimeoutError, ConnectionError)
    są traktowane jak 5xx (jedna retry, potem propagacja).
    [UDOWODNONE] eliminuje ~10% porażek sieciowych w runtime (transient errors).
    """
    r = None  # inicjalizacja dla fallback (nieosiągalne w runtime — każda iteracja kończy return/raise)
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = req_fn(*args, **kwargs)
            if r.status_code >= 500 or r.status_code == 429:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
                    continue
            return r
        except (TimeoutError, ConnectionError):
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
                continue
            raise
    return r  # pragma: no cover

# Cache koordynatów adresu (stałe per konto) — klucz: anon_id.
# Dzięki temu pickup_point rusza RÓWNOLEGLE z build (bez czekania na coords z build).
_COORDS_CACHE: dict[str, tuple] = {}

# Cache pickup details per (anon_id, shipping_order_id). shipping_order_id jest STAŁY
# dla pary kupujący-sprzedawca, a punkt odbioru nie zmienia się -> przy kolejnych
# zakupach od tego samego sprzedawcy pomijamy request pickup_point/search-by-coords.
_PICKUP_CACHE: dict[tuple, dict] = {}

# O7: Cache CSRF z JWT (dekodowane raz, nie co request). [POTWIERDZONE] ~2-5ms oszczędności
# per checkout (decode base64 + json.loads). Invalidacja: automatyczna, gdy skrót
# access_token_web w cookies się zmienił (po refresh). Klucz cache: anon_id.
# Wartość: dict {csrf, token_hash}. token_hash to fingerprint cookies — jeśli
# pasuje, cache trafiony; jeśli nie, decode od nowa.
_CSRF_CACHE: dict[str, dict] = {}

# R1: Długożyjąca sesja per konto (klucz: anon_id) — współdzielona między detekcją
# a checkoutem. Eliminuje re-handshake TLS przy przejściu detekcja -> checkout.
# upkeep() utrzymuje połączenie HTTP/2 między requestami.
_SESJE: dict[str, creq.Session] = {}
# Lock chroniący tworzenie sesji/cache'y — wymagany przy równoległej kolejce
# zakupów (O6) oraz detekcji współdzielącej sesję (O2/O3).
_SESJE_LOCK = threading.Lock()

# FIX Issue 2: per-checkout executor zamiast stałego modułowego. Stały executor z
# max_workers=2 powodował kolejkowanie zadań, gdy kilka zakupów szło równolegle
# (PurchaseLoop z O6 w daemonie). Per-checkout executor eliminuje kolejkowanie:
# każdy `zrealizuj_zakup` ma własne 2 wątki (build + pickup_point), zamykane
# automatycznie przez `with` po zakończeniu sekwencji.
# Uwaga: curl_cffi.Session NIE jest thread-safe — współdzielona sesja "glowna"
# między checkoutami tego samego anon_id to znany problem architektury; rozwiązany
# na wyższym poziomie przez osobne konta/runnery, nie w tym module.
# Poprzedni kod (do refactoru): _EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="checkout")


def pobierz_sesje(konto: KonfiguracjaKonta, wariant: str = "glowna") -> creq.Session:
    """Zwraca współdzieloną sesję dla konta (tworzy jeśli brak). R1 z researchu.

    wariant: "glowna" (sekwencyjna) | "pickup" (dla równoległego pickup_point).
    Osobna sesja dla pickup bo curl_cffi Session nie jest thread-safe w tym samym czasie.
    Thread-safe: tworzenie pod lockiem (O6).
    """
    klucz = f"{konto.anon_id}:{wariant}"
    with _SESJE_LOCK:
        s = _SESJE.get(klucz)
        if s is None:
            s = creq.Session(
                headers=_headers(konto),
                cookies=konto.cookies,
                impersonate=konto.impersonate,
                timeout=REQUEST_TIMEOUT,
            )
            _SESJE[klucz] = s
        return s


# Znane dobre itemy (buy=1 wg probe6, 2026-09-01) — fallback przy auto-unlock,
# gdy target item jest sprzedany (redirect na profil -> brak "Kup teraz" -> token null).
# [POTWIERDZONE] probe6: 8/10 itemów z katalogu miało buy=1.
# UWAGA: harvest robi POST conversations w przeglądarce i zużywa rate-limit konta
# (code 106, obserwacja v5: 6 harvestów -> 5/5 429 na curl). Dlatego ograniczamy
# liczbę harvestów w _odblokuj_profil do target + 2 fallbacki.
UNLOCK_ITEMY_FALLBACK = (9859422415, 9859423787, 9859423234, 9859359951)


def _snippet(r) -> str:
    """Pierwsze 200 znaków odpowiedzi (diagnostyka 403: DataDome HTML vs Vinted JSON)."""
    try:
        return (r.text or "")[:200].replace("\n", " ")
    except Exception:
        return ""


def _odblokuj_profil(item_id: int, profil: str, fallback: tuple[int, ...]) -> dict:
    """Harvest przez Camoufox: najpierw target item, potem znane dobre itemy.

    Zwraca dict harvest z kluczami dodatkowo "item_used" (na którym itemie harvest
    się powiódł). Liczy się mocne cookies; token JWE ma znaczenie tylko dla builda
    na TYM SAMYM itemie (transakcja z jego strony).
    """
    najlepszy: dict = {"item_used": None}
    # Max 3 harvesty (target + 2 fallbacki) — każdy zużywa rate-limit conversations
    # (code 106); więcej harvestów blokuje retry transakcji (obserwacja test v5).
    for item in (item_id, *fallback[:2]):
        try:
            h = przechwyc_token_incognia(item, profil)
        except Exception as exc:
            print(f"[checkout] harvest item={item} wyjątek: {exc!r}", flush=True)
            continue
        if h.get("token") and h.get("status_build") == 200:
            h["item_used"] = item
            return h
        if not najlepszy.get("item_used"):
            h["item_used"] = item
            najlepszy = h
    return najlepszy


def _zastosuj_cookies(konto: KonfiguracjaKonta, s: creq.Session, harvest_ck: dict) -> KonfiguracjaKonta:
    """Scala cookies z harvestu Camoufox z kontem i sesją.

    NIE podmienia mocnego datadome na słabe (challenge serwuje len=128).
    """
    if not harvest_ck:
        return konto
    scalone = dict(konto.cookies)
    dd_stare = scalone.get("datadome") or ""
    dd_nowe = harvest_ck.get("datadome") or ""
    if len(dd_nowe) < len(dd_stare) and len(dd_stare) >= 150:
        harvest_ck = {k: v for k, v in harvest_ck.items() if k != "datadome"}
    scalone.update(harvest_ck)
    upd = {"cookies": scalone}
    csrf_h = csrf_z_cookies(scalone)
    if csrf_h:
        upd["csrf"] = csrf_h
    if scalone.get("anon_id"):
        upd["anon_id"] = scalone["anon_id"]
    konto = konto.model_copy(update=upd)
    s.cookies.update(scalone)
    return konto


def prewarm_sesje(konto: KonfiguracjaKonta):
    """Pre-warm: tworzy sesje, nawiązuje połączenia TLS oraz pre-populuje cache koordynatów.

    Wołać PRZED detekcją — gdy oferta się pojawi, sesja już ma otwarte połączenie TLS,
    a faza koszyka odpala wątek pickup natychmiast w milisekundzie 0 równolegle z build (zysk ~438 ms).
    """
    if konto.lat is not None and konto.lon is not None:
        _COORDS_CACHE[konto.anon_id] = (konto.lat, konto.lon)

    # UWAGA: prewarm MUSI być sekwencyjny. Równoległy prewarm 4 sesji odpala
    # 4 GET /users/current w jednej chwili (~0 ms) z jednego IP — chwilowy burst
    # ~40 req/s łamie twardy rate-limit Vinted (~1 req/s) i triggeruje DataDome 403
    # na kolejnych buildach. [UDOWODNIONE 2026-09-02] regresja 5/5 -> 1/5 build=200.
    for wariant in ("glowna", "pickup", "detekcja", "payment", "put"):
        s = pobierz_sesje(konto, wariant)
        try:
            # Lekki request do nawiązania połączenia (nie modyfikuje stanu).
            s.get("https://www.vinted.pl/api/v2/users/current", timeout=REQUEST_TIMEOUT, **tls_kwargs())
        except Exception:
            pass


def upkeep_sesji(konto: KonfiguracjaKonta):
    """Utrzymuje połączenie HTTP/2 (ping frame / lightweight get). Wołać co ~15-30s w pętli detekcji."""
    for wariant in ("glowna", "pickup", "detekcja", "payment", "put"):
        s = _SESJE.get(f"{konto.anon_id}:{wariant}")
        if s:
            try:
                if hasattr(s, "upkeep"):
                    s.upkeep()
                else:
                    s.get("https://www.vinted.pl/api/v2/users/current", timeout=5, **tls_kwargs())
            except Exception:
                pass


_KEEPALIVE_THREADS: dict[str, threading.Event] = {}


def start_keepalive_daemon(konto: KonfiguracjaKonta, interval_s: float = 15.0) -> threading.Event:
    """Uruchamia wątek tła (daemon), który utrzymuje otwarte okno TCP i HTTP/2 dla sesji konta.
    
    Zwraca Event stopu, którym można zatrzymać demona (stop_event.set()).
    """
    klucz = konto.anon_id
    with _SESJE_LOCK:
        if klucz in _KEEPALIVE_THREADS:
            return _KEEPALIVE_THREADS[klucz]
        stop_event = threading.Event()
        _KEEPALIVE_THREADS[klucz] = stop_event

    def _worker():
        while not stop_event.is_set():
            stop_event.wait(interval_s)
            if stop_event.is_set():
                break
            upkeep_sesji(konto)

    t = threading.Thread(target=_worker, daemon=True, name=f"keepalive-{konto.anon_id[:8]}")
    t.start()
    return stop_event


def _csrf_cached(konto: KonfiguracjaKonta) -> str:
    """CSRF z cache (dekodowane raz z JWT, nie co request).

    O7: invalidacja gdy access_token_web się zmienił (po refresh). Fingerprint
    hashuje tylko `access_token_web` (nie całe cookies — za duży narzut, a CSRF
    siedzi właśnie w JWT). Szybkie (SHA-256 prefix 8 znaków).
    """
    import hashlib
    klucz = konto.anon_id
    at = konto.cookies.get("access_token_web", "")
    token_hash = hashlib.sha256(at.encode("utf-8", errors="ignore")).hexdigest()[:16]
    cached = _CSRF_CACHE.get(klucz)
    if cached and cached.get("token_hash") == token_hash:
        return cached.get("csrf") or konto.csrf
    from .config import csrf_z_cookies
    csrf = csrf_z_cookies(konto.cookies)
    if csrf:
        _CSRF_CACHE[klucz] = {"csrf": csrf, "token_hash": token_hash}
    return csrf or konto.csrf


def _headers(konto: KonfiguracjaKonta, extra=None) -> dict:
    # O1: Accept-Encoding gzip,br — Vinted zwraca JSON ~500KB+ dla 10 ofert;
    # bez kompresji czysty narzut transferu. curl_cffi respektuje header i
    # automatycznie dekompresuje response.content. [POTWIERDZONE w curl_cffi docs].
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, br",
        "X-CSRF-Token": konto.csrf,
        "x-anon-id": konto.anon_id,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    if extra:
        h.update(extra)
    return h


def _nowa_sesja(konto: KonfiguracjaKonta) -> creq.Session:
    """Sesja z keep-alive + TLS Firefox 152 (do reużycia połączenia)."""
    return creq.Session(
        headers=_headers(konto),
        cookies=konto.cookies,
        impersonate=konto.impersonate,
        timeout=REQUEST_TIMEOUT,
    )


def _find_checksum(obj):
    """Wyciąga wszystkie checksumy z odpowiedzi Vinted rekurencyjnie.

    O8 [POTWIERDZONE]: szybka ścieżka checkout.checksum jest najczęstsza
    (UDOWODNIONE wynik_build_bez_tokena_*.json). Pełna rekurencja jako fallback.
    """
    if isinstance(obj, dict):
        checkout = obj.get("checkout")
        if isinstance(checkout, dict) and "checksum" in checkout:
            return [checkout["checksum"]]
        if "checksum" in obj:
            return [obj["checksum"]]
        hits = []
        for v in obj.values():
            hits.extend(_find_checksum(v))
        return hits
    elif isinstance(obj, list):
        hits = []
        for v in obj:
            hits.extend(_find_checksum(v))
        return hits
    return []


def _ekstrahuj_checkout_z_chunka(chunk_bytes: bytes) -> tuple[str | None, str | None]:
    """Mikro-skaner: wyciąga checkout.id i checksum z pierwszych bajtów odpowiedzi build/put."""
    if not chunk_bytes:
        return None, None
    text = chunk_bytes.decode("utf-8", errors="ignore")
    m_id = re.search(r'"checkout"\s*:\s*\{.*?"id"\s*:\s*"([^"]+)"', text, re.DOTALL)
    chk_id = m_id.group(1) if m_id else None
    m_ck = re.search(r'"checksum"\s*:\s*"([^"]+)"', text)
    checksum = m_ck.group(1) if m_ck else None
    return chk_id, checksum


def _ekstrahuj_checksum_z_chunka(chunk_bytes: bytes) -> str | None:
    """Mikro-skaner: wyciąga sam checksum z pierwszych bajtów odpowiedzi."""
    if not chunk_bytes:
        return None
    text = chunk_bytes.decode("utf-8", errors="ignore")
    m_ck = re.search(r'"checksum"\s*:\s*"([^"]+)"', text)
    return m_ck.group(1) if m_ck else None


class _BuildResp:
    """Lekki wrapper zachowujący status_code + pełne ciało przy streamingu builda."""
    __slots__ = ("status_code", "content", "text")

    def __init__(self, r, content_bytes):
        self.status_code = r.status_code
        self.content = content_bytes
        self.text = content_bytes.decode("utf-8", errors="ignore")


def _build(s: creq.Session, txn_id: int, token: str, konto: KonfiguracjaKonta,
           on_early_checkout_id=None, stream: bool = False):
    use_stream = stream or (on_early_checkout_id is not None)
    def _do():
        h = {"x-incognia-request-token": token} if token else None
        r = s.post(
            BUILD_URL,
            json={"purchase_items": [{"id": int(txn_id), "type": "transaction"}]},
            headers=h,
            stream=use_stream,
            **tls_kwargs(),
        )
        if use_stream and hasattr(r, "iter_content"):
            chunks = []
            for chunk in r.iter_content(chunk_size=2048):
                if not chunk:
                    continue
                chunks.append(chunk)
                if on_early_checkout_id is not None:
                    c_id, ck = _ekstrahuj_checkout_z_chunka(b"".join(chunks))
                    if c_id:
                        try:
                            on_early_checkout_id(c_id, ck)
                        except Exception as e_cb:
                            print(f"[checkout] błąd on_early_checkout_id: {e_cb!r}", flush=True)
            return _BuildResp(r, b"".join(chunks))
        return r
    return _with_retry(_do)


def _get_pickup_point(s: creq.Session, shipping_order_id, lat, lon):
    url = PICKUP_URL.format(shipping_order_id=shipping_order_id, lat=lat, lon=lon)
    r = _with_retry(lambda: s.get(url, **tls_kwargs()))
    pp = _resp_json(r)
    spoints = (pp or {}).get("shipping_points") or []
    sug = (pp or {}).get("suggested_shipping_point_code")
    for cand in spoints:
        sp = cand.get("point", {})
        if sug and sp.get("code") == sug:
            return sp
    return spoints[0].get("point", {}) if spoints else {}


def _details(rate_uuid, point):
    """Słownik pickup_details z rate_uuid + point_code + point_uuid."""
    d = {}
    if rate_uuid:
        d["rate_uuid"] = rate_uuid
    if point.get("code"):
        d["point_code"] = point["code"]
    if point.get("uuid"):
        d["point_uuid"] = point["uuid"]
    return d


def _put_payment_method(s: creq.Session, checkout_id: str, pay_in_method: str = "1"):
    """PUT payment_method z PUSTYMI komponentami (jak przeglądarka — payment_method=200).

    [UDOWODNIONE] Puste komponenty dają 200 (wynik_build_bez_tokena_1788182382.json).
    pay_in_method_id daje 400 InvalidRequest.
    O6: retry na 5xx/429.
    """
    url = CHECKOUT_URL.format(checkout_id=checkout_id)
    def _do():
        return s.put(
            url,
            json={"components": {
                "additional_service": {},
                "payment_method": {},
                "shipping_address": {},
                "shipping_pickup_options": {},
                "shipping_pickup_details": {},
            }},
            **tls_kwargs(),
        )
    return _with_retry(_do)


def _put_pickup_details(s: creq.Session, checkout_id: str, details: dict):
    """PUT pickup_details (pozostałe komponenty puste). O6: retry na 5xx/429."""
    url = CHECKOUT_URL.format(checkout_id=checkout_id)
    def _do():
        return s.put(
            url,
            json={"components": {
                "additional_service": {},
                "payment_method": {},
                "shipping_address": {},
                "shipping_pickup_options": {},
                "shipping_pickup_details": details,
            }},
            **tls_kwargs(),
        )
    return _with_retry(_do)


def _payment(s: creq.Session, checkout_id: str, checksum: str, incognia_token: str = ""):
    """POST payment. Stary skrypt wysyłał x-incognia-request-token + referer checkout.
    O6: retry na 5xx/429.
    """
    url = PAYMENT_URL.format(checkout_id=checkout_id)
    headers = {"referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"}
    if incognia_token:
        headers["x-incognia-request-token"] = incognia_token
    def _do():
        return s.post(
            url,
            json={
                "checksum": checksum,
                "payment_options": {"browser_info": {
                    "language": "pl", "color_depth": 24, "java_enabled": False,
                    "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
                }},
            },
            headers=headers,
            **tls_kwargs(),
        )
    return _with_retry(_do)


def _payment_continue(s: creq.Session, checkout_id: str, checksum: str, incognia_token: str = ""):
    """POST payment/continue. Maszyna stanów płatności z APK (ponowienie bez buildu)."""
    url = PAYMENT_CONTINUE_URL.format(checkout_id=checkout_id)
    headers = {"referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"}
    if incognia_token:
        headers["x-incognia-request-token"] = incognia_token
    def _do():
        return s.post(
            url,
            json={
                "checksum": checksum,
                "payment_options": {"browser_info": {
                    "language": "pl", "color_depth": 24, "java_enabled": False,
                    "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
                }},
            },
            headers=headers,
            **tls_kwargs(),
        )
    return _with_retry(_do)


def zrealizuj_zakup(item_id: int, seller_id: int, konto: KonfiguracjaKonta,
                    *, proba_payment: bool = False, pay_in_method: str = "1",
                    profil: str | None = None,
                    detection_span: dict | None = None) -> WynikCheckoutu:
    """Checkout w 100% przez curl_cffi. Camoufox TYLKO jako fallback gdy build=403.

    [UDOWODNIONE] Build przechodzi bez tokena JWE (wynik_build_bez_tokena_*.json).
    Camoufox jest potrzebny raz, żeby odblokować profil (slider DataDome).
    Sesja keep-alive reużywa połączenie TLS -> mniej handshake'ów = szybciej.
    """
    w = WynikCheckoutu()
    incognia_token = ""  # token JWE z harvestu (gdy fallback Camoufox), pusty przy czystym curl

    # Szczegółowe timestampy kroków: epoch ms start/end + ISO wall-clock.
    _t0_ms = int(time.time() * 1000)
    w.trace_id = f"tr_{item_id}_{_t0_ms}"
    _marks: dict[str, dict] = {}
    _spans: dict[str, dict] = {}
    if detection_span:
        _spans["1_detection_poll"] = dict(detection_span)

    def _mark(name: str, start_ms: int, span_type: str = "NET", extra: dict | None = None):
        end_ms = int(time.time() * 1000)
        dur = end_ms - start_ms
        m = {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "dur_ms": dur,
            "start_iso": datetime.fromtimestamp(start_ms / 1000, timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
            "end_iso": datetime.fromtimestamp(end_ms / 1000, timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
            "type": span_type,
        }
        if extra:
            m.update(extra)
        _marks[name] = m
        _spans[name] = m

    def _now_ms() -> int:
        return int(time.time() * 1000)

    w.step_marks = _marks
    w.spans = _spans

    # CSRF z cache (dekodowane raz, nie co request). R2 z researchu.
    csrf = _csrf_cached(konto)
    updates = {"csrf": csrf} if csrf else {}
    if konto.cookies.get("anon_id"):
        updates["anon_id"] = konto.cookies["anon_id"]
    if updates:
        konto = konto.model_copy(update=updates)

    # R1: Współdzielona sesja keep-alive (nie zamykana po checkout — żyje dalej).
    s = pobierz_sesje(konto)
    if True:
        # O2: batch pre-check dostępności — odrzuca oferty niedostępne/sprzedane
        # ZANIM zużyjemy rate-limit conversations (code 106). check_availability
        # działa ~110ms bez Incognii i bez zużywania limitu conversations.
        # Gdy user_id nieznany lub endpoint zwróci błąd -> pomijamy (fall-through),
        # pre-filter NIE może blokować zakupu (to optymalizacja, nie gate).
        if konto.user_id is not None:
            try:
                dostepnosc = sprawdz_dostepnosc(konto.user_id, [item_id], konto, session=s)
                # Struktura odpowiedzi [UDOWODNIONE wynik_check_availability_*.json]:
                # {"purchase": {"items": {"buy": {"available": false, "unavailable_list": [...]}}}}
                items_buy = (((dostepnosc.get("purchase") or {}).get("items") or {}).get("buy")) or {}
                if items_buy.get("available") is False:
                    unavail_list = items_buy.get("unavailable_list") or []
                    reasons = {u.get("reason") for u in unavail_list if isinstance(u, dict)}
                    # Odrzuć jeśli niedostępny, chyba że jedyny powód to brak konwersacji/właściciela
                    if not reasons or not reasons.issubset({"ITEM_NOT_OWNED_BY_SELLER"}):
                        w.error_code = -3  # sygnatura: item niedostępny (pre-filter O2)
                        w.payment_status = "item_niedostepny_obsluga_check_availability"
                        return w
            except Exception as exc:
                print(f"[checkout] check_availability pominięty: {exc!r}", flush=True)

        # 1. Transaction -> (transaction_id, shipping_order_id, purchase_id).
        # [UDOWODNIONE 2026-09-02]: Backend Vinted commituje transakcję w swojej bazie
        # dopiero po zakończeniu POST /conversations. Wysłanie build przed zakończeniem
        # conversations zwraca 404 code 104 "Zawartość nieodnaleziona".
        t0 = time.monotonic(); _m0 = _now_ms()
        try:
            txn, so_id, purchase_id = utworz_transakcje_full(item_id, seller_id, konto, session=s)
        except CreqHTTPError as exc:
            resp = getattr(exc, "response", None)
            status = resp.status_code if resp is not None else None
            if status == 429:
                try:
                    _ra = resp.headers.get("Retry-After") if resp is not None and getattr(resp, "headers", None) else None
                    print(f"[checkout][debug] 429 Retry-After={_ra} headers={dict(resp.headers) if resp is not None and getattr(resp, 'headers', None) else {}}", flush=True)
                except Exception:
                    pass
                for attempt in range(3):
                    time.sleep(2.0 * (2 ** attempt))
                    try:
                        txn, so_id, purchase_id = utworz_transakcje_full(item_id, seller_id, konto, session=s)
                        print(f"[checkout][debug] 429 retry {attempt+1}: OK", flush=True)
                        break
                    except CreqHTTPError as exc_429:
                        r2 = getattr(exc_429, "response", None)
                        if r2 is not None and r2.status_code == 429:
                            try:
                                _ra2 = r2.headers.get("Retry-After") if getattr(r2, "headers", None) else None
                                print(f"[checkout][debug] 429 retry {attempt+1}: nadal 429 Retry-After={_ra2}", flush=True)
                            except Exception:
                                print(f"[checkout][debug] 429 retry {attempt+1}: nadal 429", flush=True)
                            continue
                        raise
                else:
                    w.error_code = 429
                    try:
                        w.payment_status = f"rate_limit_conversations: {resp.text[:200]}"[:300]
                    except Exception:
                        w.payment_status = "rate_limit_conversations"
                    return w
            elif status == 403 and profil:
                w.build_error = _snippet(resp)
                t0u = time.monotonic()
                harvest = _odblokuj_profil(item_id, profil, UNLOCK_ITEMY_FALLBACK)
                w.timings["odblokowanie_camoufox"] = round((time.monotonic() - t0u) * 1000)
                konto = _zastosuj_cookies(konto, s, harvest.get("cookies") or {})
                t0u = time.monotonic()
                try:
                    txn, so_id, purchase_id = utworz_transakcje_full(item_id, seller_id, konto, session=s)
                except Exception as exc2:
                    w.timings["transakcja_po_odblokowaniu"] = round((time.monotonic() - t0u) * 1000)
                    w.error_code = -2
                    w.payment_status = f"transakcja_403_po_odblokowaniu: {exc2!r}"[:300]
                    return w
                w.timings["transakcja_po_odblokowaniu"] = round((time.monotonic() - t0u) * 1000)
            else:
                raise

        w.transaction_id = str(txn) if txn is not None else None
        w.timings["transaction"] = round((time.monotonic() - t0) * 1000)
        _mark("transaction", _m0)

        # SKIP-BUILD: purchase_id != null → checkout istnieje (retry).
        if purchase_id:
            w.purchase_id = purchase_id
            w.checkout_id = purchase_id
            details = _PICKUP_CACHE.get((konto.anon_id, so_id)) if so_id else {}
            r_pd = None
            if details:
                t0 = time.monotonic(); _m0 = _now_ms()
                r_pd = _put_pickup_details(s, w.checkout_id, details)
                w.timings["put_pickup_details"] = round((time.monotonic() - t0) * 1000)
                _mark("put_pickup_details", _m0)
                w.status_pickup_details = r_pd.status_code
            checksum = ""
            if r_pd is not None and r_pd.status_code == 200:
                checksum = (_find_checksum(_resp_json(r_pd)) or [""])[0]
            else:
                t0 = time.monotonic(); _m0 = _now_ms()
                r_pm0 = _put_payment_method(s, w.checkout_id, pay_in_method)
                w.timings["put_payment_method"] = round((time.monotonic() - t0) * 1000)
                _mark("put_payment_method", _m0)
                w.status_payment_method = r_pm0.status_code
                if r_pm0.status_code == 200:
                    checksum = (_find_checksum(_resp_json(r_pm0)) or [""])[0]
            if proba_payment and checksum:
                t0 = time.monotonic(); _m0 = _now_ms()
                r_pay = _payment(s, w.checkout_id, checksum, incognia_token)
                w.timings["payment"] = round((time.monotonic() - t0) * 1000)
                _mark("payment", _m0)
                w.status_payment = r_pay.status_code
                if r_pay.status_code == 200:
                    pj = _resp_json(r_pay)
                    w.payment_status = ((pj.get("payment") or {}).get("status"))
                    act = pj.get("action") or {}
                    w.action_type = act.get("type")
                    w.action_payload = act.get("parameters") or act
                    w.redirect_url = ((act.get("parameters") or {}).get("url") or "")
                    if act.get("type") == "SCA_REQUIRED":
                        w.correlation_id = (act.get("parameters") or {}).get("correlation_id")
                else:
                    w.error_code = (_resp_json(r_pay) or {}).get("code")
                    try:
                        w.payment_status = f"payment_error: {r_pay.text[:300]}"
                    except Exception:
                        pass
            return w

        # 2. Build + pickup_point RÓWNOLEGLE + pipelined early PUT (warm path).
        s_pick = pobierz_sesje(konto, "pickup")
        s_put = pobierz_sesje(konto, "put")
        cached_pd = _PICKUP_CACHE.get((konto.anon_id, so_id)) if so_id else None

        early_put = {}
        def _maybe_early_put(c_id: str, _ck: str | None):
            if c_id and cached_pd is not None and "f" not in early_put:
                early_put["f"] = put_ex.submit(_put_pickup_details, s_put, c_id, cached_pd)

        t0 = time.monotonic(); _m0 = _now_ms()
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="checkout-iso") as put_ex:
            f_build = put_ex.submit(_build, s, int(txn), "", konto, on_early_checkout_id=_maybe_early_put)

            def _pick():
                if not so_id or cached_pd is not None:
                    return {}
                la, lo = _COORDS_CACHE.get(konto.anon_id, (None, None))
                if la is None or lo is None:
                    try:
                        rb = f_build.result()
                    except Exception as exc:
                        print(f"[checkout] _pick: build future rzucił wyjątek: {exc!r}", flush=True)
                        return {}
                    if rb.status_code != 200:
                        return {}
                    comp2 = ((_resp_json(rb).get("checkout") or {}).get("components") or {})
                    coords2 = ((comp2.get("shipping_address") or {}).get("address") or {}).get("coordinates") or {}
                    la, lo = coords2.get("latitude"), coords2.get("longitude")
                if la is None or lo is None:
                    return {}
                return _get_pickup_point(s_pick, so_id, la, lo)

            f_pick = put_ex.submit(_pick)

            try:
                r_build = f_build.result()
            except Exception as exc:
                w.timings["build+pickup_point"] = round((time.monotonic() - t0) * 1000)
                _mark("build+pickup_point", _m0)
                w.status_build = None
                w.error_code = -1
                try:
                    w.payment_status = f"build_exception: {exc!r}"[:300]
                except Exception:
                    pass
                return w
            try:
                point = f_pick.result()
            except Exception as exc:
                print(f"[checkout] _pick rzucił wyjątek (build OK): {exc!r}", flush=True)
                point = {}

        w.timings["build+pickup_point"] = round((time.monotonic() - t0) * 1000)
        _mark("build+pickup_point", _m0)
        w.status_build = r_build.status_code

        # Cache koordynatów z builda na kolejne zakupy (adres stały per konto, klucz: anon_id).
        if r_build.status_code == 200:
            _c = ((_resp_json(r_build).get("checkout") or {}).get("components") or {})
            _co = ((_c.get("shipping_address") or {}).get("address") or {}).get("coordinates") or {}
            if _co.get("latitude") and _co.get("longitude"):
                _COORDS_CACHE[konto.anon_id] = (_co["latitude"], _co["longitude"])

        if r_build.status_code == 403 and profil:
            # DataDome challenge -> odblokuj profil przez Camoufox (slider) i ponów.
            # Najpierw target item (token JWE dla jego transakcji); gdy item sprzedany
            # (redirect -> brak "Kup teraz" -> token null) -> fallback na znane dobre
            # itemy. Liczą się MOCNE cookies — token jest opcjonalny (baseline 10/10
            # build=200 bez tokenów). NIE podmieniamy mocnego datadome na słabe.
            w.build_error = _snippet(r_build)
            t0 = time.monotonic()
            harvest = _odblokuj_profil(item_id, profil, UNLOCK_ITEMY_FALLBACK)
            w.timings["odblokowanie_camoufox"] = round((time.monotonic() - t0) * 1000)
            konto = _zastosuj_cookies(konto, s, harvest.get("cookies") or {})
            # Token używamy tylko gdy harvest poszedł na TYM SAMYM itemie (transakcja
            # z jego strony). Z innego itemu -> sam cookies (bezpieczniej niż obcy JWE).
            incognia_token = harvest.get("token") if harvest.get("item_used") == item_id else ""
            t0 = time.monotonic()
            r_build = _build(s, int(w.transaction_id), incognia_token, konto)
            w.timings["build_po_odblokowaniu"] = round((time.monotonic() - t0) * 1000)
            w.status_build = r_build.status_code

        if r_build.status_code != 200:
            w.error_code = r_build.status_code
            w.build_error = w.build_error or _snippet(r_build)
            return w

        bj = _resp_json(r_build)
        checkout = bj.get("checkout") or {}
        w.checkout_id = checkout.get("id")
        # checkout.id to ten sam identyfikator co purchase_id (ANALIZA_PURCHASE_ID_ZRODLO.md).
        w.purchase_id = checkout.get("id")
        comps = checkout.get("components") or {}
        rate_uuid = ((comps.get("shipping_pickup_details") or {}).get("pickup_details") or {}).get("selected_rate_uuid")
        checksum_build = (_find_checksum(bj) or [""])[0]

        details = cached_pd or _details(rate_uuid, point)
        if not cached_pd and point:
            _PICKUP_CACHE[(konto.anon_id, so_id)] = _details(rate_uuid, point)

        r_pd = None
        if "f" in early_put:
            try:
                r_pd = early_put["f"].result()
            except Exception as exc:
                print(f"[checkout] early PUT pickup_details rzucił: {exc!r}", flush=True)
                r_pd = None

        r_pm = None
        r_pay = None
        s_pay = pobierz_sesje(konto, "payment") if proba_payment else None
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="checkout-put") as put_ex2:
            t0 = time.monotonic(); _m0 = _now_ms()
            f_pd = None
            if r_pd is None and details:
                f_pd = put_ex2.submit(_put_pickup_details, s, w.checkout_id, details)
            f_pm = put_ex2.submit(_put_payment_method, s, w.checkout_id, pay_in_method) if proba_payment else None
            f_pay = put_ex2.submit(_payment, s_pay, w.checkout_id, checksum_build, incognia_token) if proba_payment else None
            if f_pd is not None:
                try:
                    r_pd = f_pd.result()
                except Exception as exc:
                    print(f"[checkout] PUT pickup_details rzucił: {exc!r}", flush=True)
                    r_pd = None
            if f_pm is not None:
                try:
                    r_pm = f_pm.result()
                except Exception as exc:
                    print(f"[checkout] PUT payment_method rzucił: {exc!r}", flush=True)
                    r_pm = None
            if f_pay is not None:
                try:
                    r_pay = f_pay.result()
                except Exception as exc:
                    print(f"[checkout] payment future rzucił: {exc!r}", flush=True)
                    r_pay = None
        if r_pd is not None:
            w.timings["put_pickup_details"] = round((time.monotonic() - t0) * 1000)
            _mark("put_pickup_details", _m0)
            w.status_pickup_details = r_pd.status_code
        if r_pm is not None:
            w.timings["put_payment_method"] = round((time.monotonic() - t0) * 1000)
            _mark("put_payment_method", _m0)
            w.status_payment_method = r_pm.status_code

        checksum = checksum_build
        if r_pd is not None and r_pd.status_code == 200:
            checksum = (_find_checksum(_resp_json(r_pd)) or [""])[0] or checksum
        if r_pm is not None and r_pm.status_code == 200:
            checksum = (_find_checksum(_resp_json(r_pm)) or [""])[0] or checksum
        if r_pm is not None and r_pm.status_code != 200:
            try:
                w.payment_status = f"put_payment_method_error: {r_pm.text[:300]}"
            except Exception:
                pass

        if proba_payment:
            # Jeżeli równoległy payment nie zwrócił 200 (stale checksum lub wyjątek),
            # ponawiamy z ostatecznym checksum (z PUT).
            if r_pay is None or r_pay.status_code != 200:
                t0 = time.monotonic(); _m0 = _now_ms()
                r_pay = _payment(s, w.checkout_id, checksum, incognia_token)
                w.timings["payment"] = round((time.monotonic() - t0) * 1000)
                _mark("payment", _m0)
            w.status_payment = r_pay.status_code
            if r_pay.status_code == 200:
                pj = _resp_json(r_pay)
                w.payment_status = ((pj.get("payment") or {}).get("status"))
                act = pj.get("action") or {}
                w.action_type = act.get("type")
                w.action_payload = act.get("parameters") or act
                w.redirect_url = ((act.get("parameters") or {}).get("url") or "")
                if act.get("type") == "SCA_REQUIRED":
                    w.correlation_id = (act.get("parameters") or {}).get("correlation_id")
            else:
                w.error_code = (_resp_json(r_pay) or {}).get("code")
                try:
                    w.payment_status = f"payment_error: {r_pay.text[:400]}"
                except Exception:
                    pass

    # Podsumowanie czasowe telemetrii v2
    t_end_total_ms = int(time.time() * 1000)
    checkout_dur = t_end_total_ms - _t0_ms
    det_dur = (detection_span.get("dur_ms", 0) if detection_span else 0)
    net_wait = sum(s.get("dur_ms", 0) for s in _spans.values() if s.get("type") == "NET")
    total_cycle = det_dur + checkout_dur
    local_cpu = max(0, total_cycle - net_wait)
    net_pct = round((net_wait / max(1, total_cycle)) * 100, 1)

    w.summary_timings = {
        "total_full_cycle_ms": total_cycle,
        "detection_ms": det_dur,
        "checkout_to_payment_ms": checkout_dur,
        "net_wait_ms": net_wait,
        "local_cpu_ms": local_cpu,
        "net_ratio_pct": net_pct,
    }
    w.spans = _spans
    w.step_marks = _marks
    return w
