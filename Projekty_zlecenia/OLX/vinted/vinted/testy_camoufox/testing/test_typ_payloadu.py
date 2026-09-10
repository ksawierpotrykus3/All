# coding: utf-8
"""Ustala jak powstaje transakcja: build z type:'item' vs 'transaction'.

Pytanie: czy POST checkout/build z {id: ITEM_ID, type:"item"} tworzy nową transakcję?
Kontrola: {id: TRANSACTION_ID, type:"item"} powinno dać 500 (mismatch).
"""
import json
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
ITEM_ID = 9807925466
TRANSACTION_ID = 21872241924

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
    ("item_id type:item", {"purchase_items": [{"id": ITEM_ID, "type": "item"}]}),
    ("transaction_id type:item (kontrola)", {"purchase_items": [{"id": TRANSACTION_ID, "type": "item"}]}),
    ("item_id type:transaction (kontrola)", {"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]}),
]

for label, body in cases:
    r = s.post(BUILD_URL, json=body, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    print(f"[{label}] status={r.status_code} body={r.text[:400]}")
    print()
