"""
checkout_hybrid.py — hybrydowe rozwiązanie: Camoufox build + curl_cffi payment.

Architektura:
1. Camoufox: otwiera item, klika "Kup teraz", przechwytuje build (checkout_id, checksum)
2. Zapisuje checkout_id + checksum do pliku
3. curl_cffi: używa checkout_id + checksum do payment (wielokrotnie, ~200 ms)
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
CHECKOUT_STATE_PATH = BASE_DIR / "checkout_state.json"


def camoufox_build(item_id: int) -> Dict[str, Any]:
    """
    Camoufox: otwiera item, klika "Kup teraz", przechwytuje build.
    Zwraca checkout_id + checksum.
    """
    captured = {"checkout_id": None, "checksum": None, "status": None}

    def handle_response(response):
        if "/api/v2/purchases/checkout/build" in response.url and response.request.method == "POST":
            try:
                data = response.json()
                checkout = data.get("checkout", {})
                captured["checkout_id"] = checkout.get("id")
                captured["status"] = response.status
                # Szukaj checksum
                def find_checksum(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k == "checksum":
                                return v
                            r = find_checksum(v)
                            if r:
                                return r
                    elif isinstance(obj, list):
                        for v in obj:
                            r = find_checksum(v)
                            if r:
                                return r
                    return None
                captured["checksum"] = find_checksum(data)
            except Exception:
                pass

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
    ) as ctx:
        page = ctx.new_page()
        page.on("response", handle_response)

        # Otwórz stronę itemu
        item_url = f"https://www.vinted.pl/items/{item_id}"
        print(f"[camoufox] Otwieranie {item_url}...")
        page.goto(item_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # Kliknij "Kup teraz" (przycisk z tekstem "Kup teraz")
        print("[camoufox] Klikanie 'Kup teraz'...")
        page.click("button:has-text('Kup teraz')", timeout=10000)
        time.sleep(8)  # dłuższe oczekiwanie na build

        # Czekaj na checkout
        if captured["checkout_id"]:
            print(f"[camoufox] Build przechwycony: checkout_id={captured['checkout_id']}")
        else:
            print("[camoufox] Build nie przechwycony — sprawdzanie URL...")
            current_url = page.url
            print(f"[camoufox] Aktualny URL: {current_url}")
            if "/checkout" in current_url:
                import re
                m = re.search(r"/checkout/([a-zA-Z0-9_-]+)", current_url)
                if m:
                    captured["checkout_id"] = m.group(1)
                    print(f"[camoufox] Checkout z URL: {captured['checkout_id']}")
            # Screenshot dla debugowania
            page.screenshot(path=str(BASE_DIR / "debug_after_click.png"))
            print("[camoufox] Screenshot zapisany: debug_after_click.png")

        return captured


def save_checkout_state(checkout_id: str, checksum: str, item_id: int) -> None:
    """Zapisuje checkout_id + checksum do pliku."""
    state = {
        "checkout_id": checkout_id,
        "checksum": checksum,
        "item_id": item_id,
        "timestamp": time.time(),
    }
    CHECKOUT_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"[hybrid] Zapisano stan checkout: {CHECKOUT_STATE_PATH}")


def load_checkout_state() -> Optional[Dict[str, Any]]:
    """Wczytuje checkout_id + checksum z pliku."""
    if not CHECKOUT_STATE_PATH.exists():
        return None
    return json.loads(CHECKOUT_STATE_PATH.read_text(encoding="utf-8"))


def curl_payment(checkout_id: str, checksum: str, token: str) -> Dict[str, Any]:
    """
    curl_cffi: payment dla checkout_id + checksum.
    """
    from checkout_flow import step5_payment, _create_session

    session = _create_session()
    result = step5_payment(session, checkout_id, checksum, token)
    return result


def main():
    """Pełny hybrydowy flow: Camoufox build + curl_cffi payment."""
    import sys
    sys.path.insert(0, str(BASE_DIR))

    # Krok 1: Camoufox build
    item_id = 9824457876  # z poprzedniego testu
    print("=== KROK 1: Camoufox build ===")
    build_result = camoufox_build(item_id)

    if not build_result["checkout_id"]:
        print("❌ Build nie przechwycony")
        return

    # Zapisz stan
    save_checkout_state(build_result["checkout_id"], build_result["checksum"], item_id)

    # Krok 2: curl_cffi payment
    print("\n=== KROK 2: curl_cffi payment ===")
    from test_payment_flow import get_sdk_instance_id, generate_token_nodejs

    sdk_id = get_sdk_instance_id()
    token = generate_token_nodejs(sdk_id)

    payment_result = curl_payment(build_result["checkout_id"], build_result["checksum"], token)
    print(f"Payment status: {payment_result['status']}")
    print(f"Payment success: {payment_result['success']}")

    # Zapisz wynik
    result = {
        "build": build_result,
        "payment": payment_result,
    }
    (BASE_DIR / "wynik_hybrid.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWynik zapisany do: {BASE_DIR / 'wynik_hybrid.json'}")


if __name__ == "__main__":
    main()
