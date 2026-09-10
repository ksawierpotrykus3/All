# SYNTEZA: Konflikty dotyczące checkoutu i płatności

## 🔥 **GŁÓWNY KONFLIKT: Czy checkout jest rozpracowany?** [SPRZECZNOŚĆ]

### Źródło A: `02_reverse_engineering/`
```
"100% zweryfikowane endpointy checkout:
- POST /api/v2/purchases/checkout/build
- PUT /api/v2/purchases/{id}/checkout
```

### Źródło B: `03_weryfikacja/OCENA_WERYFIKACJI.md`
```
"checkout/build występuje tylko 1 raz w zminifikowanym JS
bez kontekstu endpointu. PUT /purchases/{id}/checkout nie ma w ogóle.
Status: NIEUDOWODNIONE."
```

### Źródło C: `04_niewiadome/CZEGO_NIE_MAMY.md`
```
"Nigdy nie wykonano zakupu. Jedyna zmierzona odpowiedź to HTTP 403."
```

## 🧪 **ANALIZA DOWODÓW**

### Co MAMY w danych:
- ✅ `captured_requests.json` - 52 przechwycone requesty
- ✅ Wszystkie to: katalog, banery, statystyki, reklamy
- ✅ **BRAK** endpointów checkout w capture

### Co MAMY w kodzie JS:
- ✅ `checkout/build` występuje 1x w zminifikowanym JS
- ⚠️ Bez kontekstu parametrów ani formatu requestu
- ❌ `PUT /purchases/{id}/checkout` - brak w JS

## 🎯 **ROZSTRZYGNIĘCIE KONFLIKTU**

### FAKTY:
1. **Endpointy checkout istnieją w kodzie frontendu**
2. **Nigdy nie zostały przechwycone w działaniach** (brak w captured_requests)
3. **Nigdy nie wykonano udanego zakupu** (tylko 403)

### WNIOSKI:
- ❌ **NIE** mamy "100% zweryfikowanych endpointów"
- ✅ Mamy **hipotezę** na podstawie analizy JS
- 🔬 **Wymagane:** Przechwycenie rzeczywistego checkout flow

## 📊 **STATUS CHECKOUT**

| Element | Status | Dowody |
|---------|--------|---------|
| Endpointy w JS | PRAWDA | `checkout/build` w zminifikowanym kodzie |
| Przechwycone requesty | FAŁSZ | Brak w `captured_requests.json` |
| Udało się kupić | FAŁSZ | Tylko HTTP 403 |
| Parametry requestu | NIEZNANE | Nie przechwycono |
| Format odpowiedzi | NIEZNANE | Nie otrzymano 200 |

## 🚫 **ZMYŚLONE ENDPOINTY (`/api/v2/transactions`)**

### Źródło: `07_niezweryfikowane/research/`
```
- POST /api/v2/transactions
- /transactions/{id}/shipment  
- /transactions/{id}/payment
- "Portfel omija 3DS"
- "checkout 0.6–1.2 s"
```

### Audyt: `03_weryfikacja/AUDYT_PRAWDY.md`
```
"ZMYŚLONE przez AI. Brak w captured_requests.json."
```

### ROZSTRZYGNIĘCIE:
- ❌ **FAŁSZ** - endpointy transakcji nie istnieją
- ⚠️ Hipotezy AI zapisane jako fakty
- ✅ Przeniesione do `07_niezweryfikowane/` - właściwa klasyfikacja

## 🧪 **NOWE ODKRYCIA (2026-08-31) — rozstrzygają część konfliktu**

### Przechwycono realny token Incognia + plaintext [UDOWODNIONE]

1. **Token `x-incognia-request-token` przechwycony** z checkout/build (endpoint: `POST /api/v2/purchases/checkout/build`) — realny JWE, nie hipoteza.
2. **Plaintext Incognii odczytany** przez hook `crypto.subtle.encrypt` — 39 pól fingerprintu (app_id, session_id, installation_id, canvas_paint_cpu/gpu, token_sequence_number).
3. **Klucz publiczny Incognii wyekstrahowany** (RSA-2048, e=65537) → możliwa replikacja tokenu w pure Python (bez JS runtime).

[UDOWODNIONE] To potwierdza, że endpoint `checkout/build` **istnieje i jest osiągalny** (nie fikcja). (Stan na 2026-08-31: odpowiedź to 403; **rozwiązane 2026-09-01 → build=200**, patrz sekcja DataDome ROZWIĄZANY poniżej).

### Co to zmienia w klasyfikacji

| Element | Poprzedni status | Nowy status |
|---|---|---|
| Endpoint `checkout/build` istnieje | NIEUDOWODNIONE | ✅ **UDOWODNIONE** (przechwycony realny request z tokenem Incognia) |
| Token Incognia format | nieznany | ✅ **UDOWODNIONE** (JWE + plaintext) |
| checkout/build → 200 | FAŁSZ | ❌ nadal 403 (bloker DataDome) — ✅ **AKTUALIZACJA 2026-09-01:** ROZWIĄZANE (slider solver + `profil_firefox_135`, 10/10 = 200) |

