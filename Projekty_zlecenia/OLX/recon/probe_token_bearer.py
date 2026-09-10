"""Sprawdź, czy świeży access_token działa jako Bearer na API OLX.

Bez przeglądarki — czysty curl_cffi. Celem jest ustalenie, czy token z cookie
autoryzuje requesty API (users/me) i czy da się znaleźć realne endpointy delivery.
"""
import base64
import json
import sys
from pathlib import Path

from curl_cffi import requests

BASE = Path(__file__).resolve().parent.parent
COOKIES_PATH = BASE / "dane" / "cookies.txt"


def read_token() -> str:
    for line in COOKIES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 7 and p[5] == "access_token":
            return p[6]
    raise SystemExit("brak access_token w cookies.txt")


def main():
    token = read_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    tests = [
        ("users/me", "https://www.olx.pl/api/v1/users/me/"),
        ("delivery/checkout/1084508890", "https://www.olx.pl/delivery/checkout/1084508890/"),
        ("delivery/orders", "https://www.olx.pl/api/v1/delivery/orders/"),
        ("delivery/buyers/profile", "https://www.olx.pl/api/v1/delivery/buyers/profile/"),
    ]

    out = {}
    for name, url in tests:
        try:
            r = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
            body = r.text[:800]
            out[name] = {"status": r.status_code, "url": url, "body": body}
            print(f"[{name}] {r.status_code} {url}")
            if r.status_code == 200:
                print(f"    {body[:300]}")
        except Exception as e:
            out[name] = {"error": str(e)}
            print(f"[{name}] ERROR {e}")

    OUT = BASE / "dane" / "probe_token_bearer.json"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Zapisano do {OUT}")


if __name__ == "__main__":
    main()