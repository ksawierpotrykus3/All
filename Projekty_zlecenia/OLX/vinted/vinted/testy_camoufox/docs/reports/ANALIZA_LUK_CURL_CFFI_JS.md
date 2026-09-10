# ANALIZA LUK: curl_cffi + lekki silnik JS vs pełny frontend

**Data:** 2026-08-29  
**Cel:** Określić co brakuje by `curl_cffi` + `incognia_engine.js` zrobił pełny checkout samych endpointami

---

## 1. PEŁNY FLOW FRONTEND (co robi przeglądarka krok po kroku)

```
1. NAVIGATE do strony przedmiotu (GET /items/123)
   ├── TLS handshake (JA3/JA4 + HTTP/2 settings + cert compression)
   ├── HTML response + Set-Cookie (DataDome, Vinted session)
   ├── Wykonywanie JS: DataDome SDK 5.9.2
   │   ├── Fingerprint: canvas, WebGL, fonts, audio, navigator, screen
   │   ├── Cookie `datadome` ustawiany przez JS
   │   ├── Tokeny DataDome w localStorage
   │   └── Event listeners (mousemove, click, scroll)
   ├── Wykonywanie JS: Incognia SDK (k7v3q2.vinted.com/85d7e768568e.js)
   │   ├── POST /info → GET /netconn → WS upgrade (JWE token)
   │   ├── HKDF(sdkInstanceId) → AES-256-GCM key
   │   ├── Snapshot (type="pls"): 111 sygnałów → POST /v1/consume
   │   ├── Interaction loop (type="it"): co 5s flush → POST /v1/consume
   │   └── Event listeners (pointer, keyboard, scroll, visibility)
   ├── Renderowanie React/Vue (ateam bundle)
   └── Kliknięcie "Kup teraz" (isTrusted: true)

2. POST /checkout/build (X-CSRF-Token, cookies, headers)
   ├── Body: { item_id, quantity, ... }
   ├── Response: purchase_id + redirect URL
   └── Set-Cookie: nowe ciasteczka transakcyjne

3. PUT /purchases/{purchase_id}/checkout
   ├── Body: { payment_method, ... }
   ├── Headers: X-CSRF-Token, Referer, Origin, cookies
   └── Response: order_id / redirect do płatności

4. PŁATNOŚĆ (3D Secure, Przelewy24, itp.)
```

---

## 2. CO MA curl_cffi (STAN OBECNY)

| Komponent | Status curl_cffi |
|-----------|------------------|
| TLS JA3/JA4 | ✅ `full_ja3_akamai_extra` = identyczny Firefox 152 |
| HTTP/2 frames | ⚠️ Częściowo (settings frame może się różnić) |
| Certificate compression | ❌ Nieobsługiwane (zlib/zstd) |
| Cookie jar | ✅ Pełna obsługa |
| Redirect handling | ✅ |
| Custom headers | ✅ |
| Body (JSON/form) | ✅ |
| **JavaScript execution** | ❌ **BRAK** |
| **DOM/Canvas/WebGL/Audio** | ❌ **BRAK** |
| **Event loop / listeners** | ❌ **BRAK** |
| **Trusted events (isTrusted)** | ❌ **BRAK** |
| **WebSocket** | ⚠️ Tylko handshake, brak ramek |
| **localStorage/IndexedDB** | ❌ **BRAK** |

---

## 3. CO MA NASZ SILNIK JS (`incognia_engine.js`)

| Komponent | Status silnika |
|-----------|----------------|
| HKDF + AES-GCM | ✅ Pełna implementacja WebCrypto |
| Payload /v1/consume | ✅ Generuje poprawny JSON + base64(IV||ct) |
| Snapshot collectors (17) | ✅ 111 sygnałów (mockowane) |
| Interaction collectors (7) | ✅ Struktura gotowa (mockowana) |
| **Prawdziwy Canvas/WebGL/Audio** | ❌ Mocki (losowe/statyczne dane) |
| **Prawdziwy navigator.permissions** | ❌ Mocki |
| **Prawdziwy localStorage/IndexedDB** | ❌ Mocki |
| **Event listeners (pointer/keyboard/scroll)** | ❌ Brak event loop |
| **WebSocket Incognia** | ❌ Tylko HTTP /v1/consume |
| **DataDome SDK** | ❌ **CAŁKOWITE BRAK** |

---

