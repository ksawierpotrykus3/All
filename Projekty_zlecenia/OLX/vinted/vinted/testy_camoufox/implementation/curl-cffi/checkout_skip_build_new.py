# coding: utf-8
"""checkout_skip_build_new.py — czy NOWA transakcja (bez wczesniejszego builda) ma purchase_id?

Jesli conversations na swiezym itemie zwraca transaction.purchase_id -> skip-build dziala
tez dla NOWYCH zakupow (bez wczesniejszego builda). Jesli null -> build jest niezbędny raz.

Bezpieczny probe: 1x conversations na swiezym itemie (tworzy tylko transakcje, nic nie placi).
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_skip_build_new.json"

CAT_URL = ("https://www.vinted.pl/api/v2/catalog/items"
           "?price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")

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

# znajdz swiezy item
r = s.get(CAT_URL, headers=H, impersonate="chrome146", timeout=30)
item = None
for it in r.json().get("items", []):
    if it.get("status") == "sold" or it.get("is_visible") is False:
        continue
    item = it
    break
if item is None:
    print("BRAK itemu")
    raise SystemExit(1)
item_id, seller_id = item["id"], item["user"]["id"]
print(f"item={item_id} seller={seller_id} '{item.get('title','')[:40]}'", flush=True)

t0 = time.perf_counter()
r = s.post(
    "https://www.vinted.pl/api/v2/conversations",
    json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
    headers=H, impersonate="chrome146", timeout=30, allow_redirects=False,
)
dt = round((time.perf_counter() - t0) * 1000, 1)
data = r.json() if r.status_code == 200 else {}
conv = data.get("conversation", {})
txn = conv.get("transaction") or {}
result = {
    "http": r.status_code, "elapsed_ms": dt, "item_id": item_id,
    "transaction_id": txn.get("id"),
    "transaction_status": txn.get("status"),
    "purchase_id": txn.get("purchase_id"),
    "is_reserved": txn.get("is_reserved"),
}
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
