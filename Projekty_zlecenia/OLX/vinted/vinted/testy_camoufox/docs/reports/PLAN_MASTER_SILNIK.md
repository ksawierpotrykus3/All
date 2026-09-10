# Plan implementacji: Master Silnik dla Checkout Vinted

**Data:** 2026-08-30
**Status:** Propozycja — do akceptacji przed implementacją

---

## 1. Cel

Zbudowanie **master silnika** w Pythonie, który orkiestruje:
- **Camoufox** — fingerprint DataDome (WebGL, Canvas, AudioContext)
- **Node.js** — token Incognia (AES-GCM z HKDF)
- **curl_cffi** — transport TLS (payment)

**Zasada:** "Zajeb z przeglądarki tylko to co najlepsze" — Camoufox tylko dla fingerprintu, reszta w Pythonie/Node.js.

---

## 2. Architektura

```
┌─────────────────────────────────────────────────────────────┐
│                    Master Silnik (Python)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Camoufox   │  │   Node.js   │  │      curl_cffi      │  │
│  │ (fingerprint)│  │   (token)   │  │     (transport)     │  │
│  │  WebGL      │  │  AES-GCM    │  │   TLS, HTTP/2       │  │
│  │  Canvas     │  │  HKDF       │  │   JA3, Akamai       │  │
│  │  Audio      │  │             │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          ▼                                   │
│                   ┌─────────────┐                            │
│                   │   Payment   │                            │
│                   │   Request   │                            │
│                   └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Struktura plików

| Plik | Rola | Język |
|---|---|---|
| `master_engine.py` | Główny orkiestrator | Python |
| `fingerprint_harvester.py` | Wyciąga fingerprint z Camoufox | Python |
| `token_generator.js` | Generuje token Incognia | Node.js |
| `payment_sender.py` | Wysyła payment przez curl_cffi | Python |
| `fingerprint_randomizer.py` | Randomizuje fingerprint (spójnie z Camoufox) | Python |

---

## 4. Implementacja

### 4.1 Master Silnik (`master_engine.py`)

```python
"""
Master Silnik — orkiestruje Camoufox, Node.js i curl_cffi dla payment.
"""

import asyncio
import json
from pathlib import Path

from fingerprint_harvester import FingerprintHarvester
from token_generator import TokenGenerator
from payment_sender import PaymentSender


class MasterEngine:
    def __init__(self):
        self.harvester = FingerprintHarvester()
        self.token_gen = TokenGenerator()
        self.payment_sender = PaymentSender()

    async def process_payment(self, checkout_id: str, transaction_id: int):
        """
        Pełny flow payment:
        1. Harvest fingerprintu z Camoufox
        2. Generowanie tokena Incognia w Node.js
        3. Wysłanie payment przez curl_cffi
        """
        # Krok 1: Fingerprint DataDome
        print("[1] Harvest fingerprintu z Camoufox...")
        fingerprint = await self.harvester.harvest()
        print(f"✅ Fingerprint uzyskany: {fingerprint['webgl_renderer']}")

        # Krok 2: Token Incognia
        print("[2] Generowanie tokena Incognia...")
        token = await self.token_gen.generate()
        print(f"✅ Token wygenerowany (długość: {len(token)})")

        # Krok 3: Payment
        print("[3] Wysyłanie payment...")
        result = await self.payment_sender.send(
            checkout_id=checkout_id,
            transaction_id=transaction_id,
            fingerprint=fingerprint,
            token=token,
        )
        print(f"✅ Payment status: {result['status']}")

        return result