## 4. MAPA LUK (co trzeba dodać by to zadziałało)

### 4.1 KRYTYCZNE (blokery — bez tego 403/400)

| Luki | Co trzeba zrobić | Trudność |
|------|------------------|----------|
| **DataDome SDK** | Pełna implementacja DataDome 5.9.2 w Node: OffscreenCanvas, WebGL, trustToken, audio fingerprint, behavioral signals | **BARDZO WYSOKA** (116 KB obfuskowanego kodu, anti-debug) |
| **Trusted click** | Symulacja `isTrusted: true` — **niemożliwe w Node** (to browser security feature) | **NEMOŻLIWE** bez przeglądarki |
| **TLS Certificate Compression** | curl_cffi musi obsłużyć zlib/zstd cert compression (Akamai wymaga) | ŚREDNIA (patch curl_cffi / OpenSSL) |
| **HTTP/2 Settings Frame** | Dopasować dokładnie Firefox 152: SETTINGS_HEADER_TABLE_SIZE, SETTINGS_ENABLE_PUSH, SETTINGS_MAX_CONCURRENT_STREAMS, SETTINGS_INITIAL_WINDOW_SIZE, SETTINGS_MAX_FRAME_SIZE | NISKA (konfiguracja curl_cffi) |
| **Cookie `datadome`** | Generowany przez DataDome SDK po fingerprintowaniu | ZALEŻNE OD DATA DOME |
| **localStorage/IndexedDB DataDome** | Tokeny, session data zapisywane przez SDK | ŚREDNIA (mock w Node) |

### 4.2 WAŻNE (bez tego ryzyko wykrycia/anomalii)

| Luki | Co trzeba zrobić | Trudność |
|------|------------------|----------|
| **Prawdziwe sygnały Incognia** | Zastąpić mocki prawdziwymi: canvas (npm `canvas`), WebGL (npm `canvas` + `gl`), audio (npm `web-audio-api`), fonts (npm `canvas` + `fontkit`) | WYSOKA (wymaga natywnych modułów) |
| **Behavioral signals** | Ruch myszy (krzywe Beziera, prędkość, dwell), klawiatura (inter-key timing), scroll (fizyka), focus/visibility | WYSOKA (symulacja ludzkiego zachowania) |
| **Incognia WebSocket** | Pełny handshake JWE + ramki binarne (protobuf?) | ŚREDNIA (reverse engineering WS) |
| **SDK Instance ID lifecycle** | `/v1/config` → generuje `sdkInstanceId` → używany przez Incognia | NISKA (endpoint gotowy) |
| **DataDome challenge/response** | Rozwiązywanie wyzwań (CAPTCHA, sliding puzzle) | **BARDZO WYSOKA** |

### 4.3 NICE TO HAVE (dla production readiness)

| Luki | Co trzeba zrobić |
|------|------------------|
| Rotacja `sdkInstanceId` na sesję | Nowy UUID per sesja |
| Persistencja cookies między requestami | Cookie jar współdzielony |
| Rate limiting / backoff | Respektowanie 429/5xx |
| Monitoring / logging | Metryki sukcesu/błędów |

---

## 5. OCENA WYKONALNOŚCI

### Scenariusz A: curl_cffi + incognia_engine.js (BEZ DataDome)

```
❌ NIE PRZEJDZIE
- DataDome blokuje na poziomie TLS/HTTP przed dotarciem do checkoutu
- Brak cookie `datadome` = insta-block
- Brak behavioral signals = anomalii
```

### Scenariusz B: curl_cffi + incognia_engine.js + DataDome SDK w Node

```
⚠️ TEORETYCZNIE MOŻLIWE, ALE:
- DataDome 5.9.2 = 116 KB obfuskowanego JS z anti-debug
- Wymaga: OffscreenCanvas, WebGL2, trustToken, AudioWorklet
- Wymaga: prawdziwego fingerprintu (nie mocków)
- Wymaga: rozwiązywania challenge'ów
- Koszt: 2-4 tygodnie reverse engineering + implementacja
- Ryzyko: DataDome aktualizuje SDK co tydzień → cat & mouse
```

### Scenariusz C: curl_cffi + incognia_engine.js + **prawdziwa przeglądarka headless** (Camoufox/Playwright) dla DataDome

```
✅ TO JEST NASZA OBECNA ARCHITEKTURA (hybryda):
- Camoufox robi: DataDome + Incognia + trusted click + TLS fingerprint
- curl_cffi robi: detekcja produktu (szybko, tanio)
- Checkout idzie przez Camoufox
```

---

## 6. KONKRETNE KROKI BY ZROBIĆ SCENARIUSZ B (jeśli się upierasz)

Jeśli **koniecznie** chcesz bez przeglądarki, to minimalny plan:

### Faza 1: TLS/HTTP parity (1-2 dni)
```python
# curl_cffi patches needed:
1. Certificate compression (zstd) — patch OpenSSL / curl
2. HTTP/2 SETTINGS frame exact match Firefox 152
3. ALPN h2 + http/1.1 fallback
```

### Faza 2: DataDome SDK w Node (3-6 tygodni)
```
1. Pobierz DataDome SDK z HAR (static-assets.vinted.com/datadome/...)
2. Deobfuskacja (string array + control flow flattening)
3. Zidentyfikuj wszystkie fingerprint collectors
4. Zaimplementuj w Node z natywnymi bindingami:
   - canvas → npm `canvas` (Cairo)
   - WebGL → npm `canvas` + `gl` (ANGLE/SwiftShader)
   - Audio → npm `web-audio-api` (native)
   - Fonts → npm `fontkit` + `canvas`
   - trustToken → polyfill (Chrome-only API)
5. Zaimplementuj behavioral model (mouse/keyboard/scroll)
6. Zaimplementuj challenge solver (CAPTCHA)
```

### Faza 3: Incognia WebSocket + JWE (1 tydzień)
```
1. Reverse engineering JWE token (RSA-OAEP + AES-CBC)
2. WebSocket frame format (protobuf?)
3. Synchronizacja z HTTP /v1/consume
```

### Faza 4: Integracja + testy (1 tydzień)
```
1. Pełny flow: TLS → DataDome → Incognia → checkout/build → purchase/checkout
2. Test na produkcji (ryzyko bana)
3. Monitoring anomalii
```

**SZACUNKOWY CZAS: 6-10 tygodni pracy 1 osoby doświadczonej w RE**

---

## 7. DLACZEGO TO NIE MA SENSU (biznesowo)

| Czynnik | Wartość |
|---------|---------|
| Koszt rozwoju (Faza 1-4) | ~3-5 miesięcy pracy seniora |
| Koszt utrzymania (DataDome update co tydzień) | Ciągła gra kota z myszką |
| Ryzyko prawne | DataDome ToS zabrania reverse engineering |
| Obecne rozwiązanie (Camoufox) | Działa, 20s/rezerwacja, 100% pass-rate |
| Zysk z "pure HTTP" | ~5s oszczędności na rozruchu przeglądarki |

**ROI: NEGATYWNE**

---

## 8. REKOMENDACJA

**Zostań przy hybrydzie (sekcja 12.8):**

```
curl_cffi (detekcja, <1s) → Camoufox (checkout, ~20s)
```

To jedyna sprawdzona, utrzymywalna architektura.

Jeśli **musisz** zoptymalizować czas:
1. Pool Camoufox instancji (warm browsers) → -15s na rozruch
2. Trwały profil Firefox (cookies, localStorage) → -5s
3. Async checkout queue → równoległość

---

## 9. PLIKI DOWODOWE

| Plik | Co dowodzi |
|------|------------|
| `wynik_curl_cffi_firefox152.json` | 33 strategie = 403 captcha |
| `incognia_engine.js` | Silnik generuje poprawny payload Incognia |
| `incognia_collectors_snapshot.js` | 111 sygnałów (mockowane) |
| `DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md` sekcje 12.8, 12.9, 13.1 | Pełna analiza dlaczego curl_cffi failuje |
| `spike_B4b_incognia_loader.py` | DataDome blokuje Incognia w headless |

---

## 10. WNIOSKI

**curl_cffi + lekki silnik JS NIE ZROBI PEŁNEGO CHECKOUTU** bez:
1. Pełnej implementacji DataDome SDK w Node (bardzo trudne, cat & mouse)
2. Rozwiązania `isTrusted: true` (niemożliwe bez przeglądarki)
3. Certificate compression + HTTP/2 settings parity (doable ale kosztowne)

**Najlepsza ścieżka:** Użyj Camoufox do checkoutu, curl_cffi do detekcji. To co masz **już działa**.