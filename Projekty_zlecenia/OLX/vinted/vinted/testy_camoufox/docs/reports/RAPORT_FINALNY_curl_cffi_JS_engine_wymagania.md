# RAPORT KOŃCOWY: Wymagania curl_cffi + Lekki Silnik JS do Replikacji Przeglądarki Vinted

**Data:** 2026-08-30  
**Status:** Analiza zakończona — **DataDome blokuje na warstwie transportowej (HTTP 403), nie da się przejść bez przeglądarki**

---

## 1. EXECUTIVE SUMMARY

Przeprowadzono kompleksową analizę i testy endpointu `POST /api/v2/purchases/checkout/build` dla produktu `https://www.vinted.pl/items/9807925466-genesis-krypton-700` używając:

- **Playwright MCP** — nawigacja, kliknięcie "Kup teraz", analiza flow
- **HAR (48MB, 824 entries)** — analiza requestów: checkout/build, payment, Incognia, DataDome, cchd_config
- **curl_cffi + custom Firefox 152 fingerprint** — 4 testy z różnymi konfiguracjami
- **Node.js WebCrypto** — weryfikacja kryptografii Incognia (HKDF, AES-GCM, JWE)

**WYNIK: Wszystkie testy curl_cffi zwracają HTTP 403 z wyzwaniem DataDome CAPTCHA. Nie da się przejść do warstwy Incognia bez przeglądarki.**

---

## 2. ANATOMIA REQUESTU CHECKOUT/BUILD (z HAR)

### 2.1 Endpoint i Payload
```
POST https://www.vinted.pl/api/v2/purchases/checkout/build
Body: {"purchase_items":[{"id":21872241924,"type":"transaction"}]}
```

### 2.2 Wymagane Nagłówki (z HAR)
| Nagłówek | Wartość (przykład) | Źródło |
|----------|-------------------|--------|
| `User-Agent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 OPR/134.0.0.0` | HAR (Opera GX) |
| `Accept` | `application/json,text/plain,*/*,image/webp` | HAR |
| `Accept-Language` | `pl,en-US;q=0.9,en;q=0.8,ru;q=0.7` | HAR |
| `Accept-Encoding` | `gzip, deflate, br, zstd` | HAR |
| `Content-Type` | `application/json` | HAR |
| `Origin` | `https://www.vinted.pl` | HAR |
| `Referer` | `https://www.vinted.pl/items/9807925466-genesis-krypton-700` | HAR |
| `Sec-Ch-Ua` | `"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"` | HAR |
| `Sec-Ch-Ua-Mobile` | `?0` | HAR |
| `Sec-Ch-Ua-Platform` | `"Windows"` | HAR |
| `Sec-Fetch-Dest` | `empty` | HAR |
| `Sec-Fetch-Mode` | `cors` | HAR |
| `Sec-Fetch-Site` | `same-origin` | HAR |
| `Priority` | `u=3` | HAR |
| `Locale` | `pl-PL` | HAR |
| **`X-Anon-Id`** | `98c6af5a-87da-45f2-9be5-24cf9345b003` (UUID) | HAR |
| **`X-Csrf-Token`** | `75f6c9fa-dc8e-4e52-a000-e09dd4084b3e` (UUID) | HAR |
| **`X-Incognia-Request-Token`** | JWE (RSA-OAEP + A128CBC-HS256) | HAR |

### 2.3 TLS Fingerprint (wymagany dla curl_cffi)
Zmierzony **Firefox 152** (Camoufox rv:152.0) — **100% match JA3**:
```
JA3:     6447ab086255d194909d4013b1a89e87
JA4:     t13d1617h2_86a278354501_3cbfd9057e0d
Akamai:  1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s
Extensions:
  - delegated_credential (34): ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:ecdsa_secp521r1_sha512:ecdsa_sha1
  - record_size_limit (28): 16385
  - cert_compression: zstd
```

---

