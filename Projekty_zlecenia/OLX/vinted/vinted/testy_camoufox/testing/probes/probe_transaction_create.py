# coding: utf-8
"""Testuje live endpointy tworzenia transakcji.

Item 9807925466 jest już w transakcji 21872241924 (reserved) —
błąd 'already reserved' potwierdzi, że endpoint istnieje.
"""
import json
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
ITEM_ID = 9807925466
SELLER_ID = 161574001
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:  # noqa: BLE001
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "referer": f"https://www.vinted.pl/items/{ITEM_ID}-genesis-krypton-700",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

cases = [
    ("POST /api/v2/transactions", "https://www.vinted.pl/api/v2/transactions",
     {"item_id": ITEM_ID}),
    ("POST /api/v2/transactions (z ceną)", "https://www.vinted.pl/api/v2/transactions",
     {"item_id": ITEM_ID, "price": {"amount": "150", "currency_code": "PLN"}}),
    ("POST /api/v2/items/{id}/transactions", f"https://www.vinted.pl/api/v2/items/{ITEM_ID}/transactions",
     {"price": {"amount": "150", "currency_code": "PLN"}}),
    ("POST /api/v2/items/{id}/buy_now", f"https://www.vinted.pl/api/v2/items/{ITEM_ID}/buy_now",
     {}),
    ("POST /api/v2/offers (buy)", "https://www.vinted.pl/api/v2/offers",
     {"item_ids": [ITEM_ID], "price": {"amount": "150", "currency_code": "PLN"}}),
]

for label, url, body in cases:
    r = s.post(url, json=body, headers=H, impersonate=BrowserType.chrome146,
               timeout=30, allow_redirects=False)
    print(f"[{label}] status={r.status_code} body={r.text[:300]}")
