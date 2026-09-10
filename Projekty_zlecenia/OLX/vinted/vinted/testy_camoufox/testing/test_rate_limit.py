# coding: utf-8
"""Test: czy blokada checkout/build zalezy od liczby requestow (rate limit)?"""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "referer": "https://www.vinted.pl/",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

# Test 1: tylko katalog (bez conversations/build)
print("=== TEST 1: tylko katalog ===")
r = s.get("https://www.vinted.pl/api/v2/catalog/items"
          "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
          headers=H, impersonate=BrowserType.chrome146, timeout=30)
print(f"katalog: {r.status_code}")

# Test 2: conversations (bez build)
print("\n=== TEST 2: conversations ===")
it = r.json().get("items", [])[0]
item_id, seller_id = it["id"], it["user"]["id"]
r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"conversations: {r.status_code}")
txn = r.json()["conversation"]["transaction"]["id"]

# Test 3: build (od razu, bez sleep)
print("\n=== TEST 3: build (od razu) ===")
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"build: {r.status_code}")

# Test 4: poczekaj 60s i sprobuj ponownie
print("\n=== TEST 4: po 60s ===")
time.sleep(60)
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"build po 60s: {r.status_code}")
