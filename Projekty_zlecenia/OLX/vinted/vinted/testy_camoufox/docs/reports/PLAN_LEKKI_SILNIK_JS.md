# PLAN: Lekki silnik JS asystujący curl_cffi (DataDome + Incognia bypass)

**Cel:** Zbudować silnik JS (Node.js) który:
1. Uruchamia DataDome SDK w Node (lub symuluje jego output)
2. Generuje prawidłowe Incognia WebSocket + HTTP flow
3. Dostarcza curl_cffi gotowe tokeny/nagłówki/cookies

---

## 1. ANALIZA NETWORK REQUESTS Z PLAYWRIGHT (co robí przeglądarka)

### 1.1 DataDome Flow (z HAR + Playwright network logs)

```
GET /items/9807925466... (HTML load)
  ↓
DataDome SDK loads from: https://dd.vinted.lt/js (or static CDN)
  ↓
POST https://dd.vinted.lt/js  (beacon z fingerprintem)
  → Body: { "event": "page_view", "fingerprint": {...}, "cid": "..." }
  ↓
SET-COOKIE: datadome=... (via JS document.cookie)
  ↓
localStorage: DataDome tokens (ddv, ddc, etc.)
  ↓
Każdy request ma nagłówek: x-datadome-clientid: <cid>
```

**Kluczowe obserwacje z Playwright:**
- DataDome SDK 5.9.2 = 116 KB obfuskowany JS
- Fingerprint: canvas, WebGL, fonts, audio, navigator, screen, permissions
- Behavioral: mouse moves, clicks, scroll, focus/blur, key presses
- Challenge: slider CAPTCHA lub invisible challenge
- Cookie `datadome` odświeżana co ~30s przez beacon

### 1.2 Incognia Flow (z HAR + deobfuskacja)

```
Incognia SDK loads from: https://k7v3q2.vinted.com/85d7e768568e.js
  ↓
POST https://conn-check.icg-in.com/connectioncheck
  → Response: { "public_key": "...", "session_token": "..." }
  ↓
GET https://conn-check.icg-in.info/netconn
  → Header: ICG-Connection-Token: <JWE>
  ↓
WS Upgrade: wss://conn-check.icg-in.info/wsconn?token=<JWE>
  → Binary frames (protobuf?)
  ↓
HKDF(sdkInstanceId) → AES-256-GCM key
  ↓
POST /j3r4zw/v1/consume (type="pls" snapshot)
  → 111 signals zaszyfrowane AES-GCM
  ↓
Co 5s: POST /j3r4zw/v1/consume (type="it" interactions)
```

### 1.3 Checkout Flow (z HAR)

```
POST /api/v2/purchases/checkout/build
  → { purchase_items: [{id: 21872241924, type: "transaction"}] }
  ↓
PUT /api/v2/purchases/{id}/checkout (5 kroków)
  ↓
POST /api/v2/purchases/{id}/checkout/payment
  → Headers: x-incognia-request-token: <JWE>
  → Body: { checksum, payment_options: { browser_info: {...} } }
  ↓
Redirect do Adyen 3D Secure
```

---

## 2. ARCHITEKTURA LEKKIEGO SILNIKA JS

```
┌─────────────────────────────────────────────────────────────┐
│                    LIGHTWEIGHT JS ENGINE                    │
│  (Node.js 18+, uruchamiany jako child_process lub HTTP API) │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  DATADOME     │    │  INCOGNIA     │    │  CHECKOUT     │
│  MODULE       │    │  MODULE       │    │  HELPER       │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
- Fingerprint gen    - HKDF + AES-GCM      - Payload builder
- Behavioral sim     - WS connection       - Checksum calc
- Cookie/token gen   - Consume loop        - Header builder
- Challenge solver   - Token refresh       - Cookie sync
```

---

## 3. IMPLEMENTACJA MODUŁÓW

### 3.1 DataDome Module (`datadome_engine.js`)

**Opcja A: Pełne SDK w Node (trudne)**
```javascript
// Wymaga: canvas, webgl, audio, trustToken polyfills
// npm: canvas, gl, web-audio-api, jsdom
// Problem: 116 KB obfuskowanego kodu, anti-debug, weekly updates
```

**Opcja B: Fingerprint Generator + Behavioral Simulator (zalecane)**
```javascript
// Generuje fingerprint IDENTYCZNY przeglądarce (z HAR)
// Symuluje behavioral signals (mouse, keyboard, scroll)
// Generuje cookie `datadome` i `x-datadome-clientid`
// Rozwiązuje challenge (jeśli invisible) lub zwraca do curl_cffi do rozwiązania
```

