# DataDome na checkout/build — analiza natywnego SDK + konsekwencje

Data: 2026-09-01
Źródło: dekompilacja APK (jadx_out) + benchmark przeglądarkowy [CHECKOUT_BENCHMARK.md](CHECKOUT_BENCHMARK.md).

---

## 1. STOS INTERCEPTORÓW APK [UDOWODNIONE]

Kolejność w stacku OkHttp (z dekompilacji):
```
DomainFailover → DeviceFingerprint → ApiHeaders → Language → VintedContext
→ Country → Logging → SecurityProtection → 2FA → DataDome → EndpointTracking → ScreenPerformance
```

Miejsce DataDome: **po 2FA, przed EndpointTracking** — każdy request wychodzący z APK przechodzi przez SDK DataDome.

---

## 2. NATYWNY SDK — NIE JS [UDOWODNIONE]

- `DataDomeSdkGatewayImpl` implementuje bramkę do natywnego SDK:
  `co.datadome.sdk.DataDomeInterceptor` (patrz `DataDomeModule.java` — bind interceptor).
- To jest **natywny SDK DataDome** (AAR z `com/datadome`), nie czysty JS — ale generuje te same cookie/sygnatury co web (`datadome` cookie, nagłówki `X-DD-B`, `X-DD-C`).
- Dla nas oznacza to: **web może być "lżejszy"** (SDK natywny może wymagać więcej sygnatur urządzenia niż web), ale blokada 403 na `checkout/build` w przeglądarce (benchmark) dowodzi, że **sam web stack też jest sprawdzany** pod kątem tego endpointu.

---

## 3. ENDPOINT TRACKING — JAK SDK OZNACZA BLOKADY [UDOWODNIONE]

`EndpointTrackingInterceptor`:
- przy odpowiedzi **403** odczytuje nagłówek **`X-DD-B`** (body captcha/odpowiedzi DataDome)
- zapisuje endpoint, który został zablokowany (mapa endpoint → status)
- nie blokuje dalszych requestów — tylko loguje

**Wniosek:** APK sam śledzi, które endpointy DataDome blokuje — to potwierdza, że `checkout/build` to cel o wyższym rygorze niż katalog.

---

## 4. KONSEKWENCJE Z BENCHMARKU [UDOWODNIONE]

Z [CHECKOUT_BENCHMARK.md](CHECKOUT_BENCHMARK.md):
- `catalog` (GET) → 200
- `conversations` (POST) → 200
- `checkout/build` (POST, transakcyjny) → **403** mimo ważnej sesji + świeżego cookie DataDome z loadu strony itemu

### Hierarchia progów DataDome (zaobserwowana):
```
katalog / users/current   → 200          (niski próg)
conversations             → 200          (średni próg)
checkout/build            → 403          (WYSOKI próg — transakcyjny)
```

### Co odróżnia build od conversations:
1. `checkout/build` to endpoint **płatniczy** (Incognia token wymagany w APK: `X-Incognia-Request-Token`).
2. W teście benchmarku **nie wysłano** tokenu Incognia → możliwe, że brak tokenu to dodatkowa flaga ryzyka dla DataDome.
3. DataDome może wymagać dodatkowych nagłówków urządzenia, które APK wysyła przez `DeviceFingerprint` i `ApiHeaders`.

---

## 5. HIPOTEZY DO PRZETESTOWANIA

### H1: Brak tokenu Incognia = flaga ryzyka — ❌ **ODRZUCONA (2026-09-01)**
- Test: wysłano realny, ważny token Incognia (len=3047, przechwycony z kliku "Kup teraz") w nagłówku `X-Incognia-Request-Token` do `checkout/build`.
- Wynik: **403** (188 ms) — identyczny jak bez tokenu (125 ms). Body: **captcha DataDome** (`geo.captcha-delivery.com/interstitial`), nie odrzucenie tokenu.
- Wniosek: token Incognia **nie wpływa** na decyzję DataDome przy `build`. Blokada to captcha na poziomie DataDome, nie brak sygnatury Incognia.
- Dowód: `_checkout_h1_test.json` + `_checkout_h1_test.log`.
- **Wniosek dodatkowy:** strona przechodzi do `/checkout` mimo 403 na build (obsługuje captcha jako normalny flow). To sugeruje, że DataDome na build to **captcha do rozwiązania**, nie twardy ban.

### H2: Wymagany prefetch strony checkoutu — ❌ **ODRZUCONA (2026-09-01)**
- Test: nawigacja na stronę itemu → klik "Kup teraz" → strona przechodzi na `/checkout` → czekamy na `networkidle` + 5s (pełny challenge DataDome) → dopiero wtedy wysyłamy ręczny `build`.
- Wynik: **403** (141 ms). Body: **captcha DataDome** (`geo.captcha-delivery.com/interstitial`).
- Wniosek: nawet po pełnym załadowaniu strony checkoutu DataDome zwraca captcha na `build`. **Prefetch strony nie pomaga.**
- Dowód: `_checkout_h2_test.json`.
- **Kluczowe odkrycie:** realny flow strony (klik "Kup teraz") też dostaje 403 na build — strona po prostu przechodzi na `/checkout` i tam wyświetla captcha użytkownikowi. **DataDome na build to captcha do rozwiązania przez użytkownika, nie coś co przechodzi automatycznie.**