async def main():
    engine = MasterEngine()
    result = await engine.process_payment(
        checkout_id="eWjYk_Oxxq3qOpWC4gee4",
        transaction_id=21872241924,
    )
    print(f"\nWynik: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 Fingerprint Harvester (`fingerprint_harvester.py`)

```python
"""
Fingerprint Harvester — wyciąga fingerprint DataDome z Camoufox.
"""

import asyncio
from typing import Dict, Any

from camoufox.async_api import AsyncCamoufox


class FingerprintHarvester:
    async def harvest(self) -> Dict[str, Any]:
        """
        Wyciąga fingerprint DataDome z Camoufox.
        """
        async with AsyncCamoufox(
            headless=True,
            fingerprint_preset=True,
            block_webgl=False,  # WebGL potrzebny dla DataDome
        ) as browser:
            page = await browser.new_page()
            await page.goto("https://www.vinted.pl", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # Wyciągnij fingerprint
            fingerprint = await page.evaluate("""
                () => {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl');
                    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');

                    return {
                        webgl_vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
                        webgl_renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL),
                        canvas_fingerprint: canvas.toDataURL(),
                        audio_fingerprint: null,  // TODO: AudioContext
                        screen_width: window.screen.width,
                        screen_height: window.screen.height,
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    };
                }
            """)

            return fingerprint
```

### 4.3 Token Generator (`token_generator.js`)

```javascript
/**
 * Token Generator — generuje token Incognia (AES-GCM z HKDF).
 */

const HKDF_SALT = new TextEncoder().encode('L6ZhSbP9TciQDgxC7pjukGhl4vYis56m');

async function deriveKey(sdkInstanceId) {
    const ikm = new TextEncoder().encode(sdkInstanceId);
    const baseKey = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
        { name: 'HKDF', salt: HKDF_SALT, info: new Uint8Array(0), hash: 'SHA-256' },
        baseKey,
        { name: 'AES-GCM', length: 256 },
        true,
        ['encrypt']
    );
}

async function generateToken(sdkInstanceId) {
    const key = await deriveKey(sdkInstanceId);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const payload = new TextEncoder().encode('{}');
    const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, payload);
    const out = new Uint8Array(iv.length + ct.byteLength);
    out.set(iv, 0);
    out.set(new Uint8Array(ct), iv.length);
    return Buffer.from(out).toString('base64');
}

module.exports = { generateToken };
```

### 4.4 Payment Sender (`payment_sender.py`)

```python
"""
Payment Sender — wysyła payment przez curl_cffi.
"""

from typing import Dict, Any

from curl_cffi import requests


class PaymentSender:
    async def send(
        self,
        checkout_id: str,
        transaction_id: int,
        fingerprint: Dict[str, Any],
        token: str,
    ) -> Dict[str, Any]:
        """
        Wysyła POST /checkout/payment z fingerprintem i tokenem.
        """
        url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"

        headers = {
            "accept": "application/json,text/plain,*/*,image/webp",
            "content-type": "application/json",
            "locale": "pl-PL",
            "origin": "https://www.vinted.pl",
            "referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}&order_id={transaction_id}&order_type=transaction",
            "x-anon-id": "98c6af5a-87da-45f2-9be5-24cf9345b003",
            "x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e",
            "x-incognia-request-token": token,
        }

        payload = {
            "checksum": "81043dda779dede26e8b40630aaf2c51|4f2ff5adfdcf999ed4a3e9d1c47afe91",
            "payment_options": {
                "browser_info": {
                    "language": "pl",
                    "color_depth": 24,
                    "java_enabled": False,
                    "screen_height": fingerprint["screen_height"],
                    "screen_width": fingerprint["screen_width"],
                    "timezone_offset": -120,
                }
            },
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            impersonate="firefox133",
            timeout=30,
        )

        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response.text[:500] if response.text else "",
        }
```

### 4.5 Fingerprint Randomizer (`fingerprint_randomizer.py`)

```python
"""
Fingerprint Randomizer — randomizuje fingerprint spójnie z Camoufox.
"""

import random
from typing import Dict, Any


class FingerprintRandomizer:
    def randomize(self, fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Randomizuje fingerprint spójnie z Camoufox.
        """
        # WebGL renderer — zmiana ostatnich cyfr
        renderer = fingerprint["webgl_renderer"]
        if "(" in renderer:
            base, version = renderer.rsplit("(", 1)
            version = version.rstrip(")")
            randomized = f"{base}({version[:-3]}{random.randint(100, 999)})"
            fingerprint["webgl_renderer"] = randomized

        # Screen resolution — lekka zmiana
        fingerprint["screen_width"] += random.randint(-2, 2)
        fingerprint["screen_height"] += random.randint(-2, 2)

        return fingerprint
```

---

## 5. Testowanie

### 5.1 Test jednostkowy

```python
def test_master_engine():
    engine = MasterEngine()
    result = asyncio.run(engine.process_payment(
        checkout_id="eWjYk_Oxxq3qOpWC4gee4",
        transaction_id=21872241924,
    ))
    assert result["status"] == 200
```

### 5.2 Test integracyjny

```python
def test_full_flow():
    # Test pełnego flow: harvest → token → payment
    pass
```

---

## 6. Wdrożenie

### 6.1 Wymagania

- Python 3.11+
- Node.js 18+
- Camoufox (z fingerprint_preset=True)
- curl_cffi>=0.15.0

### 6.2 Instalacja

```bash
pip install curl_cffi camoufox
npm install  # jeśli potrzebne
```

### 6.3 Uruchomienie

```bash
python master_engine.py
```

---

## 7. Wniosek

**Master Silnik** w Pythonie orkiestruje:
- **Camoufox** — fingerprint DataDome (WebGL, Canvas, AudioContext)
- **Node.js** — token Incognia (AES-GCM)
- **curl_cffi** — transport TLS (payment)

**Zasada:** "Zajeb z przeglądarki tylko to co najlepsze" — Camoufox tylko dla fingerprintu, reszta w Pythonie/Node.js.

---

**Koniec planu.**
