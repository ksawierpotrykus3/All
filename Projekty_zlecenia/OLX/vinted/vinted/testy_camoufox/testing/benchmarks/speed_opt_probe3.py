# coding: utf-8
"""speed_opt_probe3.py — ostatnie dzignie: http_version + najlepszy impersonate.

1. Sprawdza wersje HTTP (h2 vs h1.1) na GET katalogu.
2. Porownuje impersonate na GET (read-only).
3. 1x rezerwacja najlepszym impersonate.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "speed_opt_wynik3.json"

CAT_URL = ("https://www.vinted.pl/api/v2/catalog/items"
           "?price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")

results = {"impersonate_get_ms": {}, "steps": []}

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

for imp in ("chrome146", "chrome136", "safari17_0", "firefox133"):
    t0 = time.perf_counter()
    r = s.get(CAT_URL, headers=H, impersonate=imp, timeout=30)
    dt = round((time.perf_counter() - t0) * 1000, 1)
    hver = getattr(r, "http_version", "?")
    results["impersonate_get_ms"][imp] = {"ms": dt, "http": r.status_code, "hver": hver}
    print(f"{imp}: {dt:.0f} ms http={r.status_code} h{getattr(r, 'http_version', '?')}", flush=True)
    time.sleep(0.7)


def timed(name, fn):
    t0 = time.perf_counter()
    r = fn()
    dt = round((time.perf_counter() - t0) * 1000, 1)
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        data = None
    results["steps"].append({"step": name, "total_ms": dt, "http": r.status_code,
                             "hver": getattr(r, "http_version", "?")})
    print(f"[{name}] http={r.status_code} {dt:.0f} ms h{getattr(r, 'http_version', '?')}", flush=True)
    return r, data


best = min(results["impersonate_get_ms"], key=lambda k: results["impersonate_get_ms"][k]["ms"])
print(f"\nNajszybszy impersonate (GET): {best}", flush=True)

r, data = timed("catalog", lambda: s.get(CAT_URL, headers=H, impersonate=best, timeout=30))
item = None
for it in (data or {}).get("items", []):
    if it.get("status") == "sold" or it.get("is_visible") is False:
        continue
    item = it
    break
if item is None:
    print("BRAK itemu - abort")
    raise SystemExit(1)
item_id, seller_id = item["id"], item["user"]["id"]
results["item"] = {"id": item_id, "seller": seller_id, "title": item.get("title", "")[:50]}
print(f"item={item_id} seller={seller_id}", flush=True)

t_start = time.perf_counter()
r, data = timed("conversations", lambda: s.post(
    "https://www.vinted.pl/api/v2/conversations",
    json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
    headers=H, impersonate=best, timeout=30, allow_redirects=False))
txn_id = (data or {}).get("conversation", {}).get("transaction", {}).get("id")
results["txn_id"] = txn_id

r, data = timed("build", lambda: s.post(
    "https://www.vinted.pl/api/v2/purchases/checkout/build",
    json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
    headers=H, impersonate=best, timeout=30, allow_redirects=False))
checkout_id = (data or {}).get("checkout", {}).get("id")
results["checkout_id"] = checkout_id
res_ms = round((time.perf_counter() - t_start) * 1000, 1)
results["reservation_ms"] = res_ms
print(f"REZERWACJA ({best}) = {res_ms:.0f} ms", flush=True)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