## 3. WARSTWY OCHRONY (Kolejność Sprawdzania)

```
┌─────────────────────────────────────────────────────────────────┐
│ REQUEST → Cloudflare → DataDome → Incognia → Business Logic    │
└─────────────────────────────────────────────────────────────────┘
```

| Warstwa | Co Sprawdza | Czy curl_cffi + JS Engine Przejdzie? |
|---------|-------------|--------------------------------------|
| **Cloudflare** | TLS fingerprint, IP reputation, __cf_bm cookie | ⚠️ Tak (z FF152 fingerprint) |
| **DataDome** | **OffscreenCanvas, WebGL, AudioContext, trustToken, behavioral** | ❌ **NIE** — wymaga przeglądarki |
| **Incognia** | x-incognia-request-token (JWE), device fingerprint, behavioral | ⚠️ Tak (kryptografia w JS), ale nigdy nie docieramy |
| **Business Logic** | CSRF, session, payment | ✅ Tak |

---

## 4. DATA DOME — DLACZEGO BLOKUJE (Analiza HAR + Testy)

### 4.1 Dowody z HAR i Testów
```json
// Response 403 headers:
"x-datadome": "protected"
"accept-ch": "Sec-CH-UA,Sec-CH-UA-Mobile,Sec-CH-UA-Platform,Sec-CH-UA-Arch,Sec-CH-UA-Full-Version-List,Sec-CH-UA-Model,Sec-CH-Device-Memory"
"set-cookie": "datadome=...; __cf_bm=..."
```

### 4.2 Challenge URL
```
https://geo.captcha-delivery.com/captcha/?initialCid=...&cid=...&referer=...&hash=E6EAF460AA2A8322D66B42C85B62F9&t=fe&s=55108&e=...&b=2021763
```
- `hash=E6EAF460AA2A8322D66B42C85B62F9` — **DataDome JS key** (widoczny w spike_B4_decision.py: `window.ddjskey`)

### 4.3 Co DataDome Wymaga (z deobfuskacji DataDome 5.9.2 + spike B)
| API Przeglądarki | Użycie | Dostępne w Node.js? |
|------------------|--------|---------------------|
| `OffscreenCanvas` | Canvas fingerprint bez DOM | ❌ |
| `WEBGL_debug_renderer_info` | Unmasked GPU vendor/renderer | ❌ |
| `AudioContext` / `OfflineAudioContext` | Audio fingerprint (sum, sampleRate) | ❌ |
| `trustToken` (Privacy Pass) | Chrome-only anti-bot | ❌ (tylko Chrome) |
| `performance.now()` | High-res timing | ⚠️ `Date.now()` approx |
| `navigator.webdriver` + 38+ automation checks | Bot detection | ❌ |
| Behavioral (mouse, keyboard, scroll) | Human-like patterns | ❌ |

**Wniosek: DataDome 5.9.2 celowo używa API niedostępnych w Node.js/curl_cffi. To "hard block" by design.**

---

## 5. INCOGNIA — Co Potrafi Lekki Silnik JS, a Co Nie

### 5.1 Co Lekki Silnik JS (Node.js WebCrypto) POTRAFI ✅
| Operacja | Standard | Implementacja |
|----------|----------|---------------|
| HKDF-SHA256 derive key | RFC 5869 | `crypto.subtle.deriveKey` |
| AES-256-GCM encrypt/decrypt | RFC 5116 | `crypto.subtle.encrypt/decrypt` |
| RSA-OAEP (key wrapping) | RFC 8017 | `crypto.subtle.wrapKey/unwrapKey` |
| JWE Compact (A128CBC-HS256) | RFC 7516 | Manual (AES-CBC + HMAC) |
| x-incognia-request-token generation | — | **Tak, jeśli masz sygnały** |

**Zweryfikowane cross-verified:** Node.js WebCrypto ≡ Python `cryptography` (identyczne klucze/ciphertext).

