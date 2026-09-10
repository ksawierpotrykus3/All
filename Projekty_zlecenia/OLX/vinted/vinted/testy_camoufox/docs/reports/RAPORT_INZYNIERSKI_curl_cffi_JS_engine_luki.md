# RAPORT INŻYNIERSKI: Luka architektoniczna curl_cffi + lekki silnik JS vs Pełna Przeglądarka

**Data:** 2026-08-30  
**Kontekst:** Badanie edukacyjne — co brakuje by zreplikować pełny flow Vinted (warmup → Incognia → DataDome → checkout/build) bez pełnej przeglądarki  
**Status:** Analiza luk na podstawie deobfuskacji SDK Incognia (sekcja 14), pomiarów fingerprintu (Faza G), i kodu DataDome 5.9.2

---

## 1. PEŁNY FLOW FRONTENDU (co robi prawdziwa przeglądarka)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRZEGLĄDARKA (Camoufox/Firefox 152)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. TLS HANDSHAKE (ClientHello)                                            │
│     ├── JA3/JA4/Akamai fingerprint Firefox 152                             │
│     ├── Extensions: delegated_cred(34), record_size_limit(28), cert_comp(zstd)│
│     └── HTTP/2 settings + priority frames                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  2. WARMUP (nawigacja do item page)                                        │
│     ├── GET /items/{id} → HTML + __CONFIG__ (Incognia API key, DD key)     │
│     ├── Cookies: session, datadome, _vinted_fr_session                     │
│     ├── DataDome JS 5.9.2 ładuje się z static-assets.vinted.com            │
│     └── DataDome challenge: OffscreenCanvas, WebGL, AudioContext, trustToken│
├─────────────────────────────────────────────────────────────────────────────┤
│  3. INCOGNIA SDK INIT (dynamiczne ładowanie przy kliknięciu "Kup")         │
│     ├── window.__V.initSdk({ apiBaseUrl, sdkInstanceId, loaderTimings })   │
│     ├── Ładuje SDK z CDN *.incognia.com (k7v3q2.vinted.com/85d7e768568e.js)│
│     ├── Generuje sdkInstanceId (UUID v4) — tożsamość sesji                  │
│     ├── Snapshot phase (pls): device fingerprint, WebGL, canvas, audio,    │
│     │   fonts, permissions, storage, screen, navigator, WebGPU, media caps │
│     ├── Interaction phase (it): mouse, keyboard, scroll, pointer, visibility│
│     │   → flush co 5s / 50 eventów / visibilitychange                       │
│     ├── Kryptografia: HKDF-SHA256(salt="L6ZhSbP9TciQDgxC7pjukGhl4vYis56m",│
│     │   ikm=sdkInstanceId) → AES-256-GCM key                                │
│     ├── Payload: JSON signals → encrypt(AES-GCM) → base64(IV||ct)          │
│     ├── POST /v1/consume (credentials:include, keepalive) z retry/backoff  │
│     └── WebSocket: token JWE (RSA-OAEP + A128CBC-HS256) → binary frames    │
├─────────────────────────────────────────────────────────────────────────────┤
│  4. CHECKOUT BUILD                                                         │
│     ├── POST /api/v2/checkout/build (isTrusted click, cookies, tokens)     │
│     ├── Nagłówki: x-incognia-request-token (AES-GCM z HKDF key)            │
│     ├── DataDome cookie + x-datadome-clientid                              │
│     └── Response: reservation_id, payment_intent, itd.                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MAPA PODZIAŁU: curl_cffi vs Node.js WebCrypto vs Browser API