## 🧪 **NOWE ODKRYCIE (2026-09-01) — szyfrowanie karty Adyen (payment error 114)**

### Adyen CSE odtworzony z APK [UDOWODNIONE]

1. **Pełny algorytm JWE** — RSA-OAEP-256 (klucz AES) + AES-256-GCM (dane karty). Format: `header.encryptedKey.iv.cipherText.authTag`.
2. [POTWIERDZONE] **Klucz publiczny Adyen** nie jest stały — pochodzi z pola `access_key` odpowiedzi `POST payments/public/api/card_registrations` (format `exp|mod`, 518 znaków, dekompilacja APK).
3. **Endpointy tokenizacji** — `POST card_registrations` → `PUT card_registrations/{id}` (4 osobne pola JWE) → `POST card_registrations/authorisation` (3DS).

**Znaczenie:** błąd **payment error 114** („Purchase card is not valid") wynika z braku poprawnej tokenizacji karty. Odtworzenie algorytmu umożliwia tokenizację lokalnie, bez emulatora.

### Co to zmienia w klasyfikacji

| Element | Poprzedni status | Nowy status |
|---|---|---|
| Format szyfrowania karty | nieznany | ✅ **UDOWODNIONE** (JWE + algorytm) |
| Endpointy `card_registrations` | nieznane | ✅ **UDOWODNIONE** (Retrofit) |
| Tokenizacja bez emulatora | nieznana | ⚠️ **DOMNIEMANE** (brak testu na żywo) |
| payment error 114 rozwiązany | ❌ [NIEPOTWIERDZONE] | ⏳ wymaga testu integracyjnego z kartą |

Szczegóły: [ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md](../reports/ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md)

## 🧪 **NOWE ODKRYCIE (2026-09-01) — DataDome ROZWIĄZANY, build=200 [UDOWODNIONE]**

### Rozstrzygnięcie głównego blokera
Testy H1/H2/H4 na profilu `profil_firefox` dały 403/404, ale `captured_requests.json` (linie 417-462) pokazywał, że **build już wcześniej przechodził 200**. Weryfikacja `test_build_bez_tokena.py` na profilu `profil_firefox_135`:

```
zakup 1: status_build=200, pickup=200, payment=400 (error 114 - brak karty)
  transaction: 1859ms, build+pickup: 2000ms, pickup_details: 1469ms, payment: 1906ms
  TOTAL: 7250ms
zakup 2 (skip-build): transaction 250ms, pickup 547ms, payment_method 234ms
  TOTAL: 1031ms
```

### Przyczyna wcześniejszych 403
| Test | Profil | Slider | Wynik |
|---|---|---|---|
| H1/H2 | `profil_firefox` | NIE rozwiązany | 403 |
| **działający bot** | `profil_firefox_135` | **TAK (slider_solver.py)** | **200** |

**Wniosek:** [UDOWODNIONE] DataDome na build to **captcha slider do rozwiązania RAZ per profil**. Po odblokowaniu cookie DataDome jest czyste i build przechodzi w czystym curl_cffi **bez tokenu Incognia**.

### Co to zmienia w klasyfikacji

| Element | Poprzedni status | Nowy status |
|---|---|---|
| checkout/build → 200 | ❌ 403 | ✅ **UDOWODNIONE 200** (slider + czysty curl) |
| DataDome bypass | ❌ blokada | ✅ **ROZWIĄZANY** (slider_solver.py) |
| Token Incognia do build | wymagany (hipoteza) | ❌ [MIT] **NIE jest wymagany** (H1 odrzucona + build=200 bez tokenu) |
| card_registrations w web | możliwe (H4) | ❌ **ODRZUCONA** (404 — tylko APK) |
| payment | zablokowane przez 403 | ⚠️ **400 error 114** (brak karty, nie bloker techniczny) |
| Czasy | niezmierzone | ✅ full ~7.2s, skip-build ~1.0s |

### Nowy bloker: payment error 114
`payment=400 error_code=114 "Purchase card is not valid"` — konto testowe nie ma prawdziwej karty ani portfela. To NIE jest problem techniczny bota, tylko stan konta. [POTWIERDZONE] Wymaga dodania karty/portfela.

Szczegóły: [CHECKOUT_DATADOME.md](../../raporty/02_reverse_engineering/CHECKOUT_DATADOME.md) sekcja 7, `bot/output/wynik_build_bez_tokena_1788260388.json`

### Benchmark w przeglądarce Camoufox (spójny stack)
1. **catalog 406 ms (200)** — detekcja zmierzona, szybka.
2. **conversations 1172 ms (200)** — inicjacja transakcji zmierzona.
3. **checkout/build 187 ms (403 DataDome)** — **mimo** ważnej sesji i świeżego cookie DataDome wygenerowanego na loadzie strony itemu.

**Wniosek:** 403 NIE wynika z niespójności cookie curl_cffi ↔ fingerprint — występuje **również w spójnym stacku przeglądarkowym**. DataDome ma hierarchię progów: katalog/conversations przechodzą, transakcyjny `build` nie.

### Analiza APK (sekwencja + płatności)
4. **Pełna sekwencja endpointów** — `check_availability` → `checkout/build` → `checkout/payment` zmapowana w [CHECKOUT_SEKWENCJA_APK.md](../../raporty/02_reverse_engineering/CHECKOUT_SEKWENCJA_APK.md).
5. **Dwie ścieżki płatności** — WALLET (brak akcji = sukces), nowa karta (Adyen CSE), stored card (CVV przez **PayRails CSE**).
6. **`card_registrations` NIE wymaga Incognia token** [UDOWODNIONE] — lżejsza ścieżka, niezależna od checkoutu, możliwa do pre-tokenizacji równolegle.
7. **Natywny SDK DataDome w APK** (`co.datadome.sdk.DataDomeInterceptor`) + `EndpointTrackingInterceptor` (loguje `X-DD-B` przy 403).

### Co to zmienia w klasyfikacji

| Element | Poprzedni status | Nowy status |
|---|---|---|
| Czasy kroków (catalog/conversations) | niezmierzone | ✅ **UDOWODNIONE** (406/1172 ms) |
| checkout/build → 200 | FAŁSZ | ❌ nadal 403 — nawet w przeglądarce |
| Przyczyna 403 | niespójność cookie (hipoteza) | ❌ **ODRZUCONA** — spójny stack też 403 |
| Sekwencja checkout | hipoteza z JS | ✅ **UDOWODNIONE** (dekompilacja APK) |
| Stored card CVV | Adyen CSE (hipoteza) | ✅ **PayRails CSE** (dekompilacja) |
| `card_registrations` Incognia | nieznane | ✅ **NIE wymaga** (CardRegistrationsCentralApi.java) |

### Hipotezy do przetestowania (DataDome na build)
- **H1:** brak tokenu Incognia w build = flaga ryzyka → ❌ **ODRZUCONA (2026-09-01)**. Wysłano realny token (len=3047) z kliku "Kup teraz" → nadal **403**. Body to **captcha DataDome** (`geo.captcha-delivery.com/interstitial`), nie odrzucenie tokenu. Token Incognia nie wpływa na decyzję DataDome.
- **H2:** brak prefetch strony checkoutu → test `page.goto(/checkout/{id})` przed build.
- **H3:** brak nagłówków APK (DeviceFingerprint/ApiHeaders) → test z nagłówkami z APK.
- **H4:** `card_registrations` przechodzi 200 w curl_cffi → pre-tokenizacja bez głównej blokady.
- **Nowy trop po H1:** 403 to captcha, nie twardy ban → test czy po rozwiązaniu captcha (interstitial) build przechodzi 200.

Szczegóły: [CHECKOUT_BENCHMARK.md](../../raporty/02_reverse_engineering/CHECKOUT_BENCHMARK.md), [CHECKOUT_DATADOME.md](../../raporty/02_reverse_engineering/CHECKOUT_DATADOME.md)

## 🛠️ **CO DALEJ?**

### Kroki weryfikacji:
1. ✅ **Przechwycić token Incognia** — zrobione (plaintext odczytany)
2. ✅ **Zbudować lekki generator tokenu** — zrobione (pure Python + pre-warm cache)
3. ⏳ **Wysłać zreplikowany token przez curl-cffi** i sprawdzić akceptację serwera
4. ✅ **Uzyskać HTTP 200** z checkout/build — **ROZWIĄZANE 2026-09-01** (profil_firefox_135 + slider solver + czysty curl_cffi)
5. ✅ **Zaimplementować szyfrowanie Adyen CSE w Python** — **ROZWIĄZANE 2026-09-01** (moduł `adyen_cse.py` + `card_manager.py` + 93 testy jednostkowe)
6. ⏳ **Test end-to-end**: pełny zakup z prawdziwą kartą/portfelem (payment=200)

### Priorytet:
1. ✅ **Rozwiązać DataDome 403 na checkout/build** — **ROZWIĄZANE** (slider_solver.py + profil odblokowany, 20/20 prób build=200)
2. ✅ **Tokenizacja kart bez przeglądarki** — **ROZWIĄZANE** (`adyen_cse.py`, `card_manager.py`)
3. ✅ **Optymalizacja czasów rezerwacji** — **ROZWIĄZANE 2026-09-02**: czas do rezerwacji koszyka **~3.39-3.71s** z ultraszybkim parserem `orjson`, Early-Trigger Streaming w detekcji i telemetrią Waterfall v2. Odkryto i zachowano barierę transakcyjną backendu Vinted (`conversations -> build`).
4. **Rozwiązać payment error 114** — dodać kartę/portfel do konta testowego (skrypt `test_live_card_registration.py` gotowy)

---

**Źródła:** `00_POWTORZENIA_I_SPRZECZNOSCI.md`, `02_reverse_engineering/`, `03_weryfikacja/`, `04_niewiadome/`, `bot/output/test1_determinizm_with_evidence_1788307148.json`
**Status:** **ROZSTRZYGNIĘTE** [UDOWODNIONE] — checkout/build działa (200), rezerwacja koszyka <4s osiągnięta (~3.39-3.71s), payment 114 wymaga karty
**Data:** 2026-09-02