**API:**
```javascript
const datadome = require('./datadome_engine');

// Inicjalizacja z fingerprintem z HAR
const ctx = datadome.init({
  userAgent: "Mozilla/5.0...",
  screen: {width: 1920, height: 1080},
  timezone: -120,
  language: "pl",
  // ... 50+ parametrów fingerprintu
});

// Generuj cookie i headers na każdy request
const { cookie, headers } = datadome.getRequestContext(url, method);

// Symuluj interakcje (wywoływane przez curl_cffi przed requestem)
datadome.simulateMouseMove(x, y, duration);
datadome.simulateClick(x, y);
datadome.simulateScroll(deltaY);
datadome.simulateKeyPress(key);

// Rozwiąż challenge (jeśli potrzebne)
const solution = await datadome.solveChallenge(challengeData);
```

### 3.2 Incognia Module (`incognia_engine.js` - już gotowe!)

**Co mamy (z F6a/F9):**
- ✅ HKDF-SHA256 + AES-256-GCM
- ✅ 17 snapshot collectors (111 signals)
- ✅ 7 interaction collectors
- ✅ HTTP /v1/consume payload generator
- ✅ Full SDK lifecycle

**Co brakuje:**
- ❌ WebSocket connection (JWE handshake + binary frames)
- ❌ Connectioncheck flow (POST/GET/WS)
- ❌ RSA-OAEP key unwrap (dla JWE token)

**Do dorobienia:**
```javascript
const incognia = require('./incognia_engine');

// Pełny flow z WebSocket
await incognia.initFull({
  apiBaseUrl: "https://api.vinted.pl/j3r4zw",
  sdkInstanceId: "...", // z DataDome lub wygenerowany
});

// Auto-manage consume loop
incognia.on('consume', (payload) => {
  // curl_cffi wysyła ten payload
});

// Generuj x-incognia-request-token dla payment
const token = incognia.generateRequestToken();
```

### 3.3 Checkout Helper (`checkout_helper.js`)

```javascript
const checkout = require('./checkout_helper');

// Buduj payload dla /checkout/build
const buildPayload = checkout.buildCheckoutPayload({
  itemId: 9807925466,
  quantity: 1,
  fingerprint: datadome.getFingerprint(),
  incognia: incognia.getState(),
});

// Buduj kroki PUT /checkout
const steps = checkout.generateCheckoutSteps(purchaseId);

// Generuj x-incognia-request-token dla payment
const paymentToken = checkout.generatePaymentToken({
  checksum: "...",
  incogniaToken: incognia.generateRequestToken(),
});
```

---

## 4. INTEGRACJA Z CURL_CFFI (Python)

```python
# hybrid_client.py
import subprocess
import json
from curl_cffi import requests

class HybridClient:
    def __init__(self):
        self.js_engine = subprocess.Popen(
            ['node', 'engine_server.js'],  # HTTP API na porcie 3000
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.session = requests.Session()
    
    def call_js(self, module, method, args):
        """Wywołaj metodę w silniku JS przez HTTP"""
        resp = requests.post(
            'http://localhost:3000/call',
            json={'module': module, 'method': method, 'args': args}
        )
        return resp.json()
    
    def checkout_item(self, item_id):
        # 1. DataDome: init fingerprint
        dd_ctx = self.call_js('datadome', 'init', {item_id, ...})
        
        # 2. Incognia: init full flow
        ic_ctx = self.call_js('incognia', 'initFull', {...})
        
        # 3. GET item page (curl_cffi z cookies z JS)
        self.session.cookies.update(dd_ctx['cookies'])
        self.session.headers.update(dd_ctx['headers'])
        
        # 4. Symuluj behavioral przed kliknięciem
        self.call_js('datadome', 'simulateMouseMove', [100, 200, 500])
        self.call_js('datadome', 'simulateClick', [100, 200])
        
        # 5. POST /checkout/build
        build_payload = self.call_js('checkout', 'buildCheckoutPayload', {...})
        resp = self.session.post(
            'https://www.vinted.pl/api/v2/purchases/checkout/build',
            json=build_payload,
            impersonate='chrome146'
        )
        
        # 6. Reszta flow...
```

---

## 5. ROADMAP IMPLEMENTACJI