| Komponent | curl_cffi (Python) | Node.js WebCrypto | **Wymaga Browser API** |
|-----------|-------------------|-------------------|------------------------|
| **TLS ClientHello** | ✅ JA3/JA4/Akamai FF152 | — | — |
| **HTTP/2 frames** | ✅ settings, priority | — | — |
| **TLS Extensions** | ✅ 34, 28, cert_comp zstd | — | — |
| **Nagłówki HTTP** | ✅ UA, Sec-Fetch-*, cookies | — | — |
| **Cookie jar** | ✅ manual management | — | — |
| **HKDF-SHA256** | — | ✅ RFC 5869 | — |
| **AES-256-GCM** | — | ✅ RFC 5116 | — |
| **RSA-OAEP** | — | ✅ RFC 8017 | — |
| **JWE (A128CBC-HS256)** | — | ✅ RFC 7516 | — |
| **OffscreenCanvas** | ❌ | ❌ | ✅ **DataDome** |
| **WebGL / WEBGL_debug_renderer_info** | ❌ | ❌ | ✅ **DataDome + Incognia** |
| **AudioContext / OfflineAudioContext** | ❌ | ❌ | ✅ **DataDome + Incognia** |
| **trustToken API** | ❌ | ❌ | ✅ **DataDome (Chrome-only)** |
| **performance.now()** | ❌ | ❌ (Date.now approx) | ✅ **Incognia timing** |
| **visibilitychange / document.hidden** | ❌ | ❌ | ✅ **Incognia scheduler** |
| **PointerEvent / MouseEvent / KeyboardEvent** | ❌ | ❌ | ✅ **Incognia behavioral** |
| **navigator APIs** | ❌ | ❌ | ✅ **Incognia device fingerprint** |
| **WebGLRenderingContext.getParameter** | ❌ | ❌ | ✅ **Incognia WebGL fingerprint** |
| **HTMLCanvasElement.toDataURL** | ❌ | ❌ | ✅ **Incognia canvas fingerprint** |
| **Font detection (offsetWidth trick)** | ❌ | ❌ | ✅ **Incognia font enum** |
| **navigator.permissions.query** | ❌ | ❌ | ✅ **Incognia permissions** |
| **navigator.storage.estimate** | ❌ | ❌ | ✅ **Incognia storage** |
| **indexedDB** | ❌ | ❌ | ✅ **Incognia IDB** |
| **matchMedia (pointer/hover)** | ❌ | ❌ | ✅ **Incognia media caps** |
| **WebGPU (navigator.gpu)** | ❌ | ❌ | ✅ **Incognia WebGPU** |
| **MediaCapabilities / canPlayType** | ❌ | ❌ | ✅ **Incognia media** |
| **Screen / visualViewport** | ❌ | ❌ | ✅ **Incognia screen** |
| **WebSocket (binary frames)** | ❌ (ws library OK) | ❌ | ✅ **Incognia WS transport** |
| **isTrusted event property** | ❌ | ❌ | ✅ **Critical: checkout click** |

---

## 3. SZCZEGÓŁOWA ANALIZA LUK

### 3.1 DataDome Challenge (static-assets.vinted.com/datadome_5.9.2)

Z sekcji 13.5 i deobfuskacji DataDome 5.9.2:

```javascript
// DataDome używa (wykryte w kodzie):
- OffscreenCanvas                    // Canvas fingerprint bez DOM
- WEBGL_debug_renderer_info          // Unmasked vendor/renderer (WebGL ext)
- trustToken (window.trustToken)     // Chrome-only Privacy Pass API
- setAudioFingerprintSeed            // AudioContext fingerprint
- AudioContext / OfflineAudioContext // Audio fingerprint (sum, sampleRate)
- performance.now()                  // High-res timing
- navigator.webdriver detection      // Bot detection
- __webdriver_evaluate, __selenium_* // Automation detection (38+ checks)
```

**Wniosek:** DataDome challenge **nie da się zreplikować bez przeglądarki**. To zbiór API które:
- Nie istnieją w Node.js (OffscreenCanvas, WebGL, AudioContext)
- Wymagają GPU/hardware (WebGL renderer, audio hardware fingerprint)
- Są celowo zaprojektowane do wykrywania headless/automation

### 3.2 Incognia SDK — Sygnały (Snapshot + Interaction Collectors)

Z `k7v3q2_DEOBFUSCATED.js` (sekcja 14, plik 91KB deobfuskowany):

