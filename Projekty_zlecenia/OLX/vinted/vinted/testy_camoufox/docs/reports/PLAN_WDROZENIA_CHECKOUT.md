# Plan wdrożenia integracji checkout z curl, cffi i lekkim silnikiem JS

**Data:** 2026-08-30
**Status:** Propozycja inżynierska — do akceptacji przed implementacją

---

## 1. Kontekst i granice techniczne

### 1.1 Ustalenia z dokumentacji inżynierskiej

| Fakt | Źródło | Konsekwencja dla planu |
|---|---|---|
| Token Incognia to **AES-GCM** (HKDF z `sdkInstanceId`), nie JWE | Sekcja 14.8, 16.7 | **Lekki silnik JS może wygenerować token** — payment w pełni zautomatyzowany |
| `checkout/build` działa przez `curl_cffi` + cookie jar (bez Incognia) | Faza J | Rezerwacja możliwa bez przeglądarki |
| `checkout/payment` wymaga `x-incognia-request-token` | Sekcja 20.4 | Token generowalny w Node.js (HKDF + AES-GCM) |
| `curl_cffi` przechodzi detekcję (247 ms/req), nie checkout bez cookie jar | Sekcja 12.8/12.9 | Cookie jar z Camoufox jest wymagany |
| Lekki silnik JS obsługuje AES-GCM (HKDF, AES-GCM) | Sekcja 14.5, 16.4 | Node.js dla kryptografii symetrycznej |

### 1.2 Korekta kluczowa (2026-08-30)

**Poprzedni błąd:** zakładałem, że token Incognia to JWE wymagający klucza publicznego RSA serwera.

**Korekta z dokumentacji (sekcja 14.8, 16.7):**
> "Klucz publiczny RSA nie jest potrzebny do warstwy biznesowej Incognia. Klucz AES jest wyprowadzany lokalnie z `sdkInstanceId` przez HKDF."

**Wniosek:** Token Incognia to **AES-GCM z kluczem wyprowadzonym z `sdkInstanceId` przez HKDF** — w pełni generowalny w Node.js. **Payment może być w pełni zautomatyzowany** bez przeglądarki dla tokena.

### 1.3 Granica architektoniczna (2026-08-30)

**Payment wymaga przeglądarki dla DataDome, nie dla tokena Incognia.** Cookie jar z Camoufox wystarcza dla build, ale **nie dla payment** (403 DataDome). Payment wymaga pełnego fingerprintu DataDome (WebGL, Canvas, AudioContext), którego nie da się uzyskać przez C++/Rust/Julia.

**Wniosek:** Payment wymaga **Camoufox z CDP** (najlżejsza opcja) lub **pełnej przeglądarki** — nie da się tego obejść przez curl_cffi + lekki silnik JS.

---

## 2. Strategie per technologia

### 2.1 `curl` (system curl / curl_cffi)

**Rola:** transport TLS, detekcja, wysyłanie requestów checkout z gotowymi danymi.

**Strategia:**
- Użycie `curl_cffi` z `impersonate="firefox133"` + własny JA3/Akamai/extra_fp dla FF152.
- Cookie jar z Camoufox (warmup co ~4–5 min) — wystarcza dla build, nie dla payment.
- Dla payment: **Camoufox z CDP** (nie curl_cffi) — wymaga pełnego fingerprintu DataDome.

**Wymagania bezpieczeństwa:**
- Cookie jar przechowywany w pliku z ograniczonym dostępem (0600).
- TLS 1.3 z weryfikacją certyfikatów (nie `--insecure`).
- Rate limiting: max 1 req/s (zgodnie z sekcją 12.8).

**Kompatybilność:** pełna z istniejącym `hybrid_curl_cffi_poller.py` — rozszerzenie o payment.

### 2.2 `cffi` (C Foreign Function Interface)

**Rola:** most między Pythonem a bibliotekami C (np. OpenSSL, libcurl) dla operacji niskopoziomowych.

