# coding: utf-8
"""speed_opt_probe.py — gdzie znika czas rezerwacji?

Rozbija rezerwacje (conversations + build) na fazy send/parse,
mierzy koszt zimnego vs cieplego polaczenia i porownuje impersonate.
Wszystko read-only poza 1x rezerwacja (taki sam koszt jak normalny flow).

Uzycie: python speed_opt_probe.py
Wymaga swiezych cookies_profil.json.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "speed_opt_wynik.json"

CAT_URL = ("https://www.vinted.pl/api/v2/catalog/items"
           "?price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")

results = {"steps": [], "impersonate_get_ms": {}, "notes": []}


def now_ms() -> float:
    return round(time.perf_counter() * 1000, 1)


def timed(name: str, fn):
    t0 = time.perf_counter()
    r = fn()
    send = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter()
    try:
        data = r.json()
        parse = round((time.perf_counter() - t0) * 1000, 1)
    except Exception:  # noqa: BLE001
        data = None
        parse = None
    results["steps"].append({
        "step": name, "send_ms": send, "parse_ms": parse,
        "total_ms": round(send + (parse or 0), 1), "http": r.status_code,
    })
    print(f"[{name}] http={r.status_code} send={send:.0f} parse={parse} total={send + (parse or 0):.0f} ms",
          flush=True)
    return r, data


# --- Sesja ---
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

# --- 1) Porownanie impersonate na GET (read-only, ostroznie - przerwy) ---
for imp in ("chrome146", "firefox133"):
    t0 = time.perf_counter()
    r = s.get(CAT_URL, headers=H, impersonate=imp, timeout=30)
    dt = round((time.perf_counter() - t0) * 1000, 1)
    results["impersonate_get_ms"][imp] = dt
    print(f"impersonate={imp} catalog GET {dt:.0f} ms http={r.status_code}", flush=True)
    time.sleep(0.8)

# --- 2) Cieply GET + wybor itemu ---
r, data = timed("catalog(warm+wybor)", lambda: s.get(
    CAT_URL, headers=H, impersonate="chrome146", timeout=30))
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
results["item"] = {"id": item_id, "seller": seller_id,
                   "title": item.get("title", "")[:50]}
print(f"item={item_id} seller={seller_id} '{item.get('title','')[:40]}'", flush=True)

# --- 3) Rezerwacja: conversations -> build ---
t_start = time.perf_counter()
r, data = timed("conversations", lambda: s.post(
    "https://www.vinted.pl/api/v2/conversations",
    json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
    headers=H, impersonate="chrome146", timeout=30, allow_redirects=False))
txn_id = (data or {}).get("conversation", {}).get("transaction", {}).get("id")
results["transaction_id"] = txn_id
print(f"txn={txn_id}", flush=True)

r, data = timed("build", lambda: s.post(
    "https://www.vinted.pl/api/v2/purchases/checkout/build",
    json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
    headers=H, impersonate="chrome146", timeout=30, allow_redirects=False))
checkout_id = (data or {}).get("checkout", {}).get("id")
results["checkout_id"] = checkout_id
reservation_ms = round((time.perf_counter() - t_start) * 1000, 1)
results["reservation_total_ms"] = reservation_ms
print(f"REZERWACJA (conversations+build) = {reservation_ms:.0f} ms", flush=True)

# --- 4) Rozmiar odpowiedzi build (czy parse/transfer jest problemem) ---
try:
    raw = json.dumps(data).encode("utf-8") if data else b""
    results["build_response_bytes"] = len(raw)
except Exception:  # noqa: BLE001
    pass

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
