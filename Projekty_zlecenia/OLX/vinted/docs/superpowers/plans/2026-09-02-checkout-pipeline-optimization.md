# Checkout Pipeline Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skrócić krytyczną ścieżkę checkoutu o ~1.0 s na ścieżce warm (powtórny zakup od tego samego sprzedawcy) przez zrównoleglenie `put_pickup_details` z pozostałą częścią builda.

**Architecture:** `_build` już posiada martwy parametr `on_early_checkout_id`, ale `zrealizuj_zakup` go nie przekazuje. Dodajemy dedykowaną sesję `put`, podajemy callback do `_build`, który po wyłowieniu `checkout_id` z pierwszego chunka strumienia natychmiast odpała `_put_pickup_details` (warm path, gdy `cached_pd` jest znane). Kluczowe uzupełnienie: `_build` musi zachować pełne ciało odpowiedzi (dziś w streamingu jest porzucane), inaczej `_resp_json(r_build)` zwróci `{}`.

**Tech Stack:** Python 3.11+, curl_cffi, pytest (monkeypatch, wzorzec `_patch_http` z `test_checkout.py`), ThreadPoolExecutor.

---

## Korekty z weryfikacji dowodów (przed implementacją)

Trzy z czterech wcześniej zidentyfikowanych problemów NIE wymagają fixa:

1. **O1 („podwójny sleep daemona”) — NIE JEST BŁĘDEM.** W `daemon.run()` `monitoruj(..., max_iter=1)` przerywa pętlę PRZED wewnętrznym sleepem (warunek `iteracja >= max_iter` następuje przed `time.sleep` w `detection.py` L288-L298). Efektywny okres pollingu to `RTT (~0.36 s) + stop_event.wait(1.0) ≈ 1.36 s`, co jest **bezpieczne** względem rate-limitu ~0.83 req/s. Agresywne skracanie zwiększa ryzyko 429 bez znaczącego zysku. **Brak zmian.**