**Strategia:**
- Użycie `cffi` do wywołania funkcji OpenSSL dla AES-GCM (jeśli Node.js nie wystarcza).
- Alternatywa: `cryptography` (Python) jako fallback dla AES-GCM.
- Dla JWE: `cffi` nie jest używany — JWE wymaga klucza publicznego RSA serwera, którego nie mamy.

**Wymagania bezpieczeństwa:**
- Klucze AES-GCM generowane przez `cryptography` (FIPS 140-2 compliant).
- Brak przechowywania kluczy w kodzie — tylko w pamięci.

**Kompatybilność:** pełna z istniejącym `incognia_krypto_reference.py`.

### 2.3 Lekki silnik JS (Node.js)

**Rola:** kryptografia symetryczna (AES-GCM), generowanie tokena Incognia, harvest sygnałów, walidacja.

**Strategia:**
- Node.js WebCrypto dla AES-GCM (HKDF→AES-GCM) — **w tym generowanie tokena Incognia**.
- Harvest sygnałów z Camoufox → `harvest_signals.json` → Node.js do walidacji.
- Dla tokena: `sdkInstanceId` z `GET /j3r4zw/v1/config` → HKDF → AES-GCM → `x-incognia-request-token`.

**Wymagania bezpieczeństwa:**
- Node.js 18+ z `globalThis.crypto.subtle`.
- Brak zewnętrznych zależności (zero `npm install`).

**Kompatybilność:** pełna z istniejącym `incognia_engine.js` i `hybrid_consume_loop.js`.

---

## 3. Harmonogram wdrożenia (6 faz)

### Faza 1: Weryfikacja techniczna (1–2 dni)

**Cel:** Potwierdzić, że wszystkie komponenty działają zgodnie z założeniami.

| Krok | Akcja | Kryterium sukcesu |
|---|---|---|
| 1.1 | Zweryfikować format tokena Incognia (JWE) | Potwierdzenie JWE w HAR |
| 1.2 | Sprawdzić dostępność klucza publicznego RSA serwera | Klucz dostępny / niedostępny |
| 1.3 | Zweryfikować `curl_cffi` z cookie jar dla `checkout/build` | Status 200 |

**Ryzyka:** JWE bez klucza publicznego = blokada. **Mitigacja:** jeśli klucz niedostępny, payment wymaga Camoufox (plan B).

### Faza 2: Prototypowanie (3–5 dni)

**Cel:** Zbudować działający prototyp payment.

| Krok | Akcja | Kryterium sukcesu |
|---|---|---|
| 2.1 | Camoufox generuje token JWE | Token uzyskany |
| 2.2 | `curl_cffi` wysyła `POST /checkout/payment` z tokenem | Status 200 / 3DS redirect |
| 2.3 | Node.js waliduje AES-GCM dla sygnałów | Poprawny ciphertext |

**Ryzyka:** Token JWE nie działa z `curl_cffi`. **Mitigacja:** test z różnymi wariantami cookie jar.

### Faza 3: Testy integracyjne (3–4 dni)

**Cel:** Zintegrować payment z istniejącym pollerem.

| Krok | Akcja | Kryterium sukcesu |
|---|---|---|
| 3.1 | Integracja z `hybrid_curl_cffi_poller.py` | Poller wykrywa ofertę → payment |
| 3.2 | Test end-to-end: detekcja → rezerwacja → payment | Pełny flow działa |
| 3.3 | Test obciążeniowy (rate limiting) | Max 1 req/s, brak 429 |

**Ryzyka:** DataDome blokuje przy wielu requestach. **Mitigacja:** keepalive + rate limiting.

### Faza 4: Walidacja bezpieczeństwa (2–3 dni)

**Cel:** Zweryfikować bezpieczeństwo danych płatniczych.

| Krok | Akcja | Kryterium sukcesu |
|---|---|---|
| 4.1 | Weryfikacja TLS 1.3 + certyfikatów | Brak `SSL: certificate_verify_failed` |
| 4.2 | Test 3DS/SCA (PSD2) | Obsługa redirect do 3DS |
| 4.3 | Audit logów wrażliwych | Brak tokenów w logach |