### H3: Brak nagłówków APK (DeviceFingerprint/ApiHeaders)
- Test: `build` z nagłówkami odtworzonymi z APK (x-device-fingerprint, x-visitor-id itd.).
- Kryterium: 200 zamiast 403.
- **Uwaga:** po odrzuceniu H1 i H2, najbardziej prawdopodobne jest, że DataDome na build **zawsze** wymaga rozwiązania captcha (interakcji użytkownika). H3 ma niską szansę.

### H4: card_registrations jako ścieżka alternatywna — ❌ **ODRZUCONA dla web (2026-09-01)**
- `card_registrations` **NIE wymaga** Incognia token [UDOWDONIONE — patrz CHECKOUT_ROWNOWAZNOLEGLOSC.md].
- Test: 4 kandydaty URL w przeglądarce Camoufox (ważna sesja):
  - `POST /api/v2/payments/public/api/card_registrations` → 404
  - `POST /payments/public/api/card_registrations` → 404
  - `POST /api/v2/payments/card_registrations` → 404
  - `POST /api/v2/card_registrations` → 404
- Wniosek: **endpoint `card_registrations` istnieje TYLKO w APK** (prawdopodobnie za innym gatewayem/hostem). W web nie istnieje → H4 (pre-tokenizacja karty przez web) **ODRZUCONA**.
- Dowód: `_card_registrations_probe.json`.
- Konsekwencja: tokenizacja karty musi iść przez **webowy flow** (nieznany) albo przez APK gateway (wymaga odtworzenia baseUrl `API_GATEWAY_BASE_URL + PAYMENTS_PUBLIC_API`).

---

## 6. KONFRONTACJA Z DOKUMENTACJĄ

- Aktualizuje [SYNTEZA_GŁÓWNA.md](../../testy_camoufox/docs/SYNTEZA_GŁÓWNA.md) PRIORYTET 1: przyczyną 403 jest **nie samo niespójność cookie**, ale **wysoki próg transakcyjny build** (mimo spójnego stacku).
- Potwierdza [CHECKOUT_KONFLIKTY.md](../../testy_camoufox/docs/synthesis/CHECKOUT_KONFLIKTY.md): DataDome na checkout — konflikt otwarty, wymaga rozstrzygnięcia przez H1-H4.
- Uzupełnia [CHECKOUT_SEKWENCJA_APK.md](CHECKOUT_SEKWENCJA_APK.md): rola interceptorów DataDome/EndpointTracking w sekwencji.

---

## 7. ROZSTRZYGNIĘCIE [UDOWODNIONE 2026-09-01] — captcha slider odblokowuje build

**Kluczowe odkrycie z `captured_requests.json` (linie 417-462):** `checkout/build` **JUŻ PRZECHODZIŁ 200** wcześniej, a nasze testy H1/H2 dały 403 z prostego powodu — **używały profilu `profil_firefox`, który NIE był odblokowany sliderem**.

### Fakty z captured_requests.json:
- L422: `build=200 Z AUTO-SLIDEREM: solver (frame.locator drag_to na .slider do .sliderContainer) rozwiazuje challenge DataDome`
- L430: `PRZELOM: build=200 BEZ tokena JWE, czysty curl. Camoufox NIE potrzebny do zakupu - tylko RAZ do odblokowania profilu (slider). Potem datadome czyste i curl wystarcza. Caly checkout 5.6s`
- L446: `OPTYMALIZACJA 3.36s: transaction(625ms) + build ROWNOLEGLE z pickup_point(1313ms) + 1x PUT(1422ms)`

### Mechanizm (działający kod):
- `bot/src/vintedbot/checkout.py::zrealizuj_zakup` — czysty curl_cffi, `impersonate=firefox152`, sesja keep-alive.
- Gdy build=403 → fallback `przechwyc_token_incognia` (Camoufox headful) → `rozwiaz_slider` (slider_solver.py) → ponów build.
- `bot/src/vintedbot/slider_solver.py::rozwiaz_slider` — wykrywa iframe `captcha-delivery.com`, przeciąga `.slider` do końca `.sliderContainer` (`drag_to`, target x=279).

### Dlaczego nasze testy H1/H2/H4 dały 403/404:
| Test | Profil | headless | humanize | Slider | Wynik |
|---|---|---|---|---|---|
| H1 | `profil_firefox` | True | False | NIE | 403 |
| H2 | `profil_firefox` | True | False | NIE | 403 |
| H4 | `profil_firefox` | True | False | NIE | 404 (web) |
| **działający bot** | `profil_firefox_135` | **False** | **True** | **TAK** | **200** |

### Wniosek:
- **403 na build = profil wymaga rozwiązania captcha slider (raz).** Po rozwiązaniu cookie DataDome jest "czyste" i build przechodzi nawet w czystym curl_cffi bez tokenu Incognia.
- Token Incognia **nie jest wymagany** przy build (potwierdza to też odrzucenie H1 — token nie pomaga ani nie szkodzi).
- Bloker **NIE jest nierozwiązany** — istnieje działający solver slidera w `slider_solver.py`.

### [NAKAZ] Co zostało do zrobienia:
1. Zweryfikować czy `profil_firefox_135` nadal przechodzi build=200 (odświeżyć cookies i testować).
2. Jeśli tak — problem "DataDome 403" jest **rozwiązany** (slider solver działa), a projekt może iść do pomiaru payment/3DS.
3. Zaktualizować SYNTEZA_GŁÓWNA.md: bloker DataDome = ROZWIĄZANY przez slider solver.
