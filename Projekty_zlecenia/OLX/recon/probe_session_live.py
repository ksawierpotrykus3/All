"""Sonda sesji OLX na żywo — weryfikacja cookies i endpointów API.

Cel: potwierdzić, że dostarczone cookies dają dostęp do konta i API.
Wyniki zapisuje do dane/probe_session_live.json
"""
import json
from pathlib import Path

from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent
COOKIES_PATH = BASE / "dane" / "cookies.txt"
OUT_PATH = BASE / "dane" / "probe_session_live.json"

IMP = "chrome124"

# Endpointy do sondy (od najmniej do najbardziej inwazyjnych)
ENDPOINTS = [
    ("users_me", "https://www.olx.pl/api/v1/users/me/"),
    ("users_me_details", "https://www.olx.pl/api/v1/users/me/details/"),
    ("delivery_buyers_profile", "https://www.olx.pl/api/v1/delivery/buyers/profile/"),
    ("delivery_saved_addresses", "https://www.olx.pl/api/v1/delivery/orders/saved-addresses/"),
]


def load_cookies(path: Path) -> dict:
    """Wczytaj cookies z pliku Netscape do słownika {nazwa: wartość}."""
    cookies = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            name, value = parts[5], parts[6]
            cookies[name] = value
    return cookies


def main():
    cookies = load_cookies(COOKIES_PATH)
    results = {"cookies_loaded": len(cookies), "endpoints": {}}

    for name, url in ENDPOINTS:
        entry = {"url": url}
        try:
            r = creq.get(
                url,
                cookies=cookies,
                impersonate=IMP,
                timeout=15,
                headers={
                    "accept": "application/json",
                    "user-agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "authorization": f"Bearer {cookies.get('access_token', '')}",
                },
            )
            entry["status"] = r.status_code
            entry["content_type"] = r.headers.get("content-type", "")
            try:
                entry["json"] = r.json()
            except Exception:
                entry["text"] = r.text[:1000]
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
        results["endpoints"][name] = entry
        print(f"[{name}] {entry.get('status', entry.get('error'))}")

    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWyniki zapisane: {OUT_PATH}")


if __name__ == "__main__":
    main()