"""
test_payment_flow.py — pełny flow do payment: Node.js (token Incognia) + curl_cffi (payment).

Architektura z Fazy J + korekta z sekcji 22:
- Node.js: generuje x-incognia-request-token (AES-GCM z HKDF z sdkInstanceId)
- curl_cffi: wysyła POST /checkout/payment z cookie jar + checksum + tokenem z Node.js
- Lekki silnik JS: TAK — generuje token (AES-GCM), nie wymaga przeglądarki

Korekta kluczowa (sekcja 22): token Incognia to AES-GCM (HKDF z sdkInstanceId), nie JWE.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from payment_sender import send_payment, load_fingerprint

# Konfiguracja
ITEM_ID = 9807925466  # Genesis Krypton 700
CHECKOUT_ID = "eWjYk_Oxxq3qOpWC4gee4"  # z Fazy J
TRANSACTION_ID = 21872241924
CHECKSUM = "81043dda779dede26e8b40630aaf2c51|4f2ff5adfdcf999ed4a3e9d1c47afe91"  # z HAR

COOKIE_JAR_PATH = Path(__file__).parent / "cookies_profil.json"
RESULT_PATH = Path(__file__).parent / "wynik_payment_flow.json"
NODE_SCRIPT_PATH = Path(__file__).parent / "generate_incognia_token.js"


def load_cookies() -> dict:
    """Wczytuje cookies z cookies_profil.json (format listy Playwright)."""
    data = json.loads(COOKIE_JAR_PATH.read_text(encoding="utf-8"))
    return {c["name"]: c["value"] for c in data if c.get("name") and c.get("value")}


def generate_incognia_token_node(sdk_instance_id: str) -> str:
    """
    Generuje token Incognia przez Node.js WebCrypto (HKDF + AES-GCM).
    Token to AES-GCM z kluczem wyprowadzonym z sdkInstanceId przez HKDF.
    """
    # Wywołaj Node.js do wygenerowania tokena
    result = subprocess.run(
        ["node", str(NODE_SCRIPT_PATH), sdk_instance_id],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node.js error: {result.stderr}")
    return result.stdout.strip()


def get_sdk_instance_id() -> str:
    """
    Pobiera sdk_instance_id z GET /j3r4zw/v1/config (curl_cffi).
    """
    from curl_cffi import requests

    response = requests.get(
        "https://api.vinted.pl/j3r4zw/v1/config",
        impersonate="firefox133",
        timeout=30,
    )
    data = response.json()
    return data.get("sdk_instance_id")


async def main():
    results = {}

    # Krok 1: Pobierz sdk_instance_id (curl_cffi)
    print("[1] Pobieranie sdk_instance_id z /j3r4zw/v1/config...")
    sdk_instance_id = get_sdk_instance_id()
    results["sdk_instance_id"] = sdk_instance_id
    print(f"✅ sdk_instance_id: {sdk_instance_id}")

    # Krok 2: Node.js generuje token Incognia (AES-GCM)
    print("[2] Node.js: generowanie tokena Incognia (AES-GCM)...")
    token = generate_incognia_token_node(sdk_instance_id)
    results["token_length"] = len(token)
    print(f"✅ Token wygenerowany (długość: {len(token)})")

    # Krok 3: Wczytaj pre-computed fingerprint (z pliku, nie z Camoufox)
    print("[3] Wczytywanie pre-computed fingerprintu...")
    fingerprint = load_fingerprint()
    results["fingerprint_screen"] = f"{fingerprint['screen_width']}x{fingerprint['screen_height']}"
    print(f"✅ Fingerprint: {fingerprint['screen_width']}x{fingerprint['screen_height']}")

    # Krok 4: Wczytaj cookies z cookies_profil.json
    print("[4] Wczytywanie cookies z cookies_profil.json...")
    cookies = load_cookies()
    results["cookies_count"] = len(cookies)
    print(f"✅ Cookies: {len(cookies)} sztuk")

    # Krok 5: curl_cffi wysyła payment z pre-computed fingerprintem i cookies
    print("[5] curl_cffi: wysyłanie POST /checkout/payment...")
    payment_result = send_payment(
        checkout_id=CHECKOUT_ID,
        transaction_id=TRANSACTION_ID,
        token=token,
        cookies=cookies,
    )
    results["payment"] = payment_result
    print(f"Status: {payment_result['status']}")
    print(f"Headers: {payment_result['headers']}")
    print(f"Body: {payment_result['body'][:200]}...")

    # Zapisz wyniki
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWyniki zapisane do: {RESULT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
