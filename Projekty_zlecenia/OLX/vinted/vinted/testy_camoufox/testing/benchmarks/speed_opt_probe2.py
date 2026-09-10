# coding: utf-8
"""speed_opt_probe2.py — dwie dzignie do <2s rezerwacji.

1. Rezerwacja na firefox133 (conversations+build) — porownanie z chrome146 (2681ms).
2. PROBE: czy build zaakceptuje item_id zamiast txn_id (skip conversations)?
   - 200/2xx -> mozna pominac conversations (-1208 ms) -> rezerwacja ~1.5s
   - 400/422 -> build wymaga txn_id, conversations zostaje.

Ostroznie: 1 pelna rezerwacja + 1 probe (koszt jak normalny build).
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "speed_opt_wynik2.json"

CAT_URL = ("https://www.vinted.pl/api/v2/catalog/items"
           "?price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")
IMP = "firefox133"

results = {"steps": [], "item": None}


def pick_item(data):
    for it in (data or {}).get("items", []):
        if it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        return it
    return None


def timed(name, fn):
    t0 = time.perf_counter()
    r = fn()
    dt = round((time.perf_counter() - t0) * 1000, 1)
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        data = None
    results["steps"].append({"step": name, "total_ms": dt, "http": r.status_code})
    print(f"[{name}] http={r.status_code} {dt:.0f} ms", flush=True)
    return r, data


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

# --- 1) Rezerwacja na firefox133 ---
r, data = timed("catalog(firefox133)", lambda: s.get(
    CAT_URL, headers=H, impersonate=IMP, timeout=30))
item = pick_item(data)
if item is None:
    print("BRAK itemu - abort")
    raise SystemExit(1)
item_id, seller_id = item["id"], item["user"]["id"]
results["item"] = {"id": item_id, "seller": seller_id,
                   "title": item.get("title", "")[:50]}
print(f"item={item_id} seller={seller_id} '{item.get('title','')[:40]}'", flush=True)

t_start = time.perf_counter()
r, data = timed("conversations(ff133)", lambda: s.post(
    "https://www.vinted.pl/api/v2/conversations",
    json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
    headers=H, impersonate=IMP, timeout=30, allow_redirects=False))
txn_id = (data or {}).get("conversation", {}).get("transaction", {}).get("id")
results["txn_id"] = txn_id
print(f"txn={txn_id}", flush=True)

r, data = timed("build(ff133)", lambda: s.post(
    "https://www.vinted.pl/api/v2/purchases/checkout/build",
    json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
    headers=H, impersonate=IMP, timeout=30, allow_redirects=False))
checkout_id = (data or {}).get("checkout", {}).get("id")
results["checkout_id"] = checkout_id
res_ms = round((time.perf_counter() - t_start) * 1000, 1)
results["reservation_ff133_ms"] = res_ms
print(f"REZERWACJA (firefox133) = {res_ms:.0f} ms", flush=True)
time.sleep(1.5)

# --- 2) PROBE: build z item_id (bez conversations) na SWIEZYM itemie ---
r2, data2 = timed("catalog#2", lambda: s.get(
    CAT_URL, headers=H, impersonate=IMP, timeout=30))
item2 = pick_item(data2)
if item2 is None or item2["id"] == item_id:
    print("BRAK drugiego itemu - abort")
    raise SystemExit(1)
item2_id = item2["id"]
print(f"probe item={item2_id}", flush=True)
time.sleep(0.8)

t_start2 = time.perf_counter()
r, data = timed("build(item_id,bez-conv)", lambda: s.post(
    "https://www.vinted.pl/api/v2/purchases/checkout/build",
    json={"purchase_items": [{"id": item2_id, "type": "transaction"}]},
    headers=H, impersonate=IMP, timeout=30, allow_redirects=False))
dt2 = round((time.perf_counter() - t_start2) * 1000, 1)
probe_body = None
try:
    probe_body = r.json()
except Exception:  # noqa: BLE001
    probe_body = {"raw": r.text[:200]}
results["probe_build_item_id"] = {
    "item2_id": item2_id, "total_ms": dt2, "http": r.status_code,
    "errors": (probe_body or {}).get("errors") if isinstance(probe_body, dict) else None,
    "body_head": json.dumps(probe_body)[:200],
}
print(f"PROBE build(item_id) http={r.status_code} {dt2:.0f} ms -> {json.dumps(probe_body)[:150]}", flush=True)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
