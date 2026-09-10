from datetime import datetime, timezone
import json
import os
import re
import random
import time
from pathlib import Path
from urllib.parse import urlencode

from curl_cffi import requests as creq

from .config import IMPERSONATE, CONVERSATIONS_URL, CHECK_AVAILABILITY_URL, tls_kwargs
from .json_utils import json_loads, json_dumps
from .models import Filtry, Oferta, KonfiguracjaKonta

BASE = "https://www.vinted.pl/api/v2/catalog/items"
REFRESH_URL = "https://www.vinted.pl/web/api/auth/refresh"

_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 8.0


def _nastepny_interwal(bledy: int, jitter: float = 0.2) -> float:
    """Wykładniczy backoff z jitterem. `bledy` = liczba kolejnych porażek (>=1)."""
    raw = min(_BACKOFF_BASE * (2 ** (bledy - 1)), _BACKOFF_CAP)
    if jitter <= 0:
        return raw
    zjitter = raw * (1 + random.uniform(-jitter, jitter))
    return round(min(zjitter, _BACKOFF_CAP), 3)


def _sesja_aktywna(dane: dict | None) -> bool:
    """Sesja jest zalogowana, gdy users/current zawiera login."""
    if not dane:
        return False
    user = dane.get("user") or {}
    return bool(user.get("login"))


def _wymagany_csrf_token() -> str:
    """Zwraca X-CSRF-Token z env. Brak zmiennej to błąd konfiguracji."""
    token = os.environ.get("VINTED_CSRF_TOKEN")
    if not token:
        raise RuntimeError(
            "Brak VINTED_CSRF_TOKEN. Ustaw zmienną środowiskową przed uruchomieniem bota."
        )
    return token





def _csrf_dla_refresh(cookies: dict[str, str]) -> str:
    """CSRF do refresh: najpierw env, potem z JWT access_token_web."""
    token = os.environ.get("VINTED_CSRF_TOKEN")
    if token:
        return token
    from .config import csrf_z_cookies
    csrf = csrf_z_cookies(cookies)
    if csrf:
        return csrf
    raise RuntimeError("Brak CSRF: ustaw VINTED_CSRF_TOKEN albo zaloguj (access_token_web).")