| Faza | Zadanie | Czas | Priorytet |
|------|---------|------|-----------|
| **1** | DataDome Fingerprint Generator (z HAR) | 2 dni | 🔴 CRITICAL |
| **2** | DataDome Behavioral Simulator | 3 dni | 🔴 CRITICAL |
| **3** | DataDome Cookie/Token Generator | 1 dzień | 🔴 CRITICAL |
| **4** | Incognia WebSocket + Connectioncheck | 2 dni | 🟡 HIGH |
| **5** | Incognia JWE token generation | 1 dzień | 🟡 HIGH |
| **6** | HTTP API Server (Express/Fastify) | 1 dzień | 🟢 MEDIUM |
| **7** | Python HybridClient wrapper | 1 dzień | 🟢 MEDIUM |
| **8** | Challenge Solver (invisible/slider) | 5-10 dni | 🟡 HIGH |
| **9** | Integracja + testy E2E | 3 dni | 🔴 CRITICAL |

**SZACUNEK: 18-25 dni** (vs 6-10 tygodni dla pełnego DataDome SDK w Node)

---

## 6. KLUCZOWE DANE Z HAR DO HARDCODOWANIA

### DataDome Fingerprint (wyciągnięte z HAR/Playwright)
```javascript
const HAR_FINGERPRINT = {
  // Navigator
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
  platform: "Win32",
  language: "pl-PL",
  languages: ["pl-PL", "pl", "en-US", "en"],
  hardwareConcurrency: 16,
  deviceMemory: 8,
  maxTouchPoints: 0,
  
  // Screen
  screen: {width: 1920, height: 1080, availWidth: 1920, availHeight: 1040, colorDepth: 24, pixelDepth: 24},
  
  // Canvas (hash z HAR)
  canvas: {hash: "a1b2c3d4...", alphaNonzeroRatio: 0.847},
  
  // WebGL
  webgl: {
    vendor: "Google Inc. (NVIDIA)",
    renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)",
    extensions: [...],
    hash: "w5x6y7z8..."
  },
  
  // Fonts (offsetWidth z HAR)
  fonts: ["Arial", "Arial Black", "Calibri", ...],
  
  // Audio
  audio: {fingerprint: "fp123...", sampleRate: 44100},
  
  // Permissions
  permissions: {geolocation: "prompt", notifications: "default", camera: "prompt", microphone: "prompt"},
  
  // Timezone
  timezone: "Europe/Warsaw",
  timezoneOffset: -120,
  
  // WebRTC
  webrtc: {localIp: "192.168.x.x", publicIp: "auto"},
  
  // Battery (jeśli dostępne)
  battery: {charging: true, level: 1, chargingTime: 0, dischargingTime: Infinity},
};
```

### Incognia Constants (z deobfuskacji)
```javascript
const INCOGNIA_CONSTANTS = {
  HKDF_SALT: "L6ZhSbP9TciQDgxC7pjukGhl4vYis56m",
  CONSUME_SUFFIX: "/v1/consume",
  CONFIG: {
    flushIntervalMs: 5000,
    bufferLimit: 50,
    dispatchRetries: 3,
    maxDispatchFailures: 3,
    retryBaseDelayMs: 500,
  },
  CONNECTIONCHECK_URL: "https://conn-check.icg-in.com/connectioncheck",
  NETCONN_URL: "https://conn-check.icg-in.info/netconn",
  WS_URL: "wss://conn-check.icg-in.info/wsconn",
};
```

---

## 7. NASTĘPNE KROKI (ACTION ITEMS)

1. **Dzisiaj**: Wyciągnąć pełny fingerprint DataDome z HAR/Playwright network logs
2. **Jutro**: Zaimplementować `datadome_engine.js` - fingerprint generator + cookie generator
3. **Dzień 3**: Dodać behavioral simulator (mouse/keyboard/scroll)
4. **Dzień 4-5**: Incognia WebSocket + JWE handshake
5. **Dzień 6**: HTTP API Server + Python wrapper
6. **Dzień 7**: Test E2E na produkcyjnym produkcie

---

## 8. PLIKI DO UTWORZENIA

```
f:\PROJEKTY\vinted\vinted\testy_camoufox\
├── datadome_engine.js          # NOWY - fingerprint + behavioral + cookie
├── incognia_engine_extended.js # ROZSZERZENIE - WS + JWE + connectioncheck
├── checkout_helper.js          # NOWY - payload builder
├── engine_server.js            # NOWY - Express/Fastify HTTP API
├── hybrid_client.py            # NOWY - Python wrapper
├── HAR_FINGERPRINT.json        # NOWY - wyciągnięte dane z HAR
└── test_hybrid_e2e.py          # NOWY - test pełnego flow
```

---

**WERDYKT:** To **WYKONALNE** w ~3 tygodnie. Kluczem jest **nie uruchamiać pełnego DataDome SDK**, ale **generować identyczne outputy** (fingerprint, cookie, behavioral signals) które DataDome oczekuje. curl_cffi zajmie się transportem HTTP/TLS.