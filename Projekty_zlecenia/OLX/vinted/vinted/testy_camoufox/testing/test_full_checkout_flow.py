"""
test_full_checkout_flow.py — pełny flow checkout → payment przez curl_cffi.

Architektura:
- Node.js: generuje token Incognia (AES-GCM z HKDF)
- checkout_flow.py: sekwencja checkout (build → 5× PUT) przez curl_cffi
- payment_sender.py: payment z pre-computed fingerprintem

Wszystko bez Camoufox (poza początkowym harvestem cookies/fingerprintu).
"""

import asyncio
import json
import subprocess
from pathlib import Path

from checkout_flow import run_checkout_flow
from payment_sender import load_fingerprint

NODE_SCRIPT_PATH = Path(__file__).parent / "generate_incognia_token.js"
RESULT_PATH = Path(__file__).parent / "wynik_full_checkout_flow.json"


def generate_incognia_token_node(sdk_instance_id: str) -> str:
    """Generuje token Incognia przez Node.js WebCrypto (HKDF + AES-GCM)."""
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
    """Pobiera sdk_instance_id z GET /j3r4zw/v1/config (curl_cffi)."""
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
    print(f"    sdk_instance_id: {sdk_instance_id}")

    # Krok 2: Node.js generuje token Incognia (AES-GCM)
    print("[2] Node.js: generowanie tokena Incognia (AES-GCM)...")
    token = generate_incognia_token_node(sdk_instance_id)
    results["token_length"] = len(token)
    print(f"    Token wygenerowany (długość: {len(token)})")

    # Krok 3: Wczytaj pre-computed fingerprint (z pliku, nie z Camoufox)
    print("[3] Wczytywanie pre-computed fingerprintu...")
    fingerprint = load_fingerprint()
    results["fingerprint_screen"] = f"{fingerprint['screen_width']}x{fingerprint['screen_height']}"
    print(f"    Fingerprint: {fingerprint['screen_width']}x{fingerprint['screen_height']}")

    # Krok 4: Pełna sekwencja checkout + payment przez curl_cffi
    print("[4] curl_cffi: pełna sekwencja checkout → payment...")
    checkout_results = run_checkout_flow(token=token)
    results["checkout"] = checkout_results

    # Zapisz wyniki
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWyniki zapisane do: {RESULT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