### 5.2 Co Lekki Silnik JS NIE POTRAFI ❌ (Wymaga Przeglądarki)

#### A. Device Fingerprint (Snapshot Collectors — 15 typów)
| Collector | Sygnały | Browser API |
|-----------|---------|-------------|
| Canvas | SHA-256(PNG), alphaNonzeroRatio | `canvas.toDataURL`, `getImageData` |
| WebGL | vendor, renderer, **unmasked**, extensions, params, **renderHash** (triangle shader) | `WebGLRenderingContext`, `WEBGL_debug_renderer_info` |
| Audio | OfflineAudioContext: oscillator → compressor → sum, sampleRate, channels | `OfflineAudioContext`, `createDynamicsCompressor` |
| Fonts | 125 fontów — offsetWidth trick | `document.createElement`, `offsetWidth` |
| Permissions | geolocation, notifications, camera, microphone, persistent-storage | `navigator.permissions.query()` |
| Storage | cookie, localStorage, indexedDB, quota, usage, persisted | `document.cookie`, `localStorage`, `indexedDB`, `navigator.storage` |
| Navigator | userAgentData, hardwareConcurrency, deviceMemory, connection, maxTouchPoints, gpu, mediaDevices | `navigator.*` |
| Screen | inner/outer, devicePixelRatio, visualViewport, orientation, pointer/hover | `window.screen`, `visualViewport`, `matchMedia` |
| Timezone | timeZone, timezoneOffset, clockDeltaMs (performance.timeOrigin) | `Intl.DateTimeFormat`, `performance.timeOrigin` |
| Media | canPlayType (14 audio + 9 video), MSE | `HTMLAudioElement.canPlayType`, `MediaSource` |
| WebGPU | `navigator.gpu` | `navigator.gpu` |

#### B. Behavioral Signals (Interaction Collectors — 6 typów)
| Collector | Sygnały | Wymaga `isTrusted=true` |
|-----------|---------|------------------------|
| Clock | visibleMs, focusedMs | `visibilitychange`, `focus`/`blur` |
| Mouse Hover | overCount, outCount, dwellMsP50/P95 | `mouseover`/`mouseout` |
| Keyboard | keydown/keyup, interKeyMsP50/P95, paste | `keydown`/`keyup`/`paste` |
| Pointer | move/down/up/click, pointerType, timeToFirstPointer, movePause | `pointermove`/`down`/`up`/`click` |
| Scroll | scrollCount, maxDepthBucket, speedP50/P95 | `scroll` + `requestAnimationFrame` |
| Touch | (mobile) | `touchstart`/`move`/`end` |

**Kluczowe:** Wszystkie interaction collectors **weryfikują `event.isTrusted`**. Symulowane eventy mają `isTrusted=false` → odrzucane.

### 5.3 Transport Incognia
```
GET  /j3r4zw/v1/config          → config (apiBaseUrl, sdkInstanceId, loaderTimings)
POST /j3r4zw/v1/consume         → encrypted signals (AES-GCM + base64)
WS   wss://*.incognia.com/...   → binary frames (protokół nieznany, Opera nie loguje)
```

---

## 6. CCHD_CONFIG — Co Zwraca (Analiza HAR + Spike)

| Endpoint | Response | Format |
|----------|----------|--------|
| `GET https://metrics.vinted.lt/web/cchd_config` | JWE (1042B) | `application/jwt` |
| `GET https://metrics.vinted.lt/web/pvt_cchd_config` | JWE (1042B) | `application/jwt` |

**JWE Header:** `{"alg":"RSA-OAEP","enc":"A128CBC-HS256"}`

**Ważne:** To **NIE jest surowy klucz publiczny RSA** — to zaszyfrowany payload. Klucz prywatny jest tylko u serwera Incognia. Do generowania `x-incognia-request-token` potrzebny jest klucz sesyjny z HKDF(`sdkInstanceId`), a nie klucz z cchd_config.

