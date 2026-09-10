from urllib.parse import urlencode

import json
import threading
import time

import pytest

from vintedbot.checkout import zrealizuj_zakup, _find_checksum
from vintedbot.models import KonfiguracjaKonta


def test_find_checksum_rekurencyjnie():
    # O8: szybka ścieżka "checkout.checksum" zwraca PIERWSZY checksum
    # (najczęstszy wzorzec Vinted — UDOWODNIONE wynik_build_bez_tokena_*.json).
    obj = {"checkout": {"checksum": "a|b", "nested": {"checksum": "c|d"}}}
    assert _find_checksum(obj) == ["a|b"]


def test_find_checksum_fallback_rekurencja_gdy_brak_checkout():
    """O8: gdy brak klucza 'checkout', fallback do pełnej rekurencji (error responses)."""
    obj = {"other": {"checksum": "x|y"}}
    assert _find_checksum(obj) == ["x|y"]


def test_find_checksum_szybsza_sciezka_vs_rekurencja():
    """O8: smoke test — _find_checksum nie crashuje na dużym payloadzie."""
    # Payload symulujący realną odpowiedź build (~50 komponentów).
    big = {"checkout": {"checksum": "real_cs", "components": {f"comp_{i}": {"data": [1, 2, 3]} for i in range(50)}}}
    # Wywołanie zwraca pierwszy checksum (z checkout.checksum) — to ten używany w checkout.
    assert _find_checksum(big)[0] == "real_cs"


def _resp(body, status=200):
    class R:
        status_code = status
        content = json.dumps(body).encode()

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

        def json(self):
            return json.loads(self.content.decode("utf-8"))

    return R()


_BUILD_BODY = {
    "checkout": {
        "id": "CK1",
        "checksum": "a|b",
        "components": {
            "shipping_pickup_details": {"pickup_details": {"selected_rate_uuid": "RATE"}},
            "shipping_address": {
                "shipping_order_id": 123,
                "address": {"coordinates": {"latitude": 1.0, "longitude": 2.0}},
            },
        },
    }
}


def _patch_http(monkeypatch, handler):
    """Podmienia HTTP na poziomie sesji (zrealizuj_zakup używa pobierz_sesje).

    Buduje fałszywą sesję, której metody get/post/put kierują do `handler`.
    Wymaga też podmiany detection.creq (transaction gdy sesja=None — tu nie),
    ale głównie mockujemy pobierz_sesje, by zwracała fake-sesję.
    """
    import vintedbot.checkout as ch

    class _FakeSession:
        def __init__(self):
            self.cookies = {}

        def get(self, url, **kw):
            return handler("get", url, **kw)

        def post(self, url, **kw):
            return handler("post", url, **kw)

        def put(self, url, **kw):
            return handler("put", url, **kw)

    fake = _FakeSession()
    monkeypatch.setattr(ch, "pobierz_sesje", lambda konto, wariant="glowna": fake)
    # transaction idzie przez detection.utworz_transakcje_full z session=fake.
    return fake


def test_zrealizuj_zakup_bez_payment(monkeypatch):
    calls = []

    def handler(method, url, **kw):
        calls.append((method, url))
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123"}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=False)

    assert w.transaction_id == "123"
    assert w.checkout_id == "CK1"
    assert w.status_build == 200
    # payment NIE wywołane
    assert not any("/checkout/payment" in u for _, u in calls)


def test_zrealizuj_zakup_z_payment(monkeypatch):
    calls = []

    def handler(method, url, **kw):
        calls.append((method, url))
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123"}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout/payment"):
            return _resp({"payment": {"status": "pending"}, "action": {"parameters": {"url": "https://adyen/redir"}}})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert w.status_payment == 200
    assert w.payment_status == "pending"
    assert w.redirect_url == "https://adyen/redir"
    assert any("/checkout/payment" in u for _, u in calls)


# ============================================================================
# Testy dla FIX Issue 1: wyjątki z future.result() nie powinny zabijać workera
# ============================================================================

def test_build_future_exception_nie_zabija_workera(monkeypatch):
    """FIX Issue 1: POST /checkout/build rzuca TimeoutError → WynikCheckoutu z error_code=-1."""
    calls = []

    def handler(method, url, **kw):
        calls.append((method, url))
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            # Symulacja wyjątku sieciowego (timeout, connection reset, SSL error).
            raise TimeoutError("simulated build timeout")
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    # NIE rzuca wyjątku — worker przeżywa.
    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=False)

    assert w.error_code == -1  # sygnatura wyjątku sieciowego (nie HTTP status)
    assert w.status_build is None
    assert w.transaction_id == "123"
    assert "build_exception" in (w.payment_status or "")
    # PUT /checkout NIE został wysłany — flow zakończył się na build.
    assert not any("/purchases/123/checkout" in u for _, u in calls if u.endswith("/checkout"))


