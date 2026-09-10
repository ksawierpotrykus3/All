# coding: utf-8
"""checkout_skip_build_probe.py — czy mozna pominac build przy istniejacym purchase_id?

POST /conversations zwraca transakcje z transaction.purchase_id (gdy checkout istnial).
Jesli purchase_id jest -> mozna od razu PUT components + POST payment BEZ builda
(endpoint checkout/build = glowny, ktory DataDome blokuje najczesciej).

Bezpieczny probe: tylko 1x POST /conversations, zero PUT/payment.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_skip_build_probe.json"

ITEM_ID = 9807925466  # genesis krypton 700 (transakcja 21872241924 z purchase_id)
SELLER_ID = 161574001

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
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

t0 = time.perf_counter()
r = s.post(
    "https://www.vinted.pl/api/v2/conversations",
    json={"initiator": "buy", "item_id": str(ITEM_ID), "opposite_user_id": SELLER_ID},
    headers=H, impersonate="chrome146", timeout=30, allow_redirects=False,
)
dt = round((time.perf_counter() - t0) * 1000, 1)
data = r.json() if r.status_code == 200 else {}
conv = data.get("conversation", {})
txn = conv.get("transaction") or {}
result = {
    "http": r.status_code,
    "elapsed_ms": dt,
    "conversation_id": conv.get("id"),
    "transaction_id": txn.get("id"),
    "transaction_status": txn.get("status"),
    "transaction_status_title": txn.get("status_title"),
    "purchase_id": txn.get("purchase_id"),
    "is_reserved": txn.get("is_reserved"),
    "cancelable": txn.get("cancelable"),
    "transaction_keys": list(txn.keys()),
    "body_head": r.text[:400],
}
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