---

## 7. MINIMALNY ZESTAW DO REPLIKACJI PRZEGLĄDARKI

### 7.1 Co curl_cffi MUSI ZROBIĆ (Transport Layer) ✅ ZROBIONE
```python
# Wymagane parametry curl_cffi:
session.post(url,
    json=payload,
    impersonate="firefox133",           # bazowy profil
    ja3=FF152_JA3,                       # custom JA3 Firefox 152
    akamai=FF152_AKAMAI,                 # custom Akamai fingerprint
    extra_fp=FF152_EXTRA_FP,             # delegated_cred, record_size_limit, cert_compression
    timeout=30
)
```

### 7.2 Nagłówki HTTP (z HAR) — curl_cffi ROBI ✅
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "application/json,text/plain,*/*,image/webp",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    "Origin": "https://www.vinted.pl",
    "Referer": "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
    "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"',  # lub FF152 UA
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=3",
    "Locale": "pl-PL",
    "X-Anon-Id": "<UUID>",              # musi być aktualny z sesji
    "X-Csrf-Token": "<UUID>",           # musi być aktualny z sesji
    "X-Incognia-Request-Token": "<JWE>", # MUSI byc aktualny z SDK
}
```

### 7.3 Co Lekki Silnik JS (Node.js) MUSI ZROBIĆ (Crypto Layer) ✅ ZROBIONE
```javascript
// Wymagane moduły (demo_node_crypto.js):
1. HKDF-SHA256 derive session key z sdkInstanceId (salt="L6ZhSbP9TciQDgxC7pjukGhl4vYis56m")
2. AES-256-GCM encrypt payload (IV 12B, AAD="incognia-sdk-v1")
3. JWE RSA-OAEP + A128CBC-HS256 encrypt/decrypt (cchd_config format)
4. WebCrypto API only — zero native dependencies
```

### 7.4 Co NIE DA SIĘ ZROBIĆ BEZ PRZEGLĄDARKI ❌

| Komponent | Dlaczego | Rozwiązanie |
|-----------|----------|-------------|
| **DataDome Challenge** | OffscreenCanvas, WebGL, AudioContext, trustToken | **Tylko prawdziwa przeglądarka (Camoufox/Playwright)** |
| **Incognia SDK Loading** | Ładuje się z CDN `*.incognia.com`, wymaga `window`, `document`, `navigator` | Tylko przeglądarka |
| **Device Fingerprint (15 collectors)** | Canvas, WebGL (unmasked), Audio, Fonty, Permissions, Storage, WebGPU... | Tylko przeglądarka |
| **Behavioral Signals (6 collectors)** | `isTrusted=true` events (mouse, keyboard, scroll, pointer) | Tylko prawdziwe user events |
| **`x-incognia-request-token` Generation** | Wymaga uruchomionego SDK + sygnałów fingerprint/behavioral | Tylko przeglądarka z SDK |
| **WebSocket Binary Frames** | Protokół nieznany, Opera nie loguje | Reverse engineering w przeglądarce |

---

## 8. ARCHITEKTURA REALISTYCZNA (Jedyna Sprawdzona — Faza 12)

```
┌────────────────────────────────────────────────────────────────────────┐
│                    HYBRYDA: Camoufox + curl_cffi                      │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  1. CAMOUFOX (Firefox 152, persistent context)                        │
│     ├── Warmup: nawigacja do item page                                │
│     ├── DataDome Challenge: Rozwiązany w przeglądarce (OffscreenCanvas│
│     │   WebGL, AudioContext, trustToken, behavioral)                  │
│     ├── Incognia SDK: Ładuje się, inicjalizuje, generuje              │
│     │   x-incognia-request-token, wysyła sygnały do /v1/consume       │
│     ├── Kliknięcie "Kup teraz" (isTrusted=true)                       │
│     └── POST /api/v2/purchases/checkout/build → 200 OK                │
│         ├── Przechwyć: cookies, x-incognia-request-token,             │
│         │   x-datadome-clientid, x-csrf-token, x-anon-id             │
│         └── Przechwyć: WebSocket handshake JWE (jeśli możliwe)        │
│                                                                        │
│  2. CURL_CFFI (Firefox 152 fingerprint)                               │
│     ├── Polling: GET /api/v2/catalog/items (247ms vs 719ms, 3× szybciej)│
│     │   Zero DataDome blocks, zero Incognia overhead                 │
│     ├── Rezerwacja: POST /checkout/build z przechwyconymi tokenami   │
│     │   (tokeny mają TTL — replay test Faza 8: 1-2h)                 │
│     └── Payment: POST /checkout/payment z nowym tokenem              │
│                                                                        │
│  ZWERYFIKOWANE: 4/4 rezerwacje pass-rate (Faza 12)                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 9. TESTY CURL_CFFI — WYNIKI (Ten Raport)