#### SNAPSHOT COLLECTORS (uruchamiane raz przy `init()`):
| Collector | Sygnały | Browser API |
|-----------|---------|-------------|
| `ra` (Canvas) | SHA-256(canvas PNG), alphaNonzeroRatio | `canvas.toDataURL`, `getImageData` |
| `Gs` (Screen) | inner/outer width/height, devicePixelRatio, visualViewport, orientation, pointer/hover media queries | `window.screen`, `visualViewport`, `matchMedia` |
| `sa` (User-Agent Data) | brands, mobile, platform, highEntropy (uaFullVersion, platformVersion, model, architecture, bitness, wow64) | `navigator.userAgentData.getHighEntropyValues()` |
| `fa` (Keyboard - false timing) | Fixed 0, timing | — (placeholder) |
| `da` (Keyboard - true timing) | seed-based random + timing delay | `performance.now()`, `crypto.subtle.digest` |
| `ra` (WebGL) | vendor, renderer, version, shadingLanguageVersion, **unmaskedVendor/Renderer**, extensionsHash, paramsHash, **renderHash** (triangle shader) | `WebGLRenderingContext`, `WEBGL_debug_renderer_info` |
| `ha` (Permissions) | geolocation, notifications, camera, microphone, persistent-storage | `navigator.permissions.query()` |
| `nc` (Storage) | cookie (SameSite=Strict), localStorage, indexedDB, quota, usage, persisted | `document.cookie`, `localStorage`, `indexedDB`, `navigator.storage.estimate()`, `navigator.storage.persisted()` |
| `Cc` (WebGL - official) | Tożsame co `ra` ale przez oficjalny T() wrapper | WebGL |
| `wc` (Media) | audio/video canPlayType, MSE support | `HTMLAudioElement.canPlayType`, `MediaSource.isTypeSupported` |
| `ma` (Navigator) | screen, platform, language, languages, cookieEnabled, hardwareConcurrency, maxTouchPoints, deviceMemory, connection (effectiveType, rtt, downlink, saveData) | `navigator.*` |
| `Bs` (Timezone) | timeZone, timezoneOffset, clockDeltaMs (performance.timeOrigin vs Date.now) | `Intl.DateTimeFormat().resolvedOptions()`, `performance.timeOrigin` |
| `Ws` (Audio/Video codecs) | canPlayType dla 14 audio + 9 video codecs, MSE | `canPlayType`, `MediaSource` |
| `Gs` (Navigator features) | serviceWorker, WebAssembly, WebGL1/2, WebRTC, SharedArrayBuffer, crossOriginIsolated, getUserMedia, WebGPU, AudioContext, OfflineAudioContext, Notification, Geolocation | `navigator.*`, `globalThis.*` |
| `Ys` (Fonts) | 125 fontów — offsetWidth trick (span 72px, porównanie szerokości) | `document.createElement`, `offsetWidth`, `fontFamily` |
| `zs` (Loader timings) | configMs, scriptMs | `loaderTimings` passed from Vinted wrapper |
| `Hr` (Audio fingerprint) | OfflineAudioContext: oscillator → dynamicsCompressor → sum, sampleRate, channels | `OfflineAudioContext`, `createOscillator`, `createDynamicsCompressor` |

#### INTERACTION COLLECTORS (ciągłe, flush co 5s/50 eventów):
| Collector | Sygnały | Trigger |
|-----------|---------|---------|
| `ar` (Clock) | visibleMs, focusedMs | `visibilitychange`, `focus`/`blur` |
| `Cr` (Mouse hover) | overCount, outCount, dwellMsP50/P95 | `mouseover`/`mouseout` |
| `_r` (Keyboard) | keydown/keyup count, interKeyMsP50/P95, pasteCount, pasteMaxLenBucket | `keydown`/`keyup`/`paste` + `isTrusted` |
| `lr` (Pointer) | move/down/up/click count, pointerType (mouse/pen/touch), timeToFirstPointerMs, movePauseMsP50/P95 | `pointermove`/`down`/`up`/`click` |
| `Or` (Scroll) | scrollCount, maxDepthBucket, speedP50/P95 | `scroll` + `requestAnimationFrame` |

**Kluczowe:** Wszystkie interaction collectors **wymagają `isTrusted` property** na eventach. To **nie da się sfałszować bez przeglądarki** — `isTrusted=true` tylko dla prawdziwych user events.

### 3.3 Kryptografia Incognia (już zaimplementowana w Node.js WebCrypto)