def odswiez_token(cookies: dict[str, str], session=None) -> dict[str, str]:
    """Wymienia access_token_web używając refresh_token_web. Modyfikuje `cookies` w miejscu.

    session: opcjonalna współdzielona sesja keep-alive (reuse TLS). Bez niej — creq.post.
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": _csrf_dla_refresh(cookies),
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    try:
        if session is not None:
            r = session.post(REFRESH_URL, headers=headers, timeout=10, **tls_kwargs())
        else:
            r = creq.post(REFRESH_URL, headers=headers, cookies=cookies,
                          impersonate=IMPERSONATE, timeout=10, **tls_kwargs())
        r.raise_for_status()
    except Exception as exc:
        # Awaria odświeżenia nie powinna zabijać pętli monitoringu.
        # Zwracamy cookies bez zmian; kolejna iteracja spróbuje ponownie.
        print(f"[vintedbot] odświeżenie tokenu nie powiodło się: {exc}", flush=True)
        return cookies

    data = json_loads(r.content)
    if data.get("access_token"):
        cookies["access_token_web"] = data["access_token"]
    # refresh_token_web może być rotowany przez set-cookie
    set_cookie = r.headers.get("set-cookie", "")
    m = re.search(r"refresh_token_web=([^;]+)", set_cookie)
    if m:
        cookies["refresh_token_web"] = m.group(1)
    return cookies


_KATALOG_CACHE: dict[str, tuple[float, list]] = {}
# O3: TTL cache dla odpowiedzi /catalog/items. Vinted odświeża katalog co ~1-3s,
# więc cache < 300ms eliminuje duplikat requestów w hot-loop (np. gdy 2 thready
# pollingu konkurują o ten sam URL). Klucz: URL z parametrami.
_KATALOG_CACHE_TTL_S = 0.3


def ekstrahuj_pierwszy_item_z_chunka(chunk_bytes: bytes) -> dict | None:
    """Szybki mikro-skaner: wyciąga pierwszy obiekt oferty z niekompletnego strumienia JSON."""
    if not chunk_bytes:
        return None
    text = chunk_bytes.decode("utf-8", errors="ignore")
    idx_start = text.find('"items":[')
    if idx_start == -1:
        return None
    sub = text[idx_start + 9:].lstrip()
    if not sub.startswith("{"):
        return None
    depth = 0
    end_idx = -1
    for i, ch in enumerate(sub):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
    if end_idx != -1:
        try:
            return json_loads(sub[:end_idx])
        except Exception:
            pass
    return None


def pobierz_oferty(filtry: Filtry, limit: int = 20, cookies: dict[str, str] | None = None,
                   session=None, on_early_item=None, stream: bool = False) -> list[Oferta]:
    """Pobiera oferty z katalogu Vinted.
    
    Gdy podano `on_early_item` lub `stream=True`, używa Early-Trigger Streaming Detection:
    w ułamku milisekundy od odebrania pierwszego chunka sieciowego (TTFB) parsuje
    najnowszą ofertę i natychmiast wywołuje `on_early_item(oferta)` w locie,
    nie czekając na zakończenie pobierania pozostałych ofert.
    """
    params = filtry.query_params()
    params["per_page"] = limit
    params["order"] = "newest_first"
    # Build URL manually to ensure exact query string order for mocking.
    url = f"{BASE}?{urlencode(params)}"
    # O3: cache <300ms eliminuje powtórne requesty (np. gdy ten sam URL jest pytany
    # przez retry lub współbieżny wątek). Zysk: -100% HTTP dla powtórzeń w oknie TTL.
    now = time.monotonic()
    cached = _KATALOG_CACHE.get(url)
    if cached and (now - cached[0]) < _KATALOG_CACHE_TTL_S:
        return list(cached[1])

    use_stream = stream or (on_early_item is not None)
    chunks = []
    early_triggered = False

    # O2: gdy podano współdzieloną sesję keep-alive (z checkout.pobierz_sesje),
    # reużywamy otwarte połączenie TLS — bez handshake'u (~125-500 ms) co poll.
    # Cookies są już w sesji (tworzona z konto.cookies). Bez sesji: fallback creq.get.
    if session is not None:
        r = session.get(url, timeout=10, stream=use_stream, **tls_kwargs())
        if r.status_code == 401 and cookies and "refresh_token_web" in cookies:
            odswiez_token(cookies, session=session)
            r = session.get(url, timeout=10, stream=use_stream, **tls_kwargs())
    else:
        r = creq.get(url, impersonate=IMPERSONATE, timeout=10, cookies=cookies, stream=use_stream, **tls_kwargs())
        if r.status_code == 401 and cookies and "refresh_token_web" in cookies:
            cookies = odswiez_token(cookies)
            r = creq.get(url, impersonate=IMPERSONATE, timeout=10, cookies=cookies, stream=use_stream, **tls_kwargs())
    r.raise_for_status()

    if use_stream and hasattr(r, "iter_content"):
        first_chunk_ts = None
        for chunk in r.iter_content(chunk_size=4096):
            if not chunk:
                continue
            if first_chunk_ts is None:
                first_chunk_ts = time.monotonic()
                if on_early_item is not None and not early_triggered:
                    early_raw = ekstrahuj_pierwszy_item_z_chunka(chunk)
                    if early_raw:
                        t_early_dur = round((first_chunk_ts - now) * 1000)
                        t_early_end_ms = int(time.time() * 1000)
                        early_span = {
                            "start_ms": t_early_end_ms - t_early_dur,
                            "end_ms": t_early_end_ms,
                            "dur_ms": t_early_dur,
                            "start_iso": datetime.fromtimestamp((t_early_end_ms - t_early_dur) / 1000, timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
                            "end_iso": datetime.fromtimestamp(t_early_end_ms / 1000, timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
                            "type": "NET_STREAM_TTFB",
                            "cf_ray": getattr(r, "headers", {}).get("cf-ray", "") if hasattr(r, "headers") else "",
                        }
                        early_oferta = Oferta.model_validate(early_raw)
                        early_oferta.detection_span = early_span
                        early_triggered = True
                        try:
                            on_early_item(early_oferta)
                        except Exception as e_cb:
                            print(f"[detection] błąd on_early_item: {e_cb!r}", flush=True)
            chunks.append(chunk)
        content_bytes = b"".join(chunks)
    else:
        content_bytes = r.content

    t_net_dur = round((time.monotonic() - now) * 1000)
    t_net_end_ms = int(time.time() * 1000)
    t_start_ms = t_net_end_ms - t_net_dur
    cf_ray = ""
    if hasattr(r, "headers") and r.headers:
        cf_ray = r.headers.get("cf-ray", "")

    data = json_loads(content_bytes)
    det_span = {
        "start_ms": t_start_ms,
        "end_ms": t_net_end_ms,
        "dur_ms": t_net_dur,
        "start_iso": datetime.fromtimestamp(t_start_ms / 1000, timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
        "end_iso": datetime.fromtimestamp(t_net_end_ms / 1000, timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
        "type": "NET",
        "cf_ray": cf_ray,
    }
    items = []
    for raw in data.get("items", []):
        o = Oferta.model_validate(raw)
        o.detection_span = det_span
        items.append(o)
    _KATALOG_CACHE[url] = (now, list(items))
    return items


def monitoruj(filtry, interwal=1.0, callback=None, max_iter=None, cookies=None,
              recorder=None, recorder_wewn=None, session=None, adaptuj_interwal=True,
              limit=10):
    """Pętla odpytywania z backoffem 429/403 i rozdzielonym pomiarem czasu.

    `recorder` zbiera RTT (cały `pobierz_oferty`), a `recorder_wewn` zbiera
    latencję wewnętrzną (od sparsowania odpowiedzi do końca callbacku).

    session: opcjonalna współdzielona sesja keep-alive (O2) — eliminuje handshake
    TLS co poll. adaptuj_interwal (O7): gdy średni RTT rośnie, skraca czysty
    `sleep` tak, by efektywny okres (RTT + sleep) był bliski `interwal` — utrzymuje
    maksymalną częstotliwość odpytywania bez przekraczania rate-limitu.

    limit (per_page): [UDOWODNIONE 2026-09-01] RTT rośnie z rozmiarem odpowiedzi —
    p50: 10->438 ms, 24->672 ms, 48->937 ms, 96->1203 ms (pomiar output/rtt_per_page.json).
    Nowe oferty są zawsze na początku (order=newest_first), więc mały per_page
    wystarcza do detekcji i przyspiesza pętlę ~2.7x.
    """
    znane: set[int] = set()
    iteracja = 0
    kolejne_bledy = 0
    rtt_srednia = 0.0  # wygładzona średnia RTT (s) do adaptacji interwału
    while max_iter is None or iteracja < max_iter:
        t0 = time.monotonic()
        try:
            oferty = pobierz_oferty(filtry, limit=limit, cookies=cookies, session=session)
        except Exception:
            kolejne_bledy += 1
            if recorder is not None:
                recorder.record_error()
            if recorder_wewn is not None:
                recorder_wewn.record_error()
            time.sleep(_nastepny_interwal(kolejne_bledy))
            iteracja += 1
            if max_iter is not None and iteracja >= max_iter:
                break
            continue
        kolejne_bledy = 0
        t_po_pobraniu = time.monotonic()
        rtt = t_po_pobraniu - t0
        if recorder is not None:
            recorder.add(rtt * 1000)
        nowe = [o for o in oferty if o.id not in znane]
        znane.update(o.id for o in oferty)
        # Latencja wewnętrzna mierzona zawsze po pobraniu (niezależnie od callbacku),
        # żeby "wewn" było spójne z "rtt" (niepuste w bench).
        t_po_przetworzeniu = time.monotonic()
        if recorder_wewn is not None:
            recorder_wewn.add((t_po_przetworzeniu - t_po_pobraniu) * 1000)
        if nowe and callback:
            callback(nowe)
        iteracja += 1
        if max_iter is not None and iteracja >= max_iter:
            break
        # O7: adaptacyjny interwał — odejmij zmierzony RTT od zadanego okresu,
        # by efektywna częstotliwość odpytywania była bliższa 1/interwal.
        # Wygładzanie EMA (alpha=0.3) tłumi jitter pojedynczych requestów.
        if adaptuj_interwal:
            rtt_srednia = rtt if rtt_srednia == 0.0 else 0.7 * rtt_srednia + 0.3 * rtt
            sleep_s = max(0.0, interwal - rtt_srednia)
        else:
            sleep_s = interwal
        time.sleep(sleep_s)


def ekstrahuj_transakcje_z_chunka(chunk_bytes: bytes) -> tuple[int | None, int | None, str | None]:
    """Mikro-skaner: wyciąga transaction_id, shipping_order_id i purchase_id z pierwszych bajtów odpowiedzi."""
    if not chunk_bytes:
        return None, None, None
    text = chunk_bytes.decode("utf-8", errors="ignore")
    m_txn = re.search(r'"transaction"\s*:\s*\{[^}]*"id"\s*:\s*(\d+)', text)
    txn_id = int(m_txn.group(1)) if m_txn else None
    m_so = re.search(r'"shipping_order_id"\s*:\s*(\d+)', text)
    so_id = int(m_so.group(1)) if m_so else None
    m_pur = re.search(r'"purchase_id"\s*:\s*"([^"]+)"', text)
    pur_id = m_pur.group(1) if m_pur else None
    return txn_id, so_id, pur_id


def utworz_transakcje(item_id: int, seller_id: int, konto: KonfiguracjaKonta) -> str:
    """POST /api/v2/conversations -> transaction_id. Zwraca tylko ID (kompatybilność)."""
    return utworz_transakcje_full(item_id, seller_id, konto)[0]


def utworz_transakcje_full(item_id: int, seller_id: int, konto: KonfiguracjaKonta,
                            session=None, on_early_transaction=None, stream: bool = False) -> tuple:
    """POST /api/v2/conversations -> (transaction_id, shipping_order_id, purchase_id).

    Gdy podano `on_early_transaction` lub `stream=True`, wyławia transaction_id
    z pierwszego odebranego pakietu sieciowego (TTFB) i natychmiast wywołuje callback,
    nie czekając na transfer pozostałych danych konwersacji.
    """
    _headers_txn = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": konto.csrf,
        "x-anon-id": konto.anon_id,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    at = konto.cookies.get("access_token_web")
    if at:
        _headers_txn["Authorization"] = f"Bearer {at}"
    _payload = {"initiator": "buy", "item_id": int(item_id), "opposite_user_id": int(seller_id)}
    use_stream = stream or (on_early_transaction is not None)
    if session is not None:
        r = session.post(CONVERSATIONS_URL, json=_payload, headers=_headers_txn,
                         timeout=10, stream=use_stream, **tls_kwargs())
    else:
        r = creq.post(
            CONVERSATIONS_URL,
            json=_payload,
            headers=_headers_txn,
            cookies=konto.cookies,
            impersonate=IMPERSONATE,
            stream=use_stream,
            **tls_kwargs(),
            timeout=10,
        )
    if r.status_code >= 400:
        print(f"[detection] conversations HTTP {r.status_code}: {r.text[:300]}", flush=True)
        r.raise_for_status()

    if use_stream and hasattr(r, "iter_content"):
        chunks = []
        early_fired = False
        for chunk in r.iter_content(chunk_size=4096):
            if not chunk:
                continue
            if on_early_transaction is not None and not early_fired:
                e_txn, e_so, e_pur = ekstrahuj_transakcje_z_chunka(chunk)
                if e_txn:
                    early_fired = True
                    try:
                        on_early_transaction((e_txn, e_so, e_pur))
                    except Exception as exc_cb:
                        print(f"[detection] błąd on_early_transaction: {exc_cb!r}", flush=True)
            chunks.append(chunk)
        content_bytes = b"".join(chunks)
    else:
        content_bytes = r.content

    data = json_loads(content_bytes)
    conv = data.get("conversation") or {}
    txn_obj = conv.get("transaction") or {}
    txn = data.get("transaction_id") or txn_obj.get("id") or conv.get("transaction_id")
    so_id = txn_obj.get("shipping_order_id")
    purchase_id = txn_obj.get("purchase_id")
    return txn, so_id, purchase_id


def sprawdz_dostepnosc(buyer_id: int | str, item_ids: list[int | str], konto: KonfiguracjaKonta,
                        session=None) -> dict:
    """POST /checkout/purchases/check_availability -> batch pre-check dostępności ofert (~110 ms).

    [UDOWODNIONE] Brak wymogu Incognii, format snake_case: {"buyer_id": ..., "item_ids": [...]}.
    Pozwala natychmiast odrzucić oferty niedostępne/kupione/zarezerwowane bez kosztu `conversations`.
    """
    _headers_avail = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": konto.csrf,
        "x-anon-id": konto.anon_id,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    at = konto.cookies.get("access_token_web")
    if at:
        _headers_avail["Authorization"] = f"Bearer {at}"
    _payload = {
        "buyer_id": str(buyer_id),
        "item_ids": [str(i) for i in item_ids],
    }
    if session is not None:
        r = session.post(CHECK_AVAILABILITY_URL, json=_payload, headers=_headers_avail,
                         timeout=10, **tls_kwargs())
    else:
        r = creq.post(
            CHECK_AVAILABILITY_URL,
            json=_payload,
            headers=_headers_avail,
            cookies=konto.cookies,
            impersonate=IMPERSONATE,
            **tls_kwargs(),
            timeout=10,
        )
    r.raise_for_status()
    return json_loads(r.content)


def utrzymuj_sesje(cookies: dict[str, str], co_ile_s: float = 1800.0, max_cykli: int | None = None):
    """Cyklicznie odświeża token sesji, żeby nie wygasła (~2h). Blokująca pętla.

    Zwraca, gdy `max_cykli` osiągnięte (lub przy Ctrl+C). Każdy cykl woła
    `odswiez_token()` i czeka `co_ile_s`. Domyślnie co 30 minut.
    """
    cykl = 0
    while max_cykli is None or cykl < max_cykli:
        try:
            odswiez_token(cookies)
            print(f"[vintedbot] sesja odświeżona (cykl {cykl + 1})", flush=True)
        except Exception as exc:
            print(f"[vintedbot] błąd utrzymania sesji: {exc}", flush=True)
        cykl += 1
        if max_cykli is not None and cykl >= max_cykli:
            break
        time.sleep(co_ile_s)