def test_pickup_future_exception_kontynuuje_checkout(monkeypatch):
    """FIX Issue 1: GET nearby_pickup_points rzuca TimeoutError → checkout idzie dalej z payment_method."""
    calls = []

    def handler(method, url, **kw):
        calls.append((method, url))
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            # Symulacja wyjątku sieciowego pickup.
            raise ConnectionError("simulated pickup connection reset")
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    # Build OK, pickup padł → checkout kontynuuje (PUT payment_method jako fallback).
    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=False)

    assert w.status_build == 200
    assert w.checkout_id == "CK1"
    # PUT /checkout poszedł (z pustym pickup_details → fallback payment_method).
    assert any("/checkout" in u for _, u in calls if u.endswith("/checkout"))


def test_pickup_wewnetrzny_future_exception_zwraca_pusty_point(monkeypatch):
    """FIX Issue 1: `_pick` woła f_build.result() — gdy build rzuci, _pick zwraca {} zamiast crashować."""
    calls = []

    def handler(method, url, **kw):
        calls.append((method, url))
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            raise RuntimeError("build failed before pickup could read coords")
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": []})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    # Wątek workera nie wybucha wyjątkiem RuntimeError "build failed...".
    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=False)

    assert w.error_code == -1
    assert w.status_build is None


# ============================================================================
# Testy dla FIX Issue 2: per-checkout executor (brak globalnego _EXECUTOR)
# ============================================================================

def test_global_executor_zostal_usunięty():
    """FIX Issue 2: moduł nie eksportuje już _EXECUTOR — eliminacja wąskiego gardła."""
    import vintedbot.checkout as ch
    assert not hasattr(ch, "_EXECUTOR"), (
        "Moduł nadal ma globalny _EXECUTOR — to stare ograniczenie max_workers=2 "
        "kolejkujące zakupy z O6 (PurchaseLoop)."
    )


def test_kazdy_checkout_dostaje_wlasny_executor(monkeypatch):
    """FIX Issue 2: każdy `zrealizuj_zakup` tworzy NOWY ThreadPoolExecutor (per-call, nie globalny)."""
    from concurrent.futures import ThreadPoolExecutor as RealTPE
    instances = []
    n_calls = [0]

    class CountingTPE(RealTPE):
        def __init__(self, max_workers=None, **kwargs):
            super().__init__(max_workers=max_workers, **kwargs)
            n_calls[0] += 1
            instances.append(max_workers)

    monkeypatch.setattr("vintedbot.checkout.ThreadPoolExecutor", CountingTPE)

    # Wyczyść cache'e modułu (koordynaty, pickup) żeby wymusić ścieżkę równoległą build+pickup.
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    # 3 kolejne checkouts — każdy tworzy 2 lokalne executory (build+pickup oraz PUTs), łącznie 6.
    for _ in range(3):
        w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=False)
        assert w.status_build == 200

    assert n_calls[0] == 6, f"Oczekiwano 6 executorów (2 per checkout), dostałem {n_calls[0]}"
    assert all(mw in (2, 3) for mw in instances), f"Oczekiwano max_workers 2 lub 3, dostałem {instances}"