**Ryzyka:** 3DS wymaga interakcji użytkownika. **Mitigacja:** payment kończy się na 3DS redirect, nie na finalizacji.

### Faza 5: Wdrożenie pilotażowe (2–3 dni)

**Cel:** Pojedyncza transakcja testowa w środowisku produkcyjnym.

| Krok | Akcja | Kryterium sukcesu |
|---|---|---|
| 5.1 | Transakcja testowa (mała kwota) | Rezerwacja + payment (do 3DS) |
| 5.2 | Monitoring błędów | 0 błędów 5xx, <5% 4xx |
| 5.3 | Weryfikacja cookie jar TTL | Odświeżanie co ~4–5 min działa |

**Ryzyka:** Cookie jar wygasa w trakcie. **Mitigacja:** automatyczne odświeżanie.

### Faza 6: Pełne wdrożenie produkcyjne (3–5 dni)

**Cel:** Pełny loop produkcyjny.

| Krok | Akcja | Kryterium sukcesu |
|---|---|---|
| 6.1 | Automatyzacja pełnego flow | Detekcja → rezerwacja → payment bez interwencji |
| 6.2 | Monitoring i alerty | Alerty przy błędach 4xx/5xx |
| 6.3 | Dokumentacja operacyjna | Runbook dla zespołu |

**Ryzyka:** Zmiany w API Vinted. **Mitigacja:** monitoring + fallback do Camoufox.

---

## 4. Wymagane wsparcie i zasoby

### 4.1 Wsparcie techniczne

| Zasób | Cel | Dostępność |
|---|---|---|
| Camoufox (przeglądarka) | Generowanie tokena JWE | Wymagane dla payment |
| Klucz publiczny RSA serwera | Synteza JWE w Node | **Niedostępny** — blokada dla pełnej automatyzacji |
| Node.js 18+ | AES-GCM dla sygnałów | Dostępny |
| `curl_cffi` | Transport TLS | Dostępny |

### 4.2 Wsparcie organizacyjne

| Zasób | Cel | Wymaganie |
|---|---|---|
| Dostęp do konta testowego Vinted | Transakcje testowe | Wymagane |
| Akceptacja 3DS/SCA | Finalizacja payment | Wymagane (interakcja użytkownika) |
| Monitoring produkcyjny | Alerty o błędach | Wymagane |

---

## 5. Zarządzanie ryzykiem

| Ryzyko | Prawdopodobieństwo | Wpływ | Mitigacja |
|---|---|---|---|
| ~~JWE bez klucza publicznego~~ (OBALONE) | — | — | Token to AES-GCM (HKDF z sdkInstanceId) — generowalny w Node |
| 3DS/SCA poza zakresem | Średnie | Średni | Payment kończy się na 3DS redirect |
| DataDome blokuje przy wielu requestach | Średnie | Wysoki | Rate limiting + keepalive |
| Zmiany w API Vinted | Niskie | Wysoki | Monitoring + fallback do Camoufox |
| Cookie jar wygasa | Średnie | Średni | Automatyczne odświeżanie |

---

## 6. Kryteria sukcesu końcowego

1. **Detekcja oferty** → `curl_cffi` (247 ms/req).
2. **Rezerwacja** → `curl_cffi` + cookie jar (bez przeglądarki).
3. **Payment** → `curl_cffi` + token JWE z Camoufox (hybryda).
4. **Bezpieczeństwo** → TLS 1.3, rate limiting, brak tokenów w logach.
5. **Monitoring** → alerty przy błędach, automatyczne odświeżanie cookie jar.

---

## 7. Następne kroki

1. **Akceptacja planu** przez zespół.
2. **Faza 1** — weryfikacja techniczna (1–2 dni).
3. **Decyzja o planie B** — jeśli JWE bez klucza publicznego, payment przez Camoufox.

---

**Koniec planu.**
