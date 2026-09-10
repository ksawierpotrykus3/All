# coding: utf-8
"""Pełny flow zakupowy do BRAMKI przez WYŁĄCZNIE curl_cffi (bez Camoufox).

Ścieżka zakupowa 100% curl_cffi:
  catalog -> conversations -> build -> PUT payment_method -> pickup_points
  -> PUT pickup_details -> payment (-> redirect bramki Adyen)

Bez przeglądarki w ścieżce zakupowej. Zapisuje redirect_url + czas dotarcia (ms)
oraz timestamp, aby osobno wykonać screenshot bramki (render pomocniczy).

Użycie: python bench_curl_gateway_nocam.py
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMP = "chrome136"  # spójny z sesją; nie rotować

results = {"ts_start": None, "steps": [], "elapsed": {}}
T0 = time.monotonic()


def now_ms() -> float:
    return round((time.monotonic() - T0) * 1000, 1)


def wall_ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


results["ts_start"] = wall_ts()


def step(name, **extra):
    e = {"step": name, "elapsed_ms": now_ms(), "wall_utc": wall_ts()}
    e.update(extra)
    results["steps"].append(e)
    print(f"[{e['elapsed_ms']:>9.1f} ms] {name}", flush=True)


def _find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(_find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(_find_checksum(v))
    return hits


# --- sesja ---
s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
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


def main():
    # 0) health
    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=H, impersonate=IMP, timeout=30)
    if r.status_code != 200:
        print(f"[ABORT] /users/current -> {r.status_code}: {r.text[:120]}", flush=True)
        return
    step("health", http=200)

    # 1) catalog
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")
    r = s.get(url, headers=H, impersonate=IMP, timeout=30)
    item = None
    for it in r.json().get("items", []):
        u = it.get("user", {})
        if not u or it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        item = it
        break
    if item is None:
        print("BRAK itemu - abort", flush=True)
        return
    item_id, seller_id = item["id"], item["user"]["id"]
    step("catalog", http=r.status_code, item_id=item_id, seller_id=seller_id)

    # 2) conversations
    r = s.post("https://www.vinted.pl/api/v2/conversations",
               json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
               headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
    j = r.json()
    txn_id = j["conversation"]["transaction"]["id"]
    step("conversations", http=r.status_code, txn_id=txn_id)

    # 3) build
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
               headers=H | {"referer": f"https://www.vinted.pl/items/{item_id}"},
               impersonate=IMP, timeout=30, allow_redirects=False)
    if r.status_code != 200:
        step("build", http=r.status_code, body=r.text[:200])
        results["blocked"] = True
        _save()
        return
    build = r.json()
    checkout_id = build.get("checkout", {}).get("id")
    ch = _find_checksum(build)
    comps = build.get("checkout", {}).get("components", {})
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    addr = comps.get("shipping_address", {}).get("address", {})
    coords = addr.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    step("build", http=200, checkout_id=checkout_id)

    # 4) PUT payment_method
    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    r = s.put(put_url, json={"components": {
        "additional_service": {}, "payment_method": {"card_id": None, "pay_in_method_id": "12"},
        "shipping_address": {}, "shipping_pickup_options": {}, "shipping_pickup_details": {},
    }}, headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
    try:
        ch2 = _find_checksum(r.json())
    except Exception:
        ch2 = []
    step("put payment_method", http=r.status_code, checksum=bool(ch2))

    # 5) pickup points
    point = None
    if so_id:
        pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
                   f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
        r = s.get(pts_url, headers=H, impersonate=IMP, timeout=30)
        pp = r.json()
        spoints = (pp or {}).get("shipping_points") or []
        sug = (pp or {}).get("suggested_shipping_point_code")
        for cand in spoints:
            sp = cand.get("point", {})
            if sug and sp.get("code") == sug:
                point = sp
                break
        if point is None and spoints:
            point = spoints[0].get("point", {})
        step("pickup_points", http=r.status_code, n=len(spoints))

    # 6) PUT pickup_details
    details = {}
    if rate_uuid:
        details["rate_uuid"] = rate_uuid
    if point:
        if point.get("code"):
            details["point_code"] = point["code"]
        if point.get("uuid"):
            details["point_uuid"] = point["uuid"]
        if point.get("rate_uuid"):
            details["rate_uuid"] = point["rate_uuid"]
    r = s.put(put_url, json={"components": {
        "additional_service": {}, "payment_method": {}, "shipping_address": {},
        "shipping_pickup_options": {}, "shipping_pickup_details": details,
    }}, headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
    try:
        ch3 = _find_checksum(r.json())
    except Exception:
        ch3 = []
    step("put pickup_details", http=r.status_code, checksum=bool(ch3))

    # 7) payment -> bramka
    checksum = (ch3 or ch2 or ch)[0] if (ch3 or ch2 or ch) else ""
    r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
               json={"checksum": checksum, "payment_options": {"browser_info": {
                   "language": "pl", "color_depth": 24, "java_enabled": False,
                   "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
               headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
    try:
        pj = r.json()
    except Exception:
        pj = {}
    pay_status = (pj.get("payment") or {}).get("status")
    nav = (pj.get("action") or {}).get("parameters") or {}
    redirect_url = nav.get("url", "")
    T_GATEWAY = now_ms()
    success = (r.status_code == 200 and pay_status == "pending" and bool(redirect_url))
    results["success"] = success
    results["redirect_url"] = redirect_url
    results["elapsed"]["to_gateway_ms"] = T_GATEWAY if success else None
    step("PAYMENT -> BRAMKA" if success else "PAYMENT (BLAD)",
         http=r.status_code, payment_status=pay_status,
         redirect=redirect_url[:100], success=success)

    _save()


def _save():
    out = BASE_DIR / "wynik_bench_gateway_nocam.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {out}", flush=True)


if __name__ == "__main__":
    main()