```javascript
// ✅ WSZYSTKO DZIAŁA W NODE.JS (WebCrypto API)
HKDF_SALT = "L6ZhSbP9TciQDgxC7pjukGhl4vYis56m" (32B stała)
deriveAesKey(sdkInstanceId) → HKDF-SHA256(salt, ikm=sdkInstanceId) → AES-256-GCM key
aesGcmEncrypt(key, plaintext) → IV(12B) || ciphertext || tag(16B)
buildEncryptor(sdkInstanceId) → fn(plaintext) → Uint8Array(IV||ct)

// Transport:
POST /v1/consume {
  v: 1,
  type: "pls" | "it",
  siid: sdkInstanceId,
  ts: timestamp,
  t: totalTimingMs,
  tr: trigger (dla "it"),
  s: base64(IV || ciphertext)  // AES-GCM output
}
credentials: include, keepalive: true, retry 3x z exponential backoff
```

**Status:** ✅ Zaimplementowane i zweryfikowane cross-verified (Node.js ≡ Python `cryptography`) w Faza G.

### 3.4 WebSocket Transport (Incognia real-time)

Z HAR i sekcji 15.6:
- Endpoint: `wss://*.incognia.com/...` (dynamiczny z konfiguracji)
- Handshake: JWE token (RSA-OAEP + A128CBC-HS256) z `cchd_config`
- Frames: **binary** (Opera DevTools nie loguje treści)
- Protokoł: Własny, prawdopodobnie protobuf/MessagePack

**Luka:** Nie znamy formatu ramek binary. Bez tego nie ma pełnego duplexu z serwerem Incognia.

### 3.5 `x-incognia-request-token` (Checkout header)

Z sekcji 14.4 i kodu Vinted wrappera:
- Generowany przez SDK po `init()` i snapshot phase
- To **AES-GCM ciphertext** z kluczem z HKDF(sdkInstanceId)
- Payload: device fingerprint + behavioral signals (compressed)
- **Wymaga:** Uruchomionego SDK w przeglądarce (collectors + timing)

---

## 4. MINIMALNY ZESTAW DO REPLIKACJI (Co trzeba zbudować)

### 4.1 Co MAMY (Faza G — UDOWODNIONE)

```
✅ curl_cffi + custom JA3/JA4/Akamai/extra_fp (Firefox 152 fingerprint)
✅ HTTP/2 + cookie management
✅ Node.js WebCrypto: HKDF, AES-GCM, RSA-OAEP, JWE (A128CBC-HS256)
✅ Cross-verified Python ≡ Node.js crypto
```

### 4.2 Co BRAKUJE (Luki do zaplnienia)

| Luka | Rozwiązanie | Trudność | Czy da się bez przeglądarki? |
|------|-------------|----------|------------------------------|
| **DataDome challenge** | Pełna emulacja OffscreenCanvas + WebGL + AudioContext + trustToken | **BARDZO TRUDNA** | ❌ **NIE** — wymaga GPU/audio hardware |
| **Incognia SDK loading** | Fetch SDK z CDN, eval w JS engine | Średnia | ⚠️ Tak, ale SDK wywołuje browser API |
| **Device fingerprint (snapshot)** | Zaimplementować 15+ collectorów w JS engine | Trudna | ⚠️ Częściowo (bez WebGL/canvas/audio) |
| **Behavioral signals (interaction)** | Event loop symulujący ruchy myszy, klawiatura, scroll | Średnia | ⚠️ Tak (symulacja), ale bez `isTrusted` |
| **`isTrusted=true` events** | **NIEMOŻLIWE** bez prawdziwej przeglądarki | **NIEMOŻLIWE** | ❌ **NIE** |
| **WebSocket binary frames** | Reverse engineering protokołu | Trudna | ✅ Tak (gdy znamy format) |
| **`x-incognia-request-token`** | Generować po snapshot phase (wymaga sygnałów) | Średnia | ⚠️ Tak (gdy mamy sygnały) |

---

## 5. ARCHITEKTURA "LEKKI SILNIK JS" — Co musi zawierać

Jeśli chcemy **maksymalnie zbliżyć się do przeglądarki** bez jej używania:

```
┌────────────────────────────────────────────────────────────────────┐
│                    LEKKI SILNIK JS (Node.js + polyfills)          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. WEB POLYFILLS (minimalne)                                      │
│     ├── window / document / navigator (mock objects)              │
│     ├── performance.now() → high-res timer                        │
│     ├── crypto.subtle (WebCrypto) — NATYWNE w Node 18+           │
│     ├── crypto.getRandomValues — NATYWNE                          │
│     ├── fetch / WebSocket (ws library)                            │
│     ├── setTimeout / setInterval / clearInterval                  │
│     ├── TextEncoder / TextDecoder                                 │
│     ├── btoa / atob / base64url                                   │
│     └── console.log / Error / Promise                             │
│                                                                    │
│  2. BROWSER API POLYFILLS (do Incognia SDK)                       │
│     ├── document.createElement('canvas') → mock canvas            │
│     │   ├── getContext('2d') → mock 2D context                   │
│     │   ├── toDataURL() → synthetic PNG (deterministic)          │
│     │   └── getImageData() → synthetic pixel data                │
│     ├── document.createElement('span') → font detection          │
│     │   └── offsetWidth → deterministic per font                 │
│     ├── navigator.* → mock object z realistycznymi wartościami   │
│     │   ├── userAgentData.getHighEntropyValues() → mock brands   │
│     │   ├── permissions.query() → mock granted/denied            │
│     │   ├── storage.estimate() → mock quota/usage                │
│     │   ├── mediaDevices, gpu, connection, maxTouchPoints...     │
│     │   └── hardwareConcurrency, deviceMemory, platform...       │
│     ├── screen / visualViewport → mock dimensions                │
│     ├── matchMedia → mock MediaQueryList                         │
│     ├── WebGLRenderingContext → mock getParameter, extensions    │
│     │   └── WEBGL_debug_renderer_info → unmasked vendor/renderer│
│     ├── AudioContext / OfflineAudioContext → mock sum/sampleRate │
│     │   └── createOscillator, createDynamicsCompressor           │
│     ├── performance.timeOrigin → mock timestamp                  │
│     ├── indexedDB → mock (or use fake-indexeddb)                 │
│     └── localStorage / sessionStorage / cookies → in-memory      │
│                                                                    │
│  3. INCOGNIA SDK RUNTIME                                          │
│     ├── Fetch SDK z CDN (k7v3q2.vinted.com/85d7e768568e.js)      │
│     ├── eval() w sandboxie (vm2 lub isolated-vm)                 │
│     ├── window.__V.initSdk({...}) → inicjalizacja                │
│     ├── Snapshot phase: wywołanie 15 collectorów                 │
│     ├── Interaction phase: uruchomienie schedulerów              │
│     ├── HKDF/AES-GCM (używa natywnego WebCrypto — SZYBKIE)       │
│     └── Dispatcher → POST /v1/consume (fetch z credentials)      │
│                                                                    │
│  4. DATA DOME CHALLENGE — LUKA NIEROZWIĄZYWALNA                   │
│     ├── OffscreenCanvas → **NIEMOŻLIWE** bez GPU/Canvas API      │
│     ├── WebGL fingerprint → **NIEMOŻLIWE** bez WebGL context     │
│     ├── Audio fingerprint → **NIEMOŻLIWE** bez AudioContext      │
│     ├── trustToken → **TYLKO CHROME**, nie działa w Node/Firefox │
│     └── Rozwiązanie: TYLKO prawdziwa przeglądarka (Camoufox)     │
│                                                                    │
│  5. WEBSOCKET TRANSPORT                                           │
│     ├── ws library (WebSocket client)                            │
│     ├── JWE handshake (RSA-OAEP + A128CBC-HS256) — MAMY         │
│     └── Binary frames parser (reverse engineering)               │
│                                                                    │
│  6. CHECKOUT BUILD                                                │
│     ├── curl_cffi POST /checkout/build                           │
│     ├── Headers: x-incognia-request-token (z SDK),               │
│     │   x-datadome-clientid, cookies                             │
│     └── isTrusted click → **NIE DA SIĘ ZROBIĆ BEZ PRZEGLĄDARKI** │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 6. REALISTYCZNE SCENARIUSZE

### Scenariusz A: "Pełna replikacja w JS engine" (BADANIE NAUKOWE)
```
Cel: Uruchomić INCÓGNIĘ SDK w Node.js z polyfillami browser API
Wynik: SDK startuje, robi snapshot, generuje tokeny, POST /v1/consume
Problem: DataDome challenge NIE PRZEJDZIE (brak WebGL/Canvas/Audio)
         isTrusted click NIE ZADZIAŁA (symulowane eventy = isTrusted=false)
         Server-side validation: UNKNOWN (sekcja 14.9: 0% UDOWODNIONE)
