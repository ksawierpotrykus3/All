# coding: utf-8
"""Test typu payload checkout/build: 'transaction' (z HAR) vs 'item'.

HAR (udany build 200): {"purchase_items":[{"id":21872241924,"type":"transaction"}]}
Nasze testy: {"purchase_items":[{"id":9823932531,"type":"item"}]} -> 500
"""
import json
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
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
    "referer": "https://www.vinted.pl/",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

cases = [
    ("HAR exact: id=21872241924 transaction", {"purchase_items": [{"id": 21872241924, "type": "transaction"}]}),
    ("live 9823932531 transaction", {"purchase_items": [{"id": 9823932531, "type": "transaction"}]}),
    ("live 9823932531 item", {"purchase_items": [{"id": 9823932531, "type": "item"}]}),
    ("bogus 999999999999 transaction", {"purchase_items": [{"id": 999999999999, "type": "transaction"}]}),
]

for label, body in cases:
    r = s.post(BUILD_URL, json=body, headers=H,
               impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    print(f"[{label}] status={r.status_code} body={r.text[:250]}")

# sprawdz czy item 21872241924 istnieje
r = s.get("https://www.vinted.pl/api/v2/items/21872241924", impersonate=BrowserType.chrome146, timeout=30)
print("item 21872241924:", r.status_code, r.text[:150])