2. **Z3 („rate_uuid nie cache'owany”) — JUŻ ZROBIONE.** `rate_uuid` jest zapisywany w `_PICKUP_CACHE` przez `_details(rate_uuid, point)` ([checkout.py L404-L413](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L404-L413)) i zapisywany w L787-L789. **Brak zmian.**

3. **Z4 („check_availability w gorącej ścieżce”) — JUŻ OPŁACALNE.** Pre-filter ~110 ms odrzuca niedostępne oferty zanim zużyje rate-limit `conversations` (code 106). Przeniesienie do tła POLL wprowadziłoby ryzyko wyścigu (oferta mogłaby zniknąć między prefiltrem a transakcją). **Brak zmian — to świadomy kompromis, nie wąskie gardło.**

**Jedyny opłacalny fix:** pipeline `put_pickup_details` na ścieżce warm. Dowód z [test1_determinizm_with_evidence_1788304069.json](file:///f:/PROJEKTY/vinted/bot/output/test1_determinizm_with_evidence_1788304069.json): `put_pickup_details` = 1062–1172 ms, wykonuje się sekwencyjnie po `build+pickup_point` = 1203–1703 ms, mimo że `checkout_id` jest znany już z pierwszego chunka buildu.

**Ważne ograniczenie zakresu:** zysk dotyczy WYŁĄCZNIE ścieżki warm (powtórny zakup od tego samego sprzedawcy, gdy `_PICKUP_CACHE` ma wpis `(anon_id, so_id)`). Na ścieżce cold `details` nie są znane przed pickup_point, więc nie ma czego pipelinować. W praktyce bot częściej kupuje od różnych sprzedawców, więc realny zysk jest ograniczony do powtórnych transakcji.

---

## File Structure

- `bot/src/vintedbot/checkout.py` — dodanie wariantu sesji `put`, poprawka `_build` (zachowanie ciała w streamingu), pipeline w `zrealizuj_zakup`.
- `bot/tests/test_checkout.py` — test pipeline'u warm path.

---

## Task 1: Wariant sesji `put` + zachowanie ciała builda w streamingu

**Files:**
- Modify: `f:\PROJEKTY\vinted\bot\src\vintedbot\checkout.py`

- [ ] **Step 1: Dodaj `put` do wariantów `prewarm_sesje` i `upkeep_sesji`**

W `prewarm_sesje` (obecnie L218) i `upkeep_sesji` (obecnie L230) rozszerz krotkę wariantów o `"put"`:

```python
for wariant in ("glowna", "pickup", "detekcja", "payment", "put"):
```

- [ ] **Step 2: Popraw `_build`, by zachował pełne ciało w trybie streamingu**

Obecnie `_build` (L363-L388) w streamingu czyta tylko pierwszy chunk i `break`-uje, przez co `r.content` jest puste. Dodaj akumulację chunków i zwracaj lekki wrapper z kompletem `status_code` + `content`.

Zastąp ciało `_build` następującym:

```python
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
```

Uwaga: `_BuildResp` musi być zdefiniowany przed `_build` w module. `_ekstrahuj_checkout_z_chunka` już zwraca `(checkout_id, checksum)` — callback teraz dostaje oba.

- [ ] **Step 3: Uruchom testy, by potwierdzić brak regresji**

Run: `cd f:\PROJEKTY\vinted\bot; python -m pytest tests/test_checkout.py -q`
Expected: PASS (istniejące testy nie przechodzą przez streaming, bo `on_early_checkout_id` jeszcze nie jest przekazywany)

- [ ] **Step 4: Commit**

```bash
git add bot/src/vintedbot/checkout.py
git commit -m "feat(checkout): preserve build body in stream mode + add put session variant"
```

---

## Task 2: Pipeline `put_pickup_details` na ścieżce warm

**Files:**
- Modify: `f:\PROJEKTY\vinted\bot\src\vintedbot\checkout.py` (funkcja `zrealizuj_zakup`, sekcja L686-L827)
- Test: `f:\PROJEKTY\vinted\bot\tests\test_checkout.py`

- [ ] **Step 1: Napisz test — early PUT na warm path używa wczesnego `checkout_id`**

Dodaj do `test_checkout.py`:

```python
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
    # PUT dostał wypełnione shipping_pickup_details (warm details z cache).
    assert "shipping_pickup_details" in (put_body.get("components") or {})
    assert put_body["components"]["shipping_pickup_details"]["rate_uuid"] == "RATE_CACHED"
```

Uwaga: `_patch_http` mockuje `pobierz_sesje`, więc `s_put` zwróci tę samą fake-sesję; handler rozróżnia PUT po URL `/checkout` — to wystarcza.

- [ ] **Step 2: Uruchom test — oczekuj FAIL**

Run: `cd f:\PROJEKTY\vinted\bot; python -m pytest tests/test_checkout.py::test_pipeline_put_pickup_details_warm_start -v`
Expected: FAIL — obecnie `on_early_checkout_id` nie jest przekazywany, więc pipeline nie działa (brak wczesnego PUT albo `put_body` pusty).

- [ ] **Step 3: Zaimplementuj pipeline w `zrealizuj_zakup`**

Zamień dwa osobne bloki `with ThreadPoolExecutor` (build+pickup w L691-L733, potem PUT w L798-L818) jednym spójnym przepływem.

Wstaw następujący kod w miejsce L686 (komentarz `# 2. Build + pickup_point RÓWNOLEGLE ...`) aż do L827 (koniec bloku PUT):

```python
        # 2. Build + pickup_point RÓWNOLEGLE + pipelined early PUT (warm path).
        s_pick = pobierz_sesje(konto, "pickup")  # osobna sesja (thread-safety)
        s_put = pobierz_sesje(konto, "put")      # sesja dla early PUT (thread-safety)
        cached_pd = _PICKUP_CACHE.get((konto.anon_id, so_id)) if so_id else None

        early_put = {}  # kontener na future wczesnego PUT + przechwycony checksum
        def _maybe_early_put(c_id: str, ck: str | None):
            if c_id and cached_pd is not None and "f" not in early_put:
                early_put["checksum"] = ck
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

        # Cache koordynatów z builda na kolejne zakupy (adres stały per konto).
        if r_build.status_code == 200:
            _c = ((_resp_json(r_build).get("checkout") or {}).get("components") or {})
            _co = ((_c.get("shipping_address") or {}).get("address") or {}).get("coordinates") or {}
            if _co.get("latitude") and _co.get("longitude"):
                _COORDS_CACHE[konto.anon_id] = (_co["latitude"], _co["longitude"])

        if r_build.status_code == 403 and profil:
            # (istniejąca logika odblokowania DataDome — BEZ ZMIAN)
            w.build_error = _snippet(r_build)
            t0 = time.monotonic()
            harvest = _odblokuj_profil(item_id, profil, UNLOCK_ITEMY_FALLBACK)
            w.timings["odblokowanie_camoufox"] = round((time.monotonic() - t0) * 1000)
            konto = _zastosuj_cookies(konto, s, harvest.get("cookies") or {})
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
        w.purchase_id = checkout.get("id")
        comps = checkout.get("components") or {}
        rate_uuid = ((comps.get("shipping_pickup_details") or {}).get("pickup_details") or {}).get("selected_rate_uuid")
        checksum_build = (_find_checksum(bj) or [""])[0]

        details = cached_pd or _details(rate_uuid, point)
        if not cached_pd and point:
            _PICKUP_CACHE[(konto.anon_id, so_id)] = _details(rate_uuid, point)

        # Early PUT (warm path) — odebierz future jeśli pipeline wystartował.
        r_pd = None
        if "f" in early_put:
            try:
                r_pd = early_put["f"].result()
            except Exception as exc:
                print(f"[checkout] early PUT pickup_details rzucił: {exc!r}", flush=True)
                r_pd = None

        r_pm = None
        # PUT pickup_details (jeśli nie zrobiony przez pipeline) + PUT payment_method.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="checkout-put") as put_ex2:
            t0 = time.monotonic(); _m0 = _now_ms()
            f_pd = None
            if r_pd is None and details:
                f_pd = put_ex2.submit(_put_pickup_details, s, w.checkout_id, details)
            f_pm = put_ex2.submit(_put_payment_method, s, w.checkout_id, pay_in_method) if proba_payment else None
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
        if r_pd is not None:
            w.timings["put_pickup_details"] = round((time.monotonic() - t0) * 1000)
            _mark("put_pickup_details", _m0)
            w.status_pickup_details = r_pd.status_code
        if r_pm is not None:
            w.timings["put_payment_method"] = round((time.monotonic() - t0) * 1000)
            _mark("put_payment_method", _m0)
            w.status_payment_method = r_pm.status_code
```

Kontynuacja (checksum + payment) — fragment od L829 (`checksum = checksum_build`) pozostaje BEZ ZMIAN.

**Uwaga o `proba_payment=False`:** w obecnym kodzie `_put_payment_method` leci tylko, gdy `proba_payment=True`. Powyższy kod zachowuje to przez `if proba_payment else None`. W dry-run (`proba_payment=False`) z warm path dostajemy wyłącznie wczesny `put_pickup_details` — identycznie jak baseline.

- [ ] **Step 4: Uruchom test pipeline'u**

Run: `cd f:\PROJEKTY\vinted\bot; python -m pytest tests/test_checkout.py::test_pipeline_put_pickup_details_warm_start -v`
Expected: PASS

- [ ] **Step 5: Uruchom pełny zestaw testów checkoutu**

Run: `cd f:\PROJEKTY\vinted\bot; python -m pytest tests/test_checkout.py -q`
Expected: PASS (wszystkie — w tym `test_O2_dry_run_pomija_payment_method`, `test_O2_puty_rownolegle_*`, `test_OB_*`)

- [ ] **Step 6: Uruchom pełny zestaw testów jednostkowych**

Run: `cd f:\PROJEKTY\vinted\bot; python -m pytest -q`
Expected: 112 passed (111 dotychczas + 1 nowy)

- [ ] **Step 7: Commit**

```bash
git add bot/src/vintedbot/checkout.py bot/tests/test_checkout.py
git commit -m "feat(checkout): pipeline put_pickup_details via early checkout_id on warm path"
```

---

## Weryfikacja końcowa (po implementacji)

Wymagany live-test na koncie testowym (profil `profil_firefox_135`) przed wdrożeniem, bo zmiana dotyka krytycznej ścieżki z baseline 100% build=200:

Run: `cd f:\PROJEKTY\vinted\bot; python scripts/test1_determinizm_with_evidence.py`
Expected: 5/5 build=200.

**Ograniczenie weryfikacji:** skrypt `test1_determinizm_with_evidence.py` kupuje 5 RÓŻNYCH ofert od różnych sprzedawców, więc mierzy głównie cold path (pipeline nie zadziała — brak `cached_pd`). Aby zweryfikować realny zysk warm path, potrzeba 2+ zakupów od TEGO SAMEGO sprzedawcy. Bez takiego testu zysk ~1.0 s pozostaje nieudowodniony w ścieżce produkcyjnej.

Bez pozytywnego live-testu NIE łączymy do gałęzi produkcyjnej (AGENTS.md: „success rate >90%”).

---

## Zasoby wymagane

- **Techniczne:** konto testowe + profil `profil_firefox_135`; dla pełnej weryfikacji warm path — scenariusz 2+ zakupów od tego samego sprzedawcy.
- **Ludzkie:** recenzja kodu przed live-testem (zmiana krytycznej ścieżki).

## Ryzyka i ich mitygacja

| Ryzyko | Mitygacja |
|---|---|
| `_BuildResp` nie jest w pełni zgodny z `creq.Response` (brak `.headers`, `.raise_for_status`) | `_snippet` i `_resp_json` używają tylko `.status_code`/`.content`/`.text`; kod 403 sprawdzany po `status_code`. Live-test potwierdza. |
| Streaming zmienia zachowanie keep-alive | `_build` teraz konsumuje cały strumień (nie `break`), co poprawnie zamyka/zwalnia połączenie. |
| Race: early PUT 409 gdy Vinted jeszcze nie skompletował buildu | Baseline już toleruje 409 PD (fallback `put_payment_method`); early PUT na warm path używa tych samych details co normalny PUT. |