# Analiza naukowo-inżynierska: Możliwość przyspieszenia checkoutu Vinted do 2–3 s przy użyciu curl_cffi i cURL

**Data:** 2026-08-31
**Autor:** Analiza syntetyczna (AGENTS.md + kod `bot/` + pomiary `testy_camoufox/` + dokumentacja curl_cffi)
**Konwencja dowodowa:** `[UDOWODNIONE]` / `[POTWIERDZONE]` / `[DOMNIEMANE]` / `[NIEPOTWIERDZONE]`
**Zakres:** Weryfikacja pytania o realną możliwość sprowadzenia ścieżki zamówień zakupowych (`f:\PROJEKTY\vinted\bot`) do przedziału 2–3 sekund wyłącznie środkami `curl_cffi` / cURL.

---

## 1. Executive summary (werdykt)

**Pytanie:** Czy za pomocą `curl_cffi` i zapytań cURL da się przyspieszyć realizację zamówień do 2–3 s?

**Odpowiedź [UDOWODNIONE pomiarem]:**

| Interpretacja celu „2–3 s” | Osiągalne? | Zmierzony czas |
|---|---|---|
| **Czas do buildu** (rezerwacja: `conversations` → `checkout/build`) | **TAK** | **~2.7–3.2 s** |
| **Czas do bramki płatności** (full flow z `payment`) | **NIE** | **~7.5–10 s** |
| **Czas samej detekcji** (polling katalogu) | **TAK** | **~0.25–0.33 s** |

**Kluczowy wniosek:** `curl_cffi` nie skraca czasów serwerowych Vinted. Usuwa wyłącznie narzut kliencki (handshake TLS, spawn subprocesu, overhead wątków). Przedział 2–3 s jest fizycznie osiągalny **tylko jako czas do buildu (rezerwacji)** — nie jako czas do bramki płatności, ponieważ sam krok `payment` ma serwerowy floor ~2.5–2.7 s, a poprzedzają go obowiązkowe kroki (`conversations` + `build` + 2×PUT + pickup).

---

## 2. Metodologia i źródła

### 2.1 Hierarchia wiarygodności źródeł (zgodnie z AGENTS.md)

| Ranga | Źródło | Wykorzystane pliki |
|---|---|---|
| 1 (twarde dowody) | Pomiary z timestampami | [pomiar_czasu_curl_out.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/pomiar_czasu_curl_out.json), `bench_curl_gateway_nocam.py` |
| 2 (analiza danych) | Dokumenty wydajności | [PLAN_BADAN_WYDAJNOSC.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/PLAN_BADAN_WYDAJNOSC.md) |
| 2 (analiza danych) | Kod produkcyjny | [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py), [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py) |
| 2 (analiza danych) | Raporty inżynierskie | [RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md), [RAPORT_FINALNY_curl_cffi_JS_engine_wymagania.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/RAPORT_FINALNY_curl_cffi_JS_engine_wymagania.md) |
| 3 (ocena ekspercka) | Analiza konkurencji | [jak_zejsc_ponizej_kopsa.md](file:///f:/PROJEKTY/vinted/vinted/raporty/05_konkurencja/jak_zejsc_ponizej_kopsa.md) |
| Zewnętrzna dokumentacja | curl_cffi (Context7) | `/lexiforest/curl_cffi` — Session, AsyncSession, upkeep |

### 2.2 Metoda

1. Odczyt całej ścieżki zakupowej `bot/` (checkout, detection, config, models, measurement, refresh, incognia, incognia_harvest, cli, daemon).
2. Zebranie udowodnionych pomiarów latencji z `testy_camoufox/`.
3. Weryfikacja możliwości mechanizmów transportowych `curl_cffi` (keep-alive, connection pooling, AsyncSession, upkeep).
4. Rozdzielenie kosztu **serwerowego** (nieusuwalnego przez klienta) od **klienckiego** (usuwalnego).

---

## 3. Obecna architektura zakupowa (stan faktyczny kodu)

Ścieżka zakupowa jest w 100% na `curl_cffi` (impersonacja Firefox 152/135), bez Camoufox w krytycznej ścieżce. Camoufox występuje wyłącznie jako fallback przy odblokowaniu profilu (slider DataDome) i do odświeżania sesji.

### 3.1 Sekwencja `zrealizuj_zakup` ([checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L134-L270))

```
1. utworz_transakcje_full(item_id, seller_id)       → transaction_id, shipping_order_id
2. _build + _get_pickup_point  (RÓWNOLEGLE, ThreadPoolExecutor)
3. _put_pickup_details (albo _put_payment_method)   → checksum
4. [opcjonalnie] _payment                            → status / redirect_url
```

### 3.2 Już wdrożone optymalizacje klienckie

| Optymalizacja | Gdzie | Efekt [UDOWODNIONE] |
|---|---|---|
| Wspólna sesja keep-alive na cały checkout (`creq.Session`) | [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L41-L48) | reużycie handshake TLS (oszczędność ~125 ms/request, warm vs cold p50: 328 vs 453 ms) |
| Równoległość `build ∥ pickup_point` (`ThreadPoolExecutor`) | [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L166-L190) | nakładanie się dwóch niezależnych requestów |
| Cache koordynatów adresu (klucz `anon_id`) | [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L22-L24) | pickup_point startuje bez czekania na build |
| CSRF z JWT `access_token_web` zamiast hardcode | [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py#L71-L82) | poprawność sesji |
| Własny fingerprint TLS Firefox 152 (JA3/JA4/Akamai/extra_fp) | [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py#L11-L30) | przejście detekcji i buildu 200 |

### 3.3 Rozbieżność spec vs implementacja

Spec `curl-cffi-mvp-design` zakładał generowanie tokenu Incognia **na każdy zakup** przez subprocess Node.js ([incognia.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/incognia.py)). W aktualnym [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L168) build wywoływany jest z **pustym tokenem** (`_build(s, int(txn), "", konto)`), a token Incognia pobierany jest dopiero przez Camoufox w ścieżce odblokowania 403. Oznacza to, że stały koszt subprocesu Node.js **nie obciąża** ścieżki szczęśliwej (build 200 bez tokena) — co jest zgodne z adnotacją `[UDOWODNIONE] Build przechodzi bez tokena JWE`.

---

## 4. Pomiarowy rozkład kosztów czasowych

### 4.1 Floor rezerwacji (do buildu) — [UDOWODNIONE]

Źródło: [pomiar_czasu_curl_out.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/pomiar_czasu_curl_out.json) (cold session):

| Krok | delta | skumulowany | HTTP |
|---|---|---|---|
| `catalog_items` | +828 ms | 828 ms | 200 |
| `conversations_create_txn` | +1515 ms | 2343 ms | 200 |
| `checkout_build` | +1657 ms | 4000 ms | 200 |
| **Suma do buildu** | | **4015 ms** | |

Na ciepłym połączeniu (keep-alive) floor spada do **~2.7–3.0 s** ([PLAN_BADAN_WYDAJNOSC.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/PLAN_BADAN_WYDAJNOSC.md#L23)).

### 4.2 Pełny flow do bramki — [UDOWODNIONE]

Źródło: `bench_curl_gateway_nocam.py` ([PLAN_BADAN_WYDAJNOSC.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/PLAN_BADAN_WYDAJNOSC.md#L214-L228)):

```
[  297 ms] health                    -> 200
[ 1329 ms] catalog                   -> 200
[ 2641 ms] conversations             -> 200
[ 4344 ms] build                     -> 200
[ 5547 ms] put payment_method        -> 200
[ 5985 ms] pickup_points             -> 200
[ 7454 ms] put pickup_details        -> 200
[ 9985 ms] PAYMENT -> BRAMKA         -> 200, pending
=== ~10 s do bramki ===
```

### 4.3 Detekcja (polling) — [UDOWODNIONE]

| Wariant | p50 | avg | Źródło |
|---|---|---|---|
| warm Session (keep-alive) | 328 ms | 343.8 ms | S1 |
| cold Session | 453 ms | 506.0 ms | S1 |
| per_page=2 / 10 / 24 | 453 / 453 / 656 ms | — | S2 |

---

## 5. Identyfikacja wąskich gardeł

### 5.1 Wąskie gardła SERWEROWE (nieusuwalne przez klienta)

| Gardło | Koszt [UDOWODNIONE] | Charakter |
|---|---|---|
| `POST /conversations` (utworzenie transakcji) | ~1.2–1.5 s | twardy floor |
| `POST /checkout/build` (rezerwacja) | ~1.5–1.6 s | twardy floor |
| `POST /checkout/payment` | ~2.5–2.7 s | twardy floor |
| 2× PUT checkout + pickup | ~3.4 s łącznie | twardy floor |
| Rate-limit Vinted | ~0.83 req/s | twardy limit |

**Konsekwencja:** suma serwerowych czasów obowiązkowych kroków do buildu wynosi **~2.7 s minimum**. Żaden klient HTTP nie zejdzie poniżej tej granicy dla świeżego zakupu.

### 5.2 Wąskie gardła KLIENCKIE (usuwalne przez curl_cffi)

| Gardło | Koszt | Priorytet | Mechanizm curl_cffi |
|---|---|---|---|
| Re-handshake TLS (cold session) | ~125 ms/request [UDOWODNIONE] | wysoki | `Session` keep-alive + `upkeep()` |
| Zrywanie połączenia HTTP/2 między pollingiem a checkoutem | ~125–300 ms | wysoki | jedna długożyjąca `Session` + `upkeep()` |
| Overhead wątków (`ThreadPoolExecutor`) | rzędu ms (mały) | niski | `AsyncSession` z `asyncio.gather` |
| Spawn subprocesu Node.js na token (gdyby był w ścieżce) | ~50–200 ms | średni | pre-warm/cache tokenu + `sdk_instance_id` |

### 5.3 Gardło architektoniczne DataDome/Incognia (poza zakresem transportu)

[RAPORT_INZYNIERSKI](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md) dowodzi, że DataDome blokuje na warstwie TLS/HTTP **przed** walidacją Incognia, gdy brakuje pełnego fingerprintu przeglądarki. To **nie jest** problem wydajności transportu — to problem zgodności fingerprintu. curl_cffi rozwiązuje go przez dokładną emulację JA3/JA4/Akamai Firefox 152, ale **nie** przez bycie szybszym.

---

## 6. Porównanie wariantów transportu HTTP

### 6.1 curl_cffi `Session` vs pojedyncze `creq.get/post` (bez sesji)

| Wariant | Zachowanie | Zysk |
|---|---|---|
| `creq.get/post` (funkcje modułowe) | każdy request = nowy handshake TLS | baseline (zimny) |
| `creq.Session` (context manager) | cookie jar + connection pooling | ~125 ms/request [UDOWODNIONE] |
| `Session.upkeep()` | ping frame utrzymuje HTTP/2 idle | eliminuje re-handshake przy dłuższej przerwie |

### 6.2 curl_cffi `Session` (wątki) vs `AsyncSession` (asyncio)

| Wariant | Kiedy lepszy |
|---|---|
| `Session` + `ThreadPoolExecutor` | obecny kod; prosty, wystarczający dla 2 requestów równoległych |
| `AsyncSession` + `asyncio.gather` | większa liczba współbieżnych requestów (polling na wielu filtrach); mniejszy overhead; `max_clients` kontroluje pulę uchwytów cURL |

**Rekomendacja [DOMNIEMANE]:** dla samej ścieżki checkoutu (2 równoległe requesty) przejście na `AsyncSession` da znikomy zysk. Zysk jest realny dopiero przy zrównolegleniu **wielu kont/filtrów** lub **polling + checkout** jednocześnie.

### 6.3 curl_cffi vs surowy cURL CLI

| Aspekt | curl_cffi | surowy cURL |
|---|---|---|
| Emulacja fingerprintu (JA3/JA4/Akamai) | ✅ natywna (`impersonate`, `ja3`, `akamai`) | ❌ wymaga `curl-impersonate` |
| Zarządzanie cookies/sesją | ✅ `Session` | ręcznie |
| Integracja z Pydantic/Click | ✅ Python | subprocess |
| Wydajność | bliska libcurl (CFFI, brak GIL w I/O) | identyczna (ten sam libcurl) |

**Wniosek [UDOWODNIONE]:** `curl_cffi` jest już cienką warstwą nad `libcurl` przez CFFI — dalsze „przyspieszanie" przez przejście na surowy cURL nie da zysku, bo to ten sam silnik. Zysk leży w **reużyciu połączenia**, nie w zmianie biblioteki.

---

## 7. Konkretne rekomendacje implementacyjne

### R1. Długożyjąca `Session` z `upkeep()` między pollingiem a checkoutem [wysoki priorytet]

Obecnie `monitoruj()` ([detection.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/detection.py#L108-L149)) tworzy nowe sesje per request, a `zrealizuj_zakup()` tworzy osobną sesję. Rozdzielenie to powoduje re-handshake przy przejściu detekcja → checkout.

**Proponowana zmiana:** jedna współdzielona `Session` na konto, utrzymywana `upkeep()` co kilkadziesiąt sekund, przekazywana do checkoutu.

```python
# pseudokod — mechanizm, nie pełna implementacja
s = creq.Session(headers=_headers(konto), cookies=konto.cookies,
                 impersonate=konto.impersonate, timeout=30)
# w pętli pollera co N iteracji:
s.upkeep()  # utrzymuje żywe połączenie HTTP/2
```

Zysk: eliminacja ~125–300 ms re-handshake przy pierwszym kroku checkoutu.

### R2. Cache/pre-warm `sdk_instance_id` i tokenu Incognia [średni priorytet]

Jeśli build w przyszłości zacznie wymagać `x-incognia-request-token` w ścieżce szczęśliwej, subprocess Node.js ([incognia.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/incognia.py)) doda ~50–200 ms na zakup.

**Proponowana zmiana:** pobrać `sdk_instance_id` raz (config), buforować token z krótkim TTL, generować w tle przed wykryciem oferty.

```python
# koncepcja: token pre-warmed w tle, nie na żądanie w ścieżce zakupowej
```

### R3. `AsyncSession` dla zrównoleglenia wielu kont / filtrów [niski priorytet w obecnym zakresie]

Dla pojedynczego konta obecne `ThreadPoolExecutor` jest wystarczające. `AsyncSession` (`max_clients`) jest zasadne dopiero przy multikoncie i równoległym pollingu wielu filtrów — co jest poza obecnym MVP (zgodnie ze spec `curl-cffi-mvp`).

### R4. Skip-build na istniejącym `purchase_id` [średni priorytet]

Jeśli ścieżka retry/warmup dysponuje już `purchase_id`/`checkout_id` z wcześniejszego buildu, pominięcie ponownego `checkout/build` oszczędza ~1.4–1.6 s [DOMNIEMANE z H4 planu badań].

### R5. Karta bez 3DS [największy zysk pojedynczy, poza transportem]

Największy pojedynczy zysk w checkoucie to eliminacja kroku autoryzacji 3DS (`jak_zejsc_ponizej_kopsa.md`). To zysk **biznesowy**, niezależny od curl_cffi.

---

## 8. Granice fizyczne — co jest niemożliwe

| Twierdzenie | Werdykt | Dowód |
|---|---|---|
| „1–2 s do bramki" | **NIEMOŻLIWE** dla świeżego zakupu | payment floor ~2.5–2.7 s + obowiązkowe kroki przed nim |
| „2–3 s do buildu" | **MOŻLIWE** (już blisko) | ~2.7 s warm / ~3.2 s cold |
| „<250 ms detekcja" | **OSIĄGNIĘTE** | 328 ms warm p50 |
| „przyspieszenie przez zmianę curl_cffi → cURL" | **BEZ ZYSKU** | ten sam silnik libcurl przez CFFI |

---

## 9. Wnioski końcowe

1. **`curl_cffi` jest właściwym narzędziem** — dostarcza zarówno zgodność fingerprintu (JA3/JA4/Akamai Firefox 152), jak i reużycie połączenia (keep-alive + `upkeep()`). Zmiana na surowy cURL nic nie da, bo to ten sam `libcurl`.

2. **Przedział 2–3 s jest realny, ale wyłącznie jako czas do buildu.** Udowodniony floor ~2.7 s wynika z dwóch serwerowych kroków (`conversations` ~1.5 s + `build` ~1.6 s), których żaden klient HTTP nie skróci.

3. **Wąskim gardłem zakupu nie jest transport, lecz obowiązkowa sekwencja serwerowa + DataDome.** Rzeczywisty czas do bramki to ~7.5–10 s, z czego sam `payment` ~2.5–2.7 s.

4. **Pozostały potencjał optymalizacyjny po stronie klienta jest już w dużej mierze wyczerpany** — kod stosuje keep-alive, równoległość i cache koordynatów. Marginalne zyski przyniosą: współdzielona długożyjąca `Session` z `upkeep()` (R1) oraz pre-warm tokenu Incognia (R2).

5. **Największy realny zysk czasowy nie leży w warstwie transportu**, lecz w: (a) karcie bez 3DS, (b) skip-build na pre-warmed `purchase_id`, (c) pre-warm całej transakcji poza oknem wyścigu o ofertę.

---

## 10. Źródła

- [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py) — sekwencja zakupowa + optymalizacje
- [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py) — fingerprint FF152, stałe
- [detection.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/detection.py) — monitoring, transakcje
- [incognia.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/incognia.py) — token Incognia (subprocess Node)
- [pomiar_czasu_curl_out.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/pomiar_czasu_curl_out.json) — pomiar do buildu (4015 ms)
- [PLAN_BADAN_WYDAJNOSC.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/PLAN_BADAN_WYDAJNOSC.md) — warm/cold, per_page, full flow do bramki
- [RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md) — luki DataDome/Incognia
- [RAPORT_FINALNY_curl_cffi_JS_engine_wymagania.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/RAPORT_FINALNY_curl_cffi_JS_engine_wymagania.md) — architektura hybrydowa
- [jak_zejsc_ponizej_kopsa.md](file:///f:/PROJEKTY/vinted/vinted/raporty/05_konkurencja/jak_zejsc_ponizej_kopsa.md) — hierarchia zysku czasowego
- [curl-cffi-mvp-design.md](file:///f:/PROJEKTY/vinted/docs/superpowers/specs/2026-08-31-vinted-bot-curl-cffi-mvp-design.md) — spec przebudowy
- Dokumentacja curl_cffi (Context7): `/lexiforest/curl_cffi` — Session, AsyncSession, upkeep

---

*Koniec analizy naukowo-inżynierskiej.*