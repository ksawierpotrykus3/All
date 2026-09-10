# Równoległy payment z put_pickup_details (O-B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **STATUS (2026-09-02):** Zaimplementowane i zweryfikowane testami (111/111 przechodzi). Kroki commitów NIE zostały wykonane (na żądanie — oczekują na decyzję o commicie).
> **Odchylenie od planu:** priorytet checksum zmieniony z dwóch osobnych `if` na `if/elif` — `pickup_details` ma pierwszeństwo nad `payment_method`, zgodnie z intencją dokumentacji („PD jest ZAWSZE potrzebny; PM służy tylko do zdobycia checksum gdy PD odrzucony"). W teście fallbacku bez `elif` checksum z PD byłby nadpisywany przez PM.

**Goal:** Skrócić pełny checkout (z płatnością) o ~320 ms przez uruchomienie `POST /checkout/payment` równolegle z `PUT pickup_details`, zamiast sekwencyjnie po nim.

**Architecture:** W fazie po buildzie odpalamy `_payment` w osobnym wątku z własną sesją curl_cffi (wariant `"payment"`, bo `Session` nie jest thread-safe), używając `checksum_build` jako pierwszej próby. Równolegle lecą PUT-y. Jeśli payment z `checksum_build` zawiedzie (stale checksum), wykonujemy fallback: ponowienie `_payment` z checksum uzyskanym z odpowiedzi PUT. Logika jest w pełni testowalna przez mock HTTP — bez wymogu żywej karty.

**Tech Stack:** Python 3.11, `curl_cffi`, `concurrent.futures.ThreadPoolExecutor`, `pytest`.

**Dowody bazowe (plik na dysku):**
- [payment_demo_1788303188687.json](file:///f:/PROJEKTY/vinted/bot/output/payment_demo_1788303188687.json): `put_pickup_details=984ms`, `payment=320ms` → zrównoleglenie daje `max(984, 320)=984ms` zamiast `984+320=1304ms` (**−320 ms**).
- [bench_micro.json](file:///f:/PROJEKTY/vinted/bot/output/bench_micro.json): O2 równoległe PUT-y = 49.9% zysku — potwierdza skuteczność zrównoleglania operacji sieciowych.

---

## File Structure

- **Modify:** `bot/src/vintedbot/checkout.py` — sesja `"payment"` w `prewarm_sesje`/`upkeep_sesji` oraz refaktor bloku payment.
- **Test:** `bot/tests/test_checkout.py` — nowe testy O-B.

---

## Task 1: Sesja wariantu "payment" (prewarm + upkeep)

**Files:**
- Modify: `bot/src/vintedbot/checkout.py:205-234`

- [ ] **Step 1: Dodaj wariant "payment" do pętli prewarm i upkeep**

W funkcji `prewarm_sesje` (linia 214) oraz `upkeep_sesji` (linia 225) zmień krotki wariantów z trzech na cztery warianty.

W `prewarm_sesje`:

```python
    for wariant in ("glowna", "pickup", "detekcja", "payment"):
        s = pobierz_sesje(konto, wariant)
        try:
            s.get("https://www.vinted.pl/api/v2/users/current", timeout=REQUEST_TIMEOUT, **tls_kwargs())
        except Exception:
            pass
```

W `upkeep_sesji`:

```python
    for wariant in ("glowna", "pickup", "detekcja", "payment"):
        s = _SESJE.get(f"{konto.anon_id}:{wariant}")
        if s:
            try:
                if hasattr(s, "upkeep"):
                    s.upkeep()
                else:
                    s.get("https://www.vinted.pl/api/v2/users/current", timeout=5, **tls_kwargs())
            except Exception:
                pass
```

- [ ] **Step 2: Uruchom istniejące testy (regresja)**

Run: `cd f:\PROJEKTY\vinted\bot ; python -m pytest tests/test_checkout.py -q`
Expected: wszystkie dotychczasowe testy przechodzą (nie zmieniamy logiki, tylko liczbę wariantów).

- [ ] **Step 3: Commit**

```bash
git add bot/src/vintedbot/checkout.py
git commit -m "feat(checkout): add payment session variant to prewarm/upkeep"
```

---

## Task 2: Równoległy payment z fallbackiem

**Files:**
- Modify: `bot/src/vintedbot/checkout.py:769-834`

- [ ] **Step 1: Napisz test weryfikujący równoległe uruchomienie payment**

Dopisz do `bot/tests/test_checkout.py` (za istniejącym `test_O2_puty_rownolegle_obie_200`):

```python
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
                time.sleep(0.3)  # PD trwa dłużej niż payment
                return _resp({"checkout": {"checksum": "cs_pd"}})
            return _resp({"checkout": {"checksum": "cs_pm"}})
        return _resp({})

    _patch_http(monkeypatch, handler)

    w = zrealizuj_zakup(item_id=7, seller_id=9, konto=KonfiguracjaKonta(cookies={"a": "1"}), proba_payment=True)

    assert w.status_payment == 200
    assert w.status_pickup_details == 200
    # payment i PUT PD wystartowały w zbliżonym czasie (równolegle, nie sekwencyjnie).
    pay_start = next(t for m, u, t in start_times if "payment" in u and m == "post")
    pd_start = next(t for m, u, t in start_times if u.endswith("/checkout") and m == "put")
    # Różnica startów < 0.2s (gdyby sekwencyjnie, payment czekałby 0.3s na PD).
    assert abs(pay_start - pd_start) < 0.2
```

- [ ] **Step 2: Uruchom test — oczekiwany FAIL**

Run: `cd f:\PROJEKTY\vinted\bot ; python -m pytest tests/test_checkout.py::test_OB_payment_rownolegle_z_put_pickup_details -v`
Expected: FAIL — payment nadal startuje po zakończeniu PUT-ów (różnica startów >= 0.3s).

- [ ] **Step 3: Zrefaktoruj blok payment na równoległy z fallbackiem**

W `zrealizuj_zakup`, zastąp obecny blok (od `r_pd = None` przez blok `if proba_payment:` do końca) następującym kodem. Kluczowe zmiany:
- pobierz sesję `s_pay = pobierz_sesje(konto, "payment")` (osobna — thread-safe),
- w executorze PUT-ów dodaj trzeci future `f_pay` wywołujący `_payment(s_pay, w.checkout_id, checksum_build, incognia_token)`,
- po zebraniu PUT-ów sprawdź wynik payment; jeśli `status_code != 200`, wykonaj fallback `_payment` z ostatecznym checksum.

```python
        r_pd = None
        r_pm = None
        # O-B: payment startuje równolegle z PUT-ami, używając checksum_build (znanego
        # zaraz po buildzie). Osobna sesja "payment" — curl_cffi Session nie jest
        # thread-safe. Fallback: gdy payment z checksum_build zawiedzie (stale checksum),
        # ponawiamy z checksum z odpowiedzi PUT.
        s_pay = pobierz_sesje(konto, "payment") if proba_payment else None
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="checkout-put") as put_ex:
            t0 = time.monotonic(); _m0 = _now_ms()
            if details:
                f_pd = put_ex.submit(_put_pickup_details, s, w.checkout_id, details)
            else:
                f_pd = None
            f_pm = put_ex.submit(_put_payment_method, s, w.checkout_id, pay_in_method) if proba_payment else None
            f_pay = put_ex.submit(_payment, s_pay, w.checkout_id, checksum_build, incognia_token) if proba_payment else None
            try:
                r_pd = f_pd.result() if f_pd is not None else None
            except Exception as exc:
                print(f"[checkout] PUT pickup_details future rzucił wyjątek: {exc!r}", flush=True)
            try:
                r_pm = f_pm.result() if f_pm is not None else None
            except Exception as exc:
                print(f"[checkout] PUT payment_method future rzucił wyjątek: {exc!r}", flush=True)
            try:
                r_pay = f_pay.result() if f_pay is not None else None
            except Exception as exc:
                print(f"[checkout] payment future rzucił wyjątek: {exc!r}", flush=True)
                r_pay = None
        # Po `with` executor zamknięty; futures zwolnione.
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
```

- [ ] **Step 4: Uruchom nowy test — oczekiwany PASS**

Run: `cd f:\PROJEKTY\vinted\bot ; python -m pytest tests/test_checkout.py::test_OB_payment_rownolegle_z_put_pickup_details -v`
Expected: PASS

- [ ] **Step 5: Napisz test fallbacku (stale checksum)**

Dopisz do `bot/tests/test_checkout.py`:

```python
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
            # checksum_build będzie "stary"
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

    # Dwa wywołania payment: pierwsze ze "stary" checksum (409), drugie z "nowy" (200).
    assert len(payment_calls) == 2
    assert payment_calls[0]["checksum"] == "stary"
    assert payment_calls[1]["checksum"] == "nowy"
    assert w.status_payment == 200
```

- [ ] **Step 6: Uruchom test fallbacku — oczekiwany PASS**

Run: `cd f:\PROJEKTY\vinted\bot ; python -m pytest tests/test_checkout.py::test_OB_payment_fallback_gdy_checksum_build_stale -v`
Expected: PASS

- [ ] **Step 7: Uruchom pełny suite checkoutu (regresja)**

Run: `cd f:\PROJEKTY\vinted\bot ; python -m pytest tests/test_checkout.py -q`
Expected: wszystkie testy przechodzą, w tym istniejące `test_O2_*` i `test_zrealizuj_zakup_z_payment`.

- [ ] **Step 8: Commit**

```bash
git add bot/src/vintedbot/checkout.py bot/tests/test_checkout.py
git commit -m "feat(checkout): run payment in parallel with pickup_details (O-B)"
```

---

## Task 3: Pełny suite + weryfikacja telemetrii

**Files:**
- Test: `bot/tests/` (całość)

- [ ] **Step 1: Uruchom pełny suite jednostkowy**

Run: `cd f:\PROJEKTY\vinted\bot ; python -m pytest -q`
Expected: całość przechodzi (baza ~103 testów + 2 nowe).

- [ ] **Step 2: Potwierdź spójność licznika executorów**

Test `test_kazdy_checkout_dostaje_wlasny_executor` oczekiwał 6 executorów (max_workers 2 lub 3). Po zmianie `max_workers=3` w bloku PUT sprawdź, czy nadal przechodzi. Jeżeli asercja `all(mw in (2, 3))` zawiedzie (bo max_workers pozostało 3, co jest w zakresie), test przechodzi bez zmian. Nie modyfikuj testu, chyba że faktycznie zawiedzie.

- [ ] **Step 3: Commit ewentualnych poprawek**

```bash
git add -A
git commit -m "test(checkout): verify O-B parallel payment across full suite"
```

---

## Uwaga o weryfikacji end-to-end

Testy jednostkowe dowodzą **struktury równoległej i fallbacku**, ale NIE dowodzą, że `checksum_build` jest akceptowany przez prawdziwy endpoint `payment` (to wymaga żywej karty). To pozostaje [HIPOTEZA] do potwierdzenia testem live `payment_demo` po dodaniu karty do konta. Fallback w kodzie gwarantuje, że nawet gdyby `checksum_build` był nieakceptowany, checkout kończy się poprawnym payment (jak przed zmianą) — bez regresji.