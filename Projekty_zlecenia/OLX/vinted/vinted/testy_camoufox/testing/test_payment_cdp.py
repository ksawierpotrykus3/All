"""
test_payment_cdp.py — test payment przez Camoufox z CDP (najlżejsza opcja dla DataDome).

Architektura:
- Camoufox z --remote-debugging-port=9222 (CDP)
- Node.js: generuje token Incognia (AES-GCM) — nie wymaga przeglądarki
- CDP: steruje Camoufox dla payment (kliknięcie "Zapłać" z isTrusted=true)

To jest najlżejsza opcja dla payment — lżejsza niż pełna przeglądarka, cięższa niż curl_cffi.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

# Konfiguracja
ITEM_ID = 9807925466  # Genesis Krypton 700
CHECKOUT_ID = "eWjYk_Oxxq3qOpWC4gee4"  # z Fazy J
TRANSACTION_ID = 21872241924
CHECKSUM = "81043dda779dede26e8b40630aaf2c51|4f2ff5adfdcf999ed4a3e9d1c47afe91"  # z HAR

RESULT_PATH = Path(__file__).parent / "wynik_payment_cdp.json"


async def launch_camoufox_with_cdp():
    """
    Uruchamia Camoufox z CDP (remote debugging).
    """
    from camoufox.async_api import AsyncCamoufox

    # Camoufox z CDP — wymaga custom launch args
    browser = await AsyncCamoufox(
        headless=False,  # headed dla CDP
        fingerprint_preset=True,
        block_webgl=False,  # WebGL potrzebny dla DataDome
        args=["--remote-debugging-port=9222"],
    )
    return browser


async def generate_incognia_token_node(sdk_instance_id: str) -> str:
    """
    Generuje token Incognia przez Node.js WebCrypto (HKDF + AES-GCM).
    """
    result = subprocess.run(
        ["node", "generate_incognia_token.js", sdk_instance_id],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node.js error: {result.stderr}")
    return result.stdout.strip()


async def main():
    results = {}

    # Krok 1: Uruchom Camoufox z CDP
    print("[1] Uruchamianie Camoufox z CDP...")
    browser = await launch_camoufox_with_cdp()
    page = await browser.new_page()

    # Krok 2: Przejdź do checkoutu
    print("[2] Przechodzenie do checkoutu...")
    await page.goto(f"https://www.vinted.pl/items/{ITEM_ID}", wait_until="networkidle")
    await page.wait_for_timeout(3000)

    # Krok 3: Generuj token Incognia w Node.js
    print("[3] Generowanie tokena Incognia w Node.js...")
    # sdk_instance_id z localStorage lub z requestów
    sdk_instance_id = await page.evaluate("() => localStorage.getItem('sdk_instance_id')")
    if not sdk_instance_id:
        # Fallback: pobierz z /j3r4zw/v1/config
        from curl_cffi import requests
        response = requests.get("https://api.vinted.pl/j3r4zw/v1/config", impersonate="firefox133")
        sdk_instance_id = response.json().get("sdk_instance_id")

    token = await generate_incognia_token_node(sdk_instance_id)
    results["token_length"] = len(token)

    # Krok 4: Wstrzyknij token do strony i kliknij "Zapłać"
    print("[4] Wstrzykiwanie tokena i kliknięcie 'Zapłać'...")
    await page.evaluate(f"""
        () => {{
            // Wstrzyknij token do window
            window.__incognia_token = "{token}";
        }}
    """)

    # Kliknij "Zapłać" (isTrusted=true)
    # To wymaga znalezienia przycisku i kliknięcia przez CDP
    # TODO: implementacja kliknięcia

    # Zapisz wyniki
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWyniki zapisane do: {RESULT_PATH}")

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