Czas: 2-4 tygodnie inżynierii polyfilli
Wartość edukacyjna: BARDZO WYSOKA (rozumienie fingerprintingu)
```

### Scenariusz B: "Hybryda: curl_cffi + Camoufox headless dla DataDome" (PRAGMATYCZNE)
```
Architektura:
1. Camoufox (headless, persistent context) → TYLKO warmup + DataDome challenge
   - Otwiera item page, klika "Kup" (isTrusted click)
   - DataDome challenge solved w przeglądarce
   - Incognia SDK inicjalizuje się, generuje x-incognia-request-token
   - Przechwyć: cookies, x-incognia-request-token, x-datadome-clientid
   
2. curl_cffi (FF152 fingerprint) → checkout/build + polling
   - Używa przechwyconych tokenów/cookies
   - Szybsze (247ms vs 719ms), bez DataDome/Incognia overhead
   - Polling /api/v2/catalog/items bez blokad

To JEST strategia z Fazy 12 (zweryfikowana 4/4 rezerwacje).
```

### Scenariusz C: "Replay test z HAR" (NAJNIEBEZPIECZNIEJSZY TEST)
```
1. Camoufox robi pełną rezerwację (zapis HAR + WebSocket frames)
2. Wyciągnij: cookies, x-incognia-request-token, x-datadome-clientid, 
   reservation_id, WebSocket handshake JWE
3. curl_cffi + Node.js replay POST /checkout/build z wyciągniętymi danymi
4. Sprawdź czy serwer przyjmuje "stare" tokeny (tokeny mają TTL?)

Ryzyko: Tokeny Incognia są jednorazowe (timestamp + session ID)
        DataDome cookie ma lifetime
        Server-side validation może odrzucić replay
