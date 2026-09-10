# coding: utf-8
"""Pomiar czasu ścieżki curl_cffi: catalog -> conversations -> checkout/build.

Cel: udokumentować realną prędkość curl_cffi (ms/krok) jako dowód porównania
z botem klienta (Camoufox pełny flow). Nie wykonuje płatności.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = BASE_DIR / "cookies_profil.json"

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMPERSONATE = "chrome136"

T0 = time.monotonic()
results = {"started_utc": datetime.now(timezone.utc).isoformat(), "steps": []}


def t_now() -> float:
    return round((time.monotonic() - T0) * 1000, 1)


def step(name, http=None, extra=None):
    e = {
        "step": name,
        "elapsed_ms": t_now(),
        "wall_utc": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z",
    }
    if http is not None:
        e["http"] = http
    if extra:
        e.update(extra)
    results["steps"].append(e)
    print(f"[{e['elapsed_ms']:>9.1f} ms] {name}" + (f" -> HTTP {http}" if http is not None else ""), flush=True)


def _session() -> cr.Session:
    s = cr.Session()
    for c in json.loads(COOKIES_PATH.read_text(encoding="utf-8")):
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
    return s


def main():
    s = _session()
    H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

    # 1) catalog
    step("start")
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
              headers=H, impersonate=IMPERSONATE, timeout=30)
    items = r.json().get("items", [])
    it = items[0] if items else {}
    item_id, seller_id = it.get("id"), (it.get("user") or {}).get("id")
    step("catalog_items", http=r.status_code, extra={"items": len(items), "item_id": item_id})

    # 2) conversations (tworzy transakcje)
    r = s.post("https://www.vinted.pl/api/v2/conversations",
               json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
               headers=H, impersonate=IMPERSONATE, timeout=30, allow_redirects=False)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:200]}
    conv = data.get("conversation", {}) if isinstance(data, dict) else {}
    txn = conv.get("transaction") or {}
    txn_id = txn.get("id")
    purchase_id = txn.get("purchase_id")
    step("conversations_create_txn", http=r.status_code,
         extra={"transaction_id": txn_id, "purchase_id": purchase_id})

    # 3) checkout/build (spodziewany 403 DataDome w stanie blokady)
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
               headers=H | {"referer": f"https://www.vinted.pl/items/{item_id}"},
               impersonate=IMPERSONATE, timeout=30, allow_redirects=False)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:300]}
    step("checkout_build", http=r.status_code,
         extra={"captcha": "geo.captcha-delivery.com" in r.text})

    results["elapsed_total_ms"] = t_now()
    (BASE_DIR / "pomiar_czasu_curl_out.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== KONIEC: {results['elapsed_total_ms']} ms ===")


if __name__ == "__main__":
    main()
