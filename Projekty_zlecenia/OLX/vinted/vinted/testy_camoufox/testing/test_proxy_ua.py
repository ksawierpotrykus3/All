# coding: utf-8
"""Test: czy rotacja proxy (IP) zmienia tozsamosc dla DataDome?"""
import json
import uuid
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# Test 1: bez proxy (obecne IP)
print("=== TEST 1: bez proxy (obecne IP) ===")
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

r = s.get("https://www.vinted.pl/api/v2/catalog/items"
          "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
          headers=H, impersonate=BrowserType.chrome146, timeout=30)
it = r.json().get("items", [])[0]
item_id, seller_id = it["id"], it["user"]["id"]

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
txn = r.json()["conversation"]["transaction"]["id"]

r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"build: {r.status_code}")
if r.status_code == 200:
    print(f"checkout_id: {r.json().get('checkout', {}).get('id')}")
else:
    print(f"body: {r.text[:200]}")

# Test 2: z innym User-Agent (zmiana fingerprintu)
print("\n=== TEST 2: inny User-Agent ===")
s2 = cr.Session()
for c in cookies:
    try:
        s2.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s2.headers.update({
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
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})
H2 = {"x-csrf-token": CSRF, "x-anon-id": ANON}

r = s2.post("https://www.vinted.pl/api/v2/conversations",
            json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
            headers=H2, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
txn2 = r.json()["conversation"]["transaction"]["id"]

r = s2.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
            json={"purchase_items": [{"id": txn2, "type": "transaction"}]},
            headers=H2, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"build: {r.status_code}")
if r.status_code == 200:
    print(f"checkout_id: {r.json().get('checkout', {}).get('id')}")
else:
    print(f"body: {r.text[:200]}")
