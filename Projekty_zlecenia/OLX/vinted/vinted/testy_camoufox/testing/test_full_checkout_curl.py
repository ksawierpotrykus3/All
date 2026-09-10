# coding: utf-8
"""Pełny replay checkout curl_cffi: build -> PUT checkout -> status itemu.

Testuje na testowym produkcie: Genesis Krypton 700 (item 9807925466, transaction 21872241924).
"""
import json
import time
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
ITEM_ID = 9807925466
TRANSACTION_ID = 21872241924

results = {}

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

# 1) BUILD
body = {"purchase_items": [{"id": TRANSACTION_ID, "type": "transaction"}]}
r = s.post(BUILD_URL, json=body, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
results["build"] = {"status": r.status_code, "body": r.text[:3000]}
print(f"[BUILD] {r.status_code}")
try:
    build = r.json()
    checkout_id = build.get("checkout", {}).get("id")
    print(f"[BUILD] checkout_id={checkout_id}")
    print(f"[BUILD] keys={list(build.keys())}")
    comps = build.get("checkout", {}).get("components", {})
    print(f"[BUILD] components={list(comps.keys())}")
except Exception as e:  # noqa: BLE001
    print(f"[BUILD] parse error: {e}")
    checkout_id = None

# 2) PUT checkout (puste komponenty - jak frontend po wejściu)
if checkout_id:
    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    put_body = {"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {},
    }}
    r = s.put(put_url, json=put_body, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    results["put_checkout"] = {"status": r.status_code, "body": r.text[:3000]}
    print(f"[PUT checkout] {r.status_code} body={r.text[:500]}")
    time.sleep(1)

# 3) Status itemu po build/PUT
r = s.get(f"https://www.vinted.pl/api/v2/items/{ITEM_ID}", impersonate=BrowserType.chrome146, timeout=30)
results["item_status"] = {"status": r.status_code, "body": r.text[:800]}
print(f"[ITEM {ITEM_ID}] {r.status_code} {r.text[:400]}")

# 4) Status transakcji
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{TRANSACTION_ID}", impersonate=BrowserType.chrome146, timeout=30)
results["transaction_status"] = {"status": r.status_code, "body": r.text[:800]}
print(f"[TRANSACTION {TRANSACTION_ID}] {r.status_code} {r.text[:400]}")

(BASE_DIR / "wynik_full_checkout_curl.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_full_checkout_curl.json")
