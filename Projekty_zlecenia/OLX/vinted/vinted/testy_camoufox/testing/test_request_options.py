# coding: utf-8
"""Testuje live endpoint offers/request_options przez curl_cffi — czy tworzy/zwraca transaction id.

Body z HAR: {"price":{"amount":"150","currency_code":"PLN"},"item_ids":[9807925466],"seller_id":161574001}
"""
import json
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
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
    "referer": "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

url = "https://www.vinted.pl/api/v2/offers/request_options"
body = {"price": {"amount": "150", "currency_code": "PLN"},
        "item_ids": [9807925466],
        "seller_id": 161574001}

r = s.post(url, json=body, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"status={r.status_code}")
print(f"body: {r.text[:2000]}")

# Bonus: GET transactions dla itemu? i inne próby
# 1) czy endpoint /api/v2/items/{id} z auth pokazuje transaction?
r2 = s.get(f"https://www.vinted.pl/api/v2/items/9807925466", impersonate=BrowserType.chrome146, timeout=30,
           headers={"x-csrf-token": CSRF, "x-anon-id": ANON, "locale": "pl-PL"})
print(f"\nitems/9807925466 (z CSRF): {r2.status_code} {r2.text[:300]}")

# 2) próba /api/v2/transactions z item_id? (sonda - może nie istnieć)
r3 = s.post("https://www.vinted.pl/api/v2/transactions", json={"item_id": 9807925466}, headers=H,
            impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"\nPOST /api/v2/transactions: {r3.status_code} {r3.text[:400]}")