Czas: 1-2h (Faza 8 roadmapy)
```

---

## 7. DECYZJA INŻYNIERSKA

### Dlaczego Faza B wnioskowała "SILNIK JS NIEWYKONALNY" (sekcja 13.7):

1. **DataDome używa API których nie ma w Node.js** — OffscreenCanvas, WebGL, AudioContext, trustToken
2. **Incognia SDK ładuje się z zewnętrznego CDN** — nie jest w bundle Vinted
3. **Behavioral signals wymagają `isTrusted=true`** — tylko prawdziwe eventy przeglądarki
4. **Server-side validation niezbadana** — 0% UDOWODNIONE (sekcja 14.9)

### Co zmieniła Faza F + G:

- ✅ **Kryptografia Incognia jest czysta i przenośna** (HKDF, AES-GCM, JWE działają w Node.js)
- ✅ **curl_cffi potrafi zmatchować Firefox 152 fingerprint** (własny JA3/Akamai/extra_fp)
- ✅ **Podział transport/kryptografia jest czysty i edukacyjny**

### Co NIE zmieniło się:

- ❌ **DataDome challenge** — wciąż blokuje bez przeglądarki
- ❌ **Incognia SDK wymaga browser environment** — 15+ collectorów używają DOM/API
- ❌ **isTrusted click** — kritczny dla checkout/build
- ❌ **WebSocket binary protocol** — nieznany

---

## 8. REKOMENDACJA DLA ZAJĘĆ EDUKACYJNYCH

### Moduł 1: TLS Fingerprinting (curl_cffi) — **GOTOWE**
- Pomiar JA3/JA4/Akamai z prawdziwej przeglądarki
- Konfiguracja curl_cffi z custom fingerprintem
- Weryfikacja na tls.peet.ws

### Moduł 2: WebCrypto Kryptografia (Node.js) — **GOTOWE**
- HKDF-SHA256 derive key (Incognia pattern)
- AES-256-GCM encrypt/decrypt z AAD
- JWE RSA-OAEP + A128CBC-HS256 (cchd_config format)
- Cross-verification Python ≡ Node.js

### Moduł 3: Browser API Polyfilling (Incognia SDK w Node.js) — **ĆWICZENIE DLA STUDENTÓW**
- Zadanie: Zaimplementować mock `navigator`, `screen`, `canvas`, `WebGL` w Node.js
- Uruchomić `incognia_sdk_reference.js` w `vm2` / `isolated-vm`
- Zobaczyć które collectory działają, które crashują

### Moduł 4: DataDome Challenge Analysis — **CASE STUDY**
- Analiza kodu DataDome 5.9.2 (OffscreenCanvas, WebGL, AudioContext)
- Dlaczego to "hard problem" dla headless/automation
- TrustToken API — Chrome-only, Privacy Pass

### Moduł 5: Hybrydowa architektura produkcyjna — **ARCHITEKTURA REFERENCYJNA**
- curl_cffi do polling/szybkich requestów
- Camoufox do checkout/warmup (jedynie punkt wymagający browser)
- Token harvesting / replay test methodology

---

## 9. PLIKI REFERENCYJNE W PROJEKCIE

| Plik | Rola |
|------|------|
| `demo_curl_cffi_js_hkdf.py` | Orkiestrator: curl_cffi transport + Node.js crypto subprocess |
| `demo_node_crypto.js` | WebCrypto: HKDF, AES-GCM, JWE (RSA-OAEP + A128CBC-HS256) |
| `incognia_krypto_reference.js` | HKDF salt, deriveAesKey, aesGcmEncrypt, buildEncryptor |
| `incognia_transport_reference.js` | Transport, Retry, Dispatcher, encodeModel |
| `incognia_sdk_reference.js` | InteractionScheduler, IncogniaSdk, initSdk, collectors (placeholdery) |
| `k7v3q2_DEOBFUSCATED.js` | Pełny deobfuskowany SDK (91KB) — 15 snapshot + 6 interaction collectors |
| `spike_ja3_firefox152.py` | Pomiar fingerprintu Firefox 152 z Camoufox |
| `spike_curl_cffi_firefox152.py` | Weryfikacja 100% JA3 match curl_cffi |
| `wynik_ja3_firefox152.json` | Surowy fingerprint FF152 |
| `wynik_curl_cffi_firefox152.json` | Potwierdzenie match |
| `DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md` | Sekcja 16 (Faza G) — pełna dokumentacja wektora edukacyjnego |

---

## 10. PODSUMOWANIE: Co curl_cffi + JS Engine POTRAFI vs Co NIE

| ✅ **POTRAFI (z Faza G)** | ❌ **NIE POTRAFI (wymaga przeglądarki)** |
|---------------------------|------------------------------------------|
| TLS fingerprint Firefox 152 (JA3/JA4/Akamai) | DataDome challenge (OffscreenCanvas, WebGL, AudioContext, trustToken) |
| HTTP/2 + cookie management | Incognia SDK loading z CDN (wymaga window/document/navigator) |
| HKDF-SHA256, AES-GCM, RSA-OAEP, JWE | Device fingerprint collectors (canvas, WebGL, audio, fonts, permissions...) |
| Cross-verified crypto (Python ≡ Node.js) | Behavioral signals z `isTrusted=true` (mouse, keyboard, scroll, pointer) |
| POST /v1/consume z retry/backoff | WebSocket binary frames (protokół nieznany) |
| Parsowanie JWE z cchd_config | `x-incognia-request-token` generation (wymaga SDK runtime) |
| | `isTrusted` click na "Kup teraz" (critical dla checkout/build) |

---

## 11. WNIOSK KOŃCOWY

**curl_cffi + lekki silnik JS (Node.js WebCrypto) potrafi zreplikować:**
- Warstwę transportową (TLS, HTTP/2, fingerprint)
- Warstwę kryptograficzną Incognia (HKDF, AES-GCM, JWE)

**ALE NIE POTRAFI zreplikować:**
- DataDome challenge (wymaga browser GPU/audio API)
- Incognia SDK runtime (wymaga 20+ browser API)
- `isTrusted` user interactions
- Server-side validation (niezbadana)

**Jedyna sprawdzona ścieżka do `POST /checkout/build` na produkcji Vinted:**
> **Hybryda: Camoufox (warmup + checkout) + curl_cffi (polling)** — zweryfikowana 4/4 pass-rate (Faza 12).

Wszystko inne to **badanie naukowe** — cenne edukacyjnie, ale nie zastępujące przeglądarki w produkcyjnym flow checkoutu.

---

*Koniec raportu inżynierskiego.*