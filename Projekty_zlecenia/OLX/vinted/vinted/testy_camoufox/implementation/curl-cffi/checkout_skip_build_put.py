# coding: utf-8
"""checkout_skip_build_put.py — czy PUT components dziala na istniejacym purchase_id BEZ builda?

Transakcja 21872241924 ma purchase_id eWjYk_Oxxq3qOpWC4gee4 (z conversations).
Test: PUT /purchases/{purchase_id}/checkout (payment_method) -> 200?
Jesli tak -> cala sciezka bez builda (conversations -> PUT -> payment) jest zywa dla retry.

Ostroznie: tylko PUT payment_method (bez pickup_details, bez payment).
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_skip_build_put.json"

PURCHASE_ID = "eWjYk_Oxxq3qOpWC4gee4"

s = cr.Session()
for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
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
H = {"x-csrf-token": CSRF, "x-anon-id": ANON,
     "referer": f"https://www.vinted.pl/checkout?purchase_id={PURCHASE_ID}"}

t0 = time.perf_counter()
r = s.put(
    f"https://www.vinted.pl/api/v2/purchases/{PURCHASE_ID}/checkout",
    json={"components": {
        "additional_service": {},
        "payment_method": {"card_id": None, "pay_in_method_id": "12"},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {},
    }},
    headers=H, impersonate="chrome146", timeout=30, allow_redirects=False,
)
dt = round((time.perf_counter() - t0) * 1000, 1)
body = r.text[:600]
print(f"http={r.status_code} elapsed={dt} ms", flush=True)
print(f"body: {body}", flush=True)
OUT.write_text(json.dumps({
    "http": r.status_code, "elapsed_ms": dt, "body": body,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
