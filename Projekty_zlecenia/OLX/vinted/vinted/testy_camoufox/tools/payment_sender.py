"""
payment_sender.py — wysyła payment przez curl_cffi z pre-computed fingerprintem i tokenem.

Szybki — nie wymaga Camoufox, tylko curl_cffi + Node.js.
"""

import json
from pathlib import Path
from typing import Dict, Any

from curl_cffi import requests

FINGERPRINT_PATH = Path(__file__).parent / "fingerprint_datadome.json"


def load_fingerprint() -> Dict[str, Any]:
    """Wczytuje pre-computed fingerprint z pliku."""
    return json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))


def send_payment(
    checkout_id: str,
    transaction_id: int,
    token: str,
    cookies: Dict[str, str],
) -> Dict[str, Any]:
    """
    Wysyła POST /checkout/payment z pre-computed fingerprintem i tokenem.
    """
    fingerprint = load_fingerprint()

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
        cookies=cookies,
        impersonate="firefox133",
        timeout=30,
    )

    return {
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": response.text[:500] if response.text else "",
    }