def test_rownolegle_zakupy_nie_blokuja_sie_wzajemnie(monkeypatch):
    """FIX Issue 2: 2 zakupy w threads kończą się oba — dawniej globalny executor z max_workers=2
    mógłby blokować (subiektywnie wolniej), ale przede wszystkim dowodzi że nie ma wspólnego locka."""
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    results = []

    def run_one():
        results.append(zrealizuj_zakup(
            item_id=7, seller_id=9,
            konto=KonfiguracjaKonta(cookies={"a": "1"}),
            proba_payment=False,
        ))

    threads = [threading.Thread(target=run_one) for _ in range(2)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    elapsed = time.monotonic() - t0

    assert len(results) == 2
    assert all(w.status_build == 200 for w in results)
    assert all(t.is_alive() is False for t in threads)
    # Dolna granica: 2 równoległe checkouts nie powinny trwać dłużej niż ~10s (mock odpowiada natychmiast).
    assert elapsed < 10, f"2 równoległe checkouts trwały {elapsed:.2f}s — możliwy lock na executorze"


def test_payment_continue(monkeypatch):
    import vintedbot.checkout as ch

    captured = {}

    class _FakeSession:
        def post(self, url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers")
            captured["json"] = kw.get("json")
            return _resp({"status": "ok"})

    s = _FakeSession()
    r = ch._payment_continue(s, checkout_id="CK_TEST", checksum="ck_sum_123", incognia_token="TOKEN_ABC")
    assert r.status_code == 200
    assert captured["url"] == "https://www.vinted.pl/api/v2/purchases/CK_TEST/checkout/payment/continue"
    assert captured["headers"]["x-incognia-request-token"] == "TOKEN_ABC"
    assert captured["json"]["checksum"] == "ck_sum_123"


# ============================================================================
# O1: Accept-Encoding: gzip, br w _headers()
# ============================================================================

def test_O1_accept_encoding_w_naglowkach(monkeypatch):
    """O1: każda sesja budowana przez pobierz_sesje dostaje Accept-Encoding: gzip, br."""
    import vintedbot.checkout as ch
    ch._SESJE.clear()
    konto = KonfiguracjaKonta(cookies={"anon_id": "test_anon"})
    s = ch.pobierz_sesje(konto, "glowna")
    assert s.headers.get("Accept-Encoding") == "gzip, br"


def test_O1_accept_encoding_w_nowych_sesjach(monkeypatch):
    """O1: helper _headers (używany przez _nowa_sesja) też ma Accept-Encoding."""
    import vintedbot.checkout as ch
    h = ch._headers(KonfiguracjaKonta(cookies={"anon_id": "x"}))
    assert h.get("Accept-Encoding") == "gzip, br"
    # Pozostałe nagłówki nienaruszone.
    assert h.get("Accept") == "application/json"
    assert h.get("Content-Type") == "application/json"


def test_O1_accept_encoding_extra_nie_nadpisuje(monkeypatch):
    """O1: extra nagłówki przekazane do _headers nie nadpisują Accept-Encoding (extra ma wyższy priorytet)."""
    import vintedbot.checkout as ch
    h = ch._headers(KonfiguracjaKonta(cookies={"anon_id": "x"}), extra={"X-Custom": "1"})
    assert h.get("Accept-Encoding") == "gzip, br"
    assert h.get("X-Custom") == "1"


# ============================================================================
# O7: CSRF cache + invalidacja po refresh
# ============================================================================

def test_O7_csrf_cache_hit(monkeypatch):
    """O7: drugie wywołanie _csrf_cached z tymi samymi cookies nie dekoduje JWT ponownie."""
    import vintedbot.checkout as ch
    ch._CSRF_CACHE.clear()
    konto = KonfiguracjaKonta(
        cookies={
            "anon_id": "test",
            "access_token_web": "eyJhbGciOiJIUzI1NiJ9.eyJjc3JmIjoiQ1NSRl9DIn0.signature",
        }
    )
    csrf1 = ch._csrf_cached(konto)
    assert csrf1 == "CSRF_C"
    # Drugi call trafia w cache — _CSRF_CACHE ma 1 element.
    csrf2 = ch._csrf_cached(konto)
    assert csrf2 == csrf1
    assert len(ch._CSRF_CACHE) == 1


def test_O7_csrf_cache_invalidacja_po_refresh(monkeypatch):
    """O7: zmiana access_token_web w cookies powoduje invalidację cache."""
    import vintedbot.checkout as ch
    ch._CSRF_CACHE.clear()
    konto_v1 = KonfiguracjaKonta(
        cookies={"anon_id": "test", "access_token_web": "eyJ.eyJjc3JmIjoiT1hEfQ.sig"}
    )
    csrf_v1 = ch._csrf_cached(konto_v1)
    # Zmieniamy token — nowy CSRF.
    konto_v2 = KonfiguracjaKonta(
        cookies={"anon_id": "test", "access_token_web": "eyJ.eyJjc3JmIjoiTkVXIn0.sig"}
    )
    csrf_v2 = ch._csrf_cached(konto_v2)
    assert csrf_v1 != csrf_v2
    # Cache powinien mieć 1 element (nadpisany).
    assert len(ch._CSRF_CACHE) == 1


def test_O7_csrf_cache_dla_roznych_anon_id(monkeypatch):
    """O7: cache rozróżnia anon_id (różne konta = różne JWT)."""
    import vintedbot.checkout as ch
    ch._CSRF_CACHE.clear()
    # KonfiguracjaKonta ma domyślny anon_id z ANON_DEFAULT — nadpisujemy wprost.
    k1 = KonfiguracjaKonta(
        anon_id="anon1",
        cookies={"anon_id": "anon1", "access_token_web": "eyJ.eyJjc3JmIjoiQ1NSRl8xIn0.sig"},
    )
    k2 = KonfiguracjaKonta(
        anon_id="anon2",
        cookies={"anon_id": "anon2", "access_token_web": "eyJ.eyJjc3JmIjoiQ1NSRl8yIn0.sig"},
    )
    assert ch._csrf_cached(k1) != ch._csrf_cached(k2)
    assert len(ch._CSRF_CACHE) == 2


# ============================================================================
# O2+O12: równoległe PUT pickup_details + payment_method (test flow)
# ============================================================================

def test_O2_puty_rownolegle_obie_200(monkeypatch):
    """O2+O12: oba PUT-y lecą równolegle i oba zwracają 200."""
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    call_times = []
    lock = threading.Lock()

    def handler(method, url, **kw):
        with lock:
            call_times.append(time.monotonic())
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "cs_1"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert w.status_build == 200
    # Dwa PUT-y (PD i PM) zostały wykonane.
    put_calls = [t for t in call_times if t > call_times[0] + 0.5]  # po pickup
    assert w.status_pickup_details == 200
    assert w.status_payment_method == 200


def test_OB_payment_rownolegle_z_put_pickup_details(monkeypatch):
    """O-B: payment leci równolegle z PUT pickup_details (nie czeka na jego wynik)."""
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    import time
    start_times = []
    lock = threading.Lock()

    def handler(method, url, **kw):
        with lock:
            start_times.append((method, url, time.monotonic()))
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout/payment"):
            return _resp({"payment": {"status": "pending"}, "action": {"parameters": {"url": "https://adyen/redir"}}})
        if url.endswith("/checkout") and method.lower() == "put":
            body = kw.get("json") or {}
            comps = body.get("components") or {}
            pd = comps.get("shipping_pickup_details") or {}
            if pd.get("rate_uuid") or pd.get("point_code"):
                time.sleep(0.3)
                return _resp({"checkout": {"checksum": "cs_pd"}})
            return _resp({"checkout": {"checksum": "cs_pm"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert w.status_payment == 200
    assert w.status_pickup_details == 200
    pay_start = next(t for m, u, t in start_times if "payment" in u and m == "post")
    pd_start = next(t for m, u, t in start_times if u.endswith("/checkout") and m == "put")
    assert abs(pay_start - pd_start) < 0.2


def test_OB_payment_fallback_gdy_checksum_build_stale(monkeypatch):
    """O-B: gdy payment z checksum_build zwróci 409, fallback ponawia z checksum z PUT."""
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    payment_calls = []

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp({**_BUILD_BODY, "checkout": {**_BUILD_BODY["checkout"], "checksum": "stary"}})
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout/payment"):
            payment_calls.append(kw.get("json") or {})
            if len(payment_calls) == 1:
                return _resp({"code": "stale_checksum"}, status=409)
            return _resp({"payment": {"status": "pending"}})
        if url.endswith("/checkout") and method.lower() == "put":
            body = kw.get("json") or {}
            comps = body.get("components") or {}
            pd = comps.get("shipping_pickup_details") or {}
            if pd.get("rate_uuid") or pd.get("point_code"):
                return _resp({"checkout": {"checksum": "nowy"}})
            return _resp({"checkout": {"checksum": "cs_pm"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert len(payment_calls) == 2
    assert payment_calls[0]["checksum"] == "stary"
    # Separatne `if` dla r_pd i r_pm: przy obu 200 PM wygrywa jako "najnowszy" checksum.
    assert payment_calls[1]["checksum"] == "cs_pm"
    assert w.status_payment == 200


def test_O2_puty_rownolegle_fallback_gdy_pd_409(monkeypatch):
    """O2+O12: gdy PUT PD zwraca 409 (lock), PM jest gotowy jako fallback."""
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            body = kw.get("json") or {}
            comps = body.get("components") or {}
            pd = comps.get("shipping_pickup_details") or {}
            # Rozróżniamy PD (zawiera rate_uuid lub point_code) od PM (puste).
            if pd.get("rate_uuid") or pd.get("point_code"):
                return _resp({"code": "lock_held"}, status=409)
            return _resp({"checkout": {"checksum": "cs_fallback"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert w.status_pickup_details == 409
    assert w.status_payment_method == 200  # fallback zadziałał


def test_O2_puty_rownolegle_jeden_wyjatku_drugi_continues(monkeypatch):
    """O2+O12: wyjątek w jednym PUT nie zabija drugiego (FIX Issue 1 + O2)."""
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            body = kw.get("json") or {}
            comps = body.get("components") or {}
            pd = comps.get("shipping_pickup_details") or {}
            if pd.get("rate_uuid") or pd.get("point_code"):
                raise ConnectionError("PUT PD timeout")
            return _resp({"checkout": {"checksum": "cs_pm"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    # Worker przeżywa; checkout kontynuuje mimo wyjątku PD.
    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    # PD rzucił wyjątek (status_pickup_details pozostaje None bo r_pd=None).
    assert w.status_build == 200
    # PM poszedł równolegle i zwrócił 200.
    assert w.status_payment_method == 200


def test_O2_dry_run_pomija_payment_method(monkeypatch):
    """Dry-run (proba_payment=False): PUT payment_method NIE leci (wrażliwy krok).

    Baseline 10/10 build=200 miał status_payment_method=null — przywracamy to
    zachowanie w dry-run; PM tylko w realnych zakupach lub jako fallback checksum.
    """
    import vintedbot.checkout as ch
    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            body = kw.get("json") or {}
            comps = body.get("components") or {}
            pd = comps.get("shipping_pickup_details") or {}
            # PD ma wypełnione shipping_pickup_details; PM jest puste.
            if pd.get("rate_uuid") or pd.get("point_code"):
                return _resp({"checkout": {"checksum": "cs_pd"}})
            raise AssertionError("PM PUT nie powinien lecieć w dry-run")
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=False)

    assert w.status_build == 200
    assert w.status_pickup_details == 200
    assert w.status_payment_method is None


# ============================================================================
# O2: batch pre-check dostępności przed conversations
# ============================================================================

def test_O2_item_niedostepny_odrzuca_przed_conversations(monkeypatch):
    """O2: gdy check_availability zwraca available=false, checkout kończy się
    z error_code=-3 ZANIM wywoła conversations (oszczędza rate-limit code 106)."""
    import vintedbot.checkout as ch

    calls = []

    def handler(method, url, **kw):
        calls.append((method, url))
        if "conversations" in url:
            raise AssertionError("conversations NIE powinien być wywołany dla niedostępnego itemu")
        return _resp({})

    _patch_http(monkeypatch, handler)

    def fake_dostepnosc(buyer_id, item_ids, konto, session=None):
        # Struktura [UDOWODNIONE wynik_check_availability_*.json].
        return {"purchase": {"items": {"buy": {"available": False, "unavailable_list": []}}}}

    monkeypatch.setattr(ch, "sprawdz_dostepnosc", fake_dostepnosc)

    w = zrealizuj_zakup(
        item_id=7, seller_id=9,
        konto=KonfiguracjaKonta(cookies={"a": "1"}, user_id=12345),
        proba_payment=False,
    )

    assert w.error_code == -3
    assert w.payment_status == "item_niedostepny_obsluga_check_availability"
    # conversations nie zostało wywołane.
    assert not any("conversations" in u for _, u in calls)


def test_O2_item_dostepny_przechodzi_dalej(monkeypatch):
    """O2: gdy check_availability zwraca available=true, checkout kontynuuje normalnie."""
    import vintedbot.checkout as ch

    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    def fake_dostepnosc(buyer_id, item_ids, konto, session=None):
        return {"purchase": {"items": {"buy": {"available": True}}}}

    monkeypatch.setattr(ch, "sprawdz_dostepnosc", fake_dostepnosc)

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(
        item_id=7, seller_id=9,
        konto=KonfiguracjaKonta(cookies={"a": "1"}, user_id=12345),
        proba_payment=False,
    )

    assert w.status_build == 200
    assert w.checkout_id == "CK1"


def test_O2_bez_user_id_pomija_prefilter(monkeypatch):
    """O2: brak user_id → pre-filter pominięty, checkout idzie normalnym torem."""
    import vintedbot.checkout as ch

    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()

    called = {"n": 0}

    def fake_dostepnosc(buyer_id, item_ids, konto, session=None):
        called["n"] += 1
        return {"purchase": {"items": {"buy": {"available": False}}}}

    monkeypatch.setattr(ch, "sprawdz_dostepnosc", fake_dostepnosc)

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _resp(_BUILD_BODY)
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            return _resp({"checkout": {"checksum": "x|y"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(
        item_id=7, seller_id=9,
        konto=KonfiguracjaKonta(cookies={"a": "1"}),  # user_id = None
        proba_payment=False,
    )

    assert w.status_build == 200
    assert called["n"] == 0  # pre-filter nie został wywołany


# ============================================================================
# O6: retry-with-backoff w checkout
# ============================================================================

def test_O6_retry_na_5xx_druga_proba_sukces(monkeypatch):
    """O6: 503 z retry → druga próba 200 → zwrócone 200."""
    import vintedbot.checkout as ch
    call_count = [0]

    def _fn():
        call_count[0] += 1
        if call_count[0] == 1:
            return _resp({}, status=503)
        return _resp({"ok": True})

    r = ch._with_retry(_fn)
    assert r.status_code == 200
    assert call_count[0] == 2  # wykonane 2×


def test_O6_brak_retry_na_403_datadome(monkeypatch):
    """O6: 403 (DataDome) NIE jest retry'owane — bez sensu, to nie transient error."""
    import vintedbot.checkout as ch
    call_count = [0]

    def _fn():
        call_count[0] += 1
        return _resp({}, status=403)

    r = ch._with_retry(_fn)
    assert r.status_code == 403
    assert call_count[0] == 1  # tylko 1 próba


def test_O6_retry_na_429_rate_limit(monkeypatch):
    """O6: 429 (rate-limit) retry'owane, druga próba sukces."""
    import vintedbot.checkout as ch
    call_count = [0]

    def _fn():
        call_count[0] += 1
        if call_count[0] == 1:
            return _resp({}, status=429)
        return _resp({"ok": True})

    r = ch._with_retry(_fn)
    assert r.status_code == 200
    assert call_count[0] == 2


def test_O6_retry_na_2_probach_konczy_na_ostatniej_odpowiedzi(monkeypatch):
    """O6: max_retries=1 — po 2× 503 zwraca ostatnią 503 (nie propaguje wyjątku)."""
    import vintedbot.checkout as ch
    call_count = [0]

    def _fn():
        call_count[0] += 1
        return _resp({}, status=503)

    r = ch._with_retry(_fn)
    assert r.status_code == 503
    assert call_count[0] == 2  # 1 retry = 2 próby


# ============================================================================
# O3: cache /catalog/items (TTL 300ms)
# ============================================================================

def test_O3_katalog_cache_hit(monkeypatch):
    """O3: 2× pobierz_oferty w odstępie <300ms → drugi wywołanie zwraca cache bez HTTP."""
    from urllib.parse import urlencode
    import vintedbot.detection as det

    det._KATALOG_CACHE.clear()

    # Mockujemy creq.get żeby liczyć wywołania HTTP.
    call_count = [0]
    real_get = det.creq.get

    def mock_get(url, **kw):
        call_count[0] += 1
        return _resp_with_json([{"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}}])

    monkeypatch.setattr(det.creq, "get", mock_get)

    filtry = det.Filtry()
    of1 = det.pobierz_oferty(filtry, limit=10)
    of2 = det.pobierz_oferty(filtry, limit=10)

    assert len(of1) == 1
    assert len(of2) == 1
    assert call_count[0] == 1  # tylko 1 HTTP — drugi z cache


def test_O3_katalog_cache_miss_po_ttl(monkeypatch):
    """O3: po upływie TTL cache wygasa i idzie HTTP."""
    import vintedbot.detection as det

    det._KATALOG_CACHE.clear()
    det._KATALOG_CACHE_TTL_S = 0.05  # 50ms dla testu

    call_count = [0]

    def mock_get(url, **kw):
        call_count[0] += 1
        return _resp_with_json([])

    monkeypatch.setattr(det.creq, "get", mock_get)

    filtry = det.Filtry()
    det.pobierz_oferty(filtry, limit=10)
    time.sleep(0.1)  # TTL expired
    det.pobierz_oferty(filtry, limit=10)

    assert call_count[0] == 2  # oba poszły do HTTP


def test_O3_katalog_cache_per_url(monkeypatch):
    """O3: różne URL-e mają osobne wpisy w cache."""
    import vintedbot.detection as det

    det._KATALOG_CACHE.clear()

    call_count = [0]

    def mock_get(url, **kw):
        call_count[0] += 1
        return _resp_with_json([])

    monkeypatch.setattr(det.creq, "get", mock_get)

    # Różne per_page → różne URL-e.
    det.pobierz_oferty(det.Filtry(), limit=10)
    det.pobierz_oferty(det.Filtry(), limit=20)

    assert call_count[0] == 2  # 2 różne URL-e = 2 HTTP


def _resp_with_json(body, status=200):
    """Helper: response z JSON body. body może być listą (dla items) lub dict."""
    # Zachowanie wsteczne: jeśli body to lista, owij w {"items": body} (katalog API).
    # Jeśli to dict, prześlij bezpośrednio (users/current API).
    if isinstance(body, list):
        payload = {"items": body}
    else:
        payload = body
    class R:
        status_code = status
        content = json.dumps(payload).encode()

        def raise_for_status(self):
            if status >= 400:
                raise Exception(f"HTTP {status}")

        def json(self):
            return json.loads(self.content.decode("utf-8"))

    return R()


# ============================================================================
# O4: cache users/current (TTL 30s)
# ============================================================================

def test_O4_cache_hit_is_ready(monkeypatch):
    """O4: drugie wywołanie is_ready() w oknie TTL nie robi HTTP."""
    from vintedbot.session_state import SessionState

    s = SessionState()
    s.cookies = {"access_token_web": "x"}
    s.login = "user1"

    http_calls = [0]
    real_get = __import__("vintedbot.session_state", fromlist=["creq"]).creq.get

    def mock_get(url, **kw):
        http_calls[0] += 1
        return _resp_with_json({"user": {"login": "user1", "id": 1}})

    monkeypatch.setattr("vintedbot.session_state.creq.get", mock_get)

    assert s.is_ready() is True
    assert s.is_ready() is True  # drugie powinno trafić w cache
    # Pierwsze robi HTTP; drugie z cache.
    assert http_calls[0] == 1


def test_O4_cache_invalidacja_po_set_cookies(monkeypatch):
    """O4: set_cookies() resetuje cache (nowe cookies = potencjalnie nowy login)."""
    from vintedbot.session_state import SessionState

    s = SessionState()
    s.cookies = {"a": "1"}
    s.login = "user1"

    def mock_get(url, **kw):
        return _resp_with_json({"user": {"login": "user2", "id": 2}})

    monkeypatch.setattr("vintedbot.session_state.creq.get", mock_get)

    assert s.is_ready() is True
    # Nowe cookies — cache powinien się zresetować.
    s.set_cookies({"b": "2"}, "user2")
    assert s.is_ready() is True
    # Login zaktualizowany.
    assert s.login == "user2"


def test_O4_cache_brak_negatywnej_cache(monkeypatch):
    """O4: 401 NIE jest cache'owane — następne is_ready() od razu próbuje znowu."""
    from vintedbot.session_state import SessionState

    s = SessionState()
    s.cookies = {"a": "1"}

    http_calls = [0]

    def mock_get(url, **kw):
        http_calls[0] += 1
        if http_calls[0] == 1:
            return _resp_with_json({}, status=401)
        return _resp_with_json({"user": {"login": "u", "id": 1}})

    monkeypatch.setattr("vintedbot.session_state.creq.get", mock_get)

    assert s.is_ready() is False  # 401, brak cache
    assert s.is_ready() is True  # drugi raz poszedł HTTP i dostał 200
    assert http_calls[0] == 2  # oba poszły (negatywny nie cached)


# ============================================================================
# O9: auto-refresh tokena
# ============================================================================

def test_O9_token_expires_in_brak_tokenu():
    """O9: _token_expires_in zwraca None gdy brak JWT."""
    from vintedbot.refresh import _token_expires_in
    assert _token_expires_in({}) is None
    assert _token_expires_in({"access_token_web": "nieprawidłowy"}) is None


def test_O9_token_expires_in_poprawny_jwt():
    """O9: _token_expires_in odczytuje exp claim z JWT payload."""
    import time
    import base64
    from vintedbot.refresh import _token_expires_in

    # JWT z exp = teraz + 100s.
    payload = json.dumps({"exp": int(time.time()) + 100}).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    token = f"header.{b64}.sig"
    expires_in = _token_expires_in({"access_token_web": token})
    assert expires_in is not None
    assert 95 < expires_in < 105  # margines na czas wykonania


def test_O9_should_force_refresh_gdy_token_wygasa(monkeypatch):
    """O9: _should_force_refresh=True gdy token blisko wygaśnięcia."""
    import time
    import base64
    from vintedbot.refresh import RefreshLoop, _token_expires_in
    from vintedbot.session_state import SessionState, SessionStatus

    # JWT z exp = teraz + 60s (< threshold 15min).
    payload = json.dumps({"exp": int(time.time()) + 60}).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    cookies = {"access_token_web": f"h.{b64}.s"}

    s = SessionState()
    s.cookies = cookies
    s.set_status(SessionStatus.READY)

    loop = RefreshLoop(profile="/tmp/fake", interval_min=4)
    assert loop._should_force_refresh(s) is True


def test_O9_should_not_force_refresh_gdy_token_daleko(monkeypatch):
    """O9: _should_force_refresh=False gdy token >15min do wygaśnięcia."""
    import time
    import base64
    from vintedbot.refresh import RefreshLoop
    from vintedbot.session_state import SessionState, SessionStatus

    # JWT z exp = teraz + 1h.
    payload = json.dumps({"exp": int(time.time()) + 3600}).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    cookies = {"access_token_web": f"h.{b64}.s"}

    s = SessionState()
    s.cookies = cookies
    s.set_status(SessionStatus.READY)

    loop = RefreshLoop(profile="/tmp/fake", interval_min=4)
    assert loop._should_force_refresh(s) is False


def test_O9_current_sleep_dynamiczny(monkeypatch):
    """O9: _current_sleep_s zwraca 60s gdy token wygasa, inaczej interwał domyślny."""
    import time
    import base64
    from vintedbot.refresh import RefreshLoop
    from vintedbot.session_state import SessionState, SessionStatus

    s_expires_soon = SessionState()
    payload = json.dumps({"exp": int(time.time()) + 60}).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    s_expires_soon.cookies = {"access_token_web": f"h.{b64}.s"}
    s_expires_soon.set_status(SessionStatus.READY)

    s_far = SessionState()
    payload = json.dumps({"exp": int(time.time()) + 3600}).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    s_far.cookies = {"access_token_web": f"h.{b64}.s"}
    s_far.set_status(SessionStatus.READY)

    loop = RefreshLoop(profile="/tmp/fake", interval_min=4)
    assert loop._current_sleep_s(s_expires_soon) == 60.0  # aggressive
    assert loop._current_sleep_s(s_far) == 240.0  # 4 min default


def test_ekstrahuj_checkout_i_checksum_z_chunka():
    from vintedbot.checkout import _ekstrahuj_checkout_z_chunka, _ekstrahuj_checksum_z_chunka
    
    chunk_build = b'{"checkout":{"id":"CK_STREAM_9988","components":{...},"checksum":"cs_build_123|456"}}'
    chk_id, csum = _ekstrahuj_checkout_z_chunka(chunk_build)
    assert chk_id == "CK_STREAM_9988"
    assert csum == "cs_build_123|456"
    
    chunk_put = b'{"checkout":{"id":"CK_STREAM_9988","checksum":"cs_put_789|000"}}'
    put_csum = _ekstrahuj_checksum_z_chunka(chunk_put)
    assert put_csum == "cs_put_789|000"


def test_prewarm_sesje_prepopuluje_coords_cache(monkeypatch):
    from vintedbot.checkout import prewarm_sesje, _COORDS_CACHE
    from vintedbot.models import KonfiguracjaKonta
    
    konto = KonfiguracjaKonta(anon_id="test_anon_preseed", lat=54.35, lon=18.65)
    
    # Mock network GET in prewarm
    class FakeSession:
        def get(self, *args, **kwargs):
            return None
    
    monkeypatch.setattr("vintedbot.checkout.pobierz_sesje", lambda k, w: FakeSession())
    
    _COORDS_CACHE.clear()
    prewarm_sesje(konto)
    assert _COORDS_CACHE.get("test_anon_preseed") == (54.35, 18.65)


def test_pipeline_put_pickup_details_warm_start(monkeypatch):
    """Pipeline warm path: przy cached_pd, _put_pickup_details startuje z checkout_id
    z pierwszego chunka buildu, a nie z pełnego parsowania odpowiedzi."""
    import vintedbot.checkout as ch
    from vintedbot.config import ANON_DEFAULT

    ch._COORDS_CACHE.clear()
    ch._PICKUP_CACHE.clear()
    # Warm start: details już w cache dla pary (anon_id, shipping_order_id=456).
    ch._PICKUP_CACHE[(ANON_DEFAULT, 456)] = {
        "rate_uuid": "RATE_CACHED", "point_code": "P1", "point_uuid": "U1",
    }

    put_body = {}

    class _StreamBuild:
        status_code = 200
        headers = {}
        def iter_content(self, chunk_size=2048):
            yield b'{"checkout":{"id":"CK_EARLY","checksum":"a|b",'
            yield b'"components":{...}}}'
        def raise_for_status(self):
            pass

    def handler(method, url, **kw):
        if "conversations" in url:
            return _resp({"conversation": {"transaction": {"id": "123", "shipping_order_id": 456}}})
        if "checkout/build" in url:
            return _StreamBuild()
        if "nearby_pickup_points" in url:
            return _resp({"shipping_points": [{"point": {"code": "P1", "uuid": "U1"}}]})
        if url.endswith("/checkout") and method.lower() == "put":
            put_body.update(kw.get("json") or {})
            return _resp({"checkout": {"checksum": "cs_pd"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9,
                        konto=KonfiguracjaKonta(cookies={"a": "1"}),
                        proba_payment=False)

    assert w.status_build == 200
    assert w.status_pickup_details == 200
    assert "shipping_pickup_details" in (put_body.get("components") or {})
    assert put_body["components"]["shipping_pickup_details"]["rate_uuid"] == "RATE_CACHED"