| Test | Fingerprint | UA | x-incognia-token | Wynik |
|------|-------------|-----|------------------|-------|
| 1 | FF152 custom | FF152 | HAR token | **403 DataDome** |
| 2 | FF152 custom | Chrome/Opera (HAR) | HAR token | **403 DataDome** |
| 3 | chrome131 built-in | Chrome/Opera (HAR) | HAR token | **403 DataDome** |
| 4 | FF152 custom | FF152 | **BEZ tokenu** | **403 DataDome** |

**Wniosek: DataDome blokuje WSZYSTKIE requesty na etapie TLS/HTTP — przed jakąkolwiek walidacją Incognia/Business Logic.**

---

## 10. SZCZEGÓŁOWA MAPA LUK (Co Brakuje)

| Luka | curl_cffi | Node.js WebCrypto | Wymaga Przeglądarki |
|------|-----------|-------------------|---------------------|
| TLS Fingerprint FF152 | ✅ JA3/JA4/Akamai + extensions | — | — |
| HTTP/2 + Headers | ✅ | — | — |
| Cookie Management | ✅ | — | — |
| Sec-CH-UA Headers | ✅ | — | — |
| X-Anon-Id, X-Csrf-Token | ✅ (manual) | — | — |
| **DataDome Challenge** | ❌ | ❌ | ✅ **TAK** |
| **OffscreenCanvas** | — | ❌ | ✅ |
| **WebGL (unmasked)** | — | ❌ | ✅ |
| **AudioContext/OfflineAudioContext** | — | ❌ | ✅ |
| **trustToken API** | — | ❌ | ✅ (Chrome only) |
| **Incognia SDK Load** | — | ❌ (no window/document) | ✅ |
| **Device Fingerprint (15 collectors)** | — | ❌ (no browser API) | ✅ |
| **Behavioral Signals (6 collectors)** | — | ❌ (no isTrusted) | ✅ |
| **x-incognia-request-token Generation** | — | ✅ Crypto only | ✅ **Needs SDK runtime** |
| **WebSocket Binary Frames** | ❌ (ws OK, but protocol unknown) | — | ✅ Reverse eng. |

---

## 11. PLIKI PROJEKTU (Gotowe do Użycia Edukacyjnego)

| Plik | Rola |
|------|------|
| `demo_curl_cffi_js_hkdf.py` | Orkiestrator: curl_cffi transport + Node.js crypto subprocess |
| `demo_node_crypto.js` | WebCrypto: HKDF, AES-GCM, JWE (RSA-OAEP + A128CBC-HS256) |
| `test_curl_cffi_checkout.py` | Testy checkout/build z HAR headers + FF152 fingerprint |
| `spike_ja3_firefox152.py` | Pomiar JA3/JA4/Akamai z Camoufox |
| `spike_curl_cffi_firefox152.py` | Weryfikacja 100% JA3 match |
| `incognia_krypto_reference.js` | HKDF salt, deriveAesKey, aesGcmEncrypt, buildEncryptor |
| `incognia_transport_reference.js` | Transport, Retry, Dispatcher, encodeModel |
| `incognia_sdk_reference.js` | InteractionScheduler, IncogniaSdk, initSdk, collectors |
| `k7v3q2_DEOBFUSCATED.js` | Pełny SDK (91KB) — 15 snapshot + 6 interaction collectors |
| `analyze_har.py` / `analyze_har2-4.py` | Analiza HAR (824 entries) |
| `RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md` | Szczegółowa mapa luk |
| `DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md` | Sekcja 16 (Faza G) + załącznik |

---

## 12. WNIOSKI KOŃCOWE

### ✅ Co SIĘ UDALO (Edukacyjnie Cenne)
1. **curl_cffi + custom FF152 fingerprint** — 100% match JA3/JA4/Akamai z Camoufox
2. **Node.js WebCrypto** — pełna implementacja kryptografii Incognia (HKDF, AES-GCM, JWE)
3. **Cross-verified crypto** — Python `cryptography` ≡ Node.js WebCrypto (identyczne wyniki)
4. **HAR analiza** — kompletny obraz flow: checkout/build → payment → Incognia → DataDome
5. **Podział transport/kryptografia** — czysty, edukacyjny, gotowy do zajęć

### ❌ Co NIE DA SIĘ (Bez Przeglądarki)
1. **DataDome Challenge** — wymaga GPU/audio API (OffscreenCanvas, WebGL, AudioContext, trustToken)
2. **Incognia SDK Runtime** — ładuje się z CDN, wymaga 21 browser API (21 collectors)
3. **`isTrusted=true` Events** — tylko prawdziwe user interactions
4. **`x-incognia-request-token` Generation** — wymaga uruchomionego SDK z sygnałami

### 🎯 Jedyna Sprawdzona Ścieżka Produkcyjna
> **HYBRYDA: Camoufox (warmup + checkout) + curl_cffi (polling)** — zweryfikowana 4/4 pass-rate (Faza 12).

Wszystkie inne podejścia (pełna replikacja w Node.js, replay test z HAR, lekki silnik JS) są **badaniami naukowymi** — cennymi edukacyjnie, ale nie zastępującymi przeglądarki w produkcyjnym flow checkoutu Vinted.

---

## 13. REKOMENDACJA DLA ZAJĘĆ EDUKACYJNYCH

### Moduł 1: TLS Fingerprinting (curl_cffi) — **GOTOWY**
- Pomiar JA3/JA4/Akamai z Camoufox
- Konfiguracja curl_cffi z custom fingerprintem
- Weryfikacja na tls.peet.ws

### Moduł 2: WebCrypto Kryptografia (Node.js) — **GOTOWY**
- HKDF-SHA256 derive key (Incognia pattern)
- AES-256-GCM encrypt/decrypt z AAD
- JWE RSA-OAEP + A128CBC-HS256 (cchd_config format)

### Moduł 3: Browser API Polyfilling (Incognia SDK w Node.js) — **ĆWICZENIE**
- Zadanie: Zaimplementować mock `navigator`, `screen`, `canvas`, `WebGL` w Node.js
- Uruchomić `incognia_sdk_reference.js` w `vm2` / `isolated-vm`
- Zobaczyć które collectory działają, które crashują

### Moduł 4: DataDome Challenge Analysis — **CASE STUDY**
- Analiza kodu DataDome 5.9.2
- Dlaczego to "hard problem" dla headless/automation
- TrustToken API — Chrome-only, Privacy Pass

### Moduł 5: Hybrydowa Architektura — **ARCHITEKTURA REFERENCYJNA**
- curl_cffi do polling/szybkich requestów
- Camoufox do checkout/warmup (jedyny punkt wymagający browser)
- Token harvesting / replay test methodology

---

*Koniec raportu inżynierskiego.*