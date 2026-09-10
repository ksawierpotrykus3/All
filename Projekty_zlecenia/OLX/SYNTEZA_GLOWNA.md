# GŁÓWNA SYNTEZA: Status projektu OLX Bot

> **GŁÓWNE ZRÓDŁO PRAWDY**: Cała spójna, zweryfikowana dokumentacja projektu znajduje się w:
> 👉 **[gemini/KOMPENDIUM_OLX.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/gemini/KOMPENDIUM_OLX.md)**

## STAN PROJEKTU - 2026-09-02 (Aktualizacja Gemini)

### CO WIEMY (udowodnione empirycznie) [UDOWODNIONE]

1. **Detektor ofert działa** — sekwencyjne ID + sliding window + hole-sweeper (`bot/detector.py`). Przewaga 9-14 min nad wyszukiwarką. [UDOWODNIONE]
2. **Obejście CloudFront 403** — `curl_cffi` z `impersonate="chrome124"` omija blokady TLS. [UDOWODNIONE]
3. **Trwała sesja i auto-refresh** — wdrożono architekturę trwałego profilu z Vinted (`profiles/olx_profile`). Odświeżanie tokena w tle działa w 100% bez interakcji człowieka (`gemini/skrypty/test_session_refresh.py`). [UDOWODNIONE]
4. **Rozwiązanie wyzwań Slider CAPTCHA (DataDome / AWS WAF)** — jednorazowe zalogowanie w oknie `ZALOGUJ_SIE_OLX.bat` zapisało tokeny `aws-waf-token` i `datadome`. W trybie headless bot nie napotyka już slidera. [UDOWODNIONE]
5. **Autoryzacja API** — Bearer token działa na endpointach profilu (`GET /api/v1/users/me/` → 200) oraz mikroserwisach Pay & Ship. [UDOWODNIONE]
6. **Prawdziwy silnik zakupu i rezerwacji** — backend to mikroserwis **`https://pl.ps.prd.eu.olx.org`**:
   - `GET /checkout/v1/checkout/{adId}` → szczegóły i kalkulacja kosztów (200 OK).
   - `POST /order/v1/purchase-order` z `{"adId": adId}` → tworzy Purchase Order w stanie `Draft` w **~150 ms** (`201 Created`). [UDOWODNIONE]
7. **Metody dostawy i płatności** — formularz obsługuje InPost Paczkomat 24/7 (6,49 zł) oraz płatność BLIK / PayU. [UDOWODNIONE zrzutem ekranu `gemini/dane/checkout_step2.png`].
8. **Wybór punktu odbioru** — endpoint `GET /fulfillment/v1/fulfillment/{id}/service-points/search?latitude={lat}&longitude={lon}&limit=50` zwraca listę punktów InPost na mapie. Wybór punktu wymaga interakcji z mapą (URL checkoutu przechodzi na `/map`). [UDOWODNIONE — `gemini/dane/lock_hypothesis_result.json`].
9. **Maszyna stanów zamówienia** — `GET /order/v1/purchase-order/{id}/next` zwraca kroki `fulfillment` (state=required), `buyer-billing`, `payment-method-selection`, `donation-selection`, `safedeal-info`. [UDOWODNIONE].
10. **Pełny łańcuch czystego API do podsumowania** — przechwycone POST-y `202 Accepted`: `pick-up-point/submit`, `personal-details/submit`, `payment-method-selection/submit`, `donation-selection/submit`, `billing-needed/submit`. Selektor punktu Paczkomat: `button[data-testid='map-list-item']`. Dojście do ekranu `#summary` (przycisk „Zamawiam i płacę"). [UDOWODNIONE — `gemini/dane/paczkomat_and_lock_proof.json`].
11. **Moment blokady 15 min** — `buyer-confirmation` (przycisk „Zamawiam i płacę") ma w maszynie stanów `state: required` i NIE został wykonany. Przechwycono tylko `GET .../buyer-confirmation` (odczyt ekranu), a NIE `POST .../buyer-confirmation/submit`. Blokada w tym punkcie to **HIPOTEZA, nie dowód**. [HIPOTEZA]

### CO ZOSTAŁO OBALONE (błędy wcześniejszych analiz) [OBALONE]

1. **[OBALONE]** Koncepcja 08 (`POST /delivery/checkout/{id}/`, `/api/v1/delivery/orders/`) — wszystkie te endpointy zwracają 404.
2. **[OBALONE]** Teoria, że refresh token leży w `localStorage` lub `sessionStorage` — nie ma go tam. Sesja opiera się na ciasteczkach `login.olx.pl`.
3. **[OBALONE]** Założenie, że `POST /order/v1/purchase-order` natychmiast blokuje ofertę — **błąd/nadinterpretacja**. Zamówienie tworzone jest ze statusem `Draft`, a pole `delivery.rock.active` w ofercie nadal wynosi `True`. Blokada oferty następuje na dalszym etapie.

### CO POZOSTAJE DO DOKOŃCZENIA [HIPOTEZA]

1. Dokładny moment zablokowania oferty — **NADAL NIEPOTWIERDZONE**. Dwa testy (`test_lock_hypothesis.py`, `test_lock_hypothesis2.py`) utknęły na wyborze Paczkomatu (selektor punktu na mapie nie został trafiony), więc nie dotarliśmy do podsumowania/płatności. `delivery.rock.active` pozostało `true` w obu testach, ale **to nie dowodzi braku blokady** — test nie przeszedł pełnego flowu.
2. Prawidłowy selektor punktu odbioru na mapie (`/map`) — wymaga zbadania DOM mapy InPost.
3. Pełny payload wywołania `fulfillment` i `buyer-billing`.
