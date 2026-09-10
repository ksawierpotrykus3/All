# coding: utf-8
"""Zoptymalizowany flow zakupowy do BRAMKI — wszystkie potwierdzone wektory naraz.

Wektory (wszystkie UDOWODNIONE):
  - NOWY backend transakcji /messaging/main/inquiries (~28% szybszy, sekcja 34.7)
  - równoległość PUT payment_method | GET nearby_pickup_points (sekcja 32.5)
  - pojedynczy PUT pickup_details (nie 6 osobnych PUT-ów, sekcja 34.5)

Sekwencja (krytyczna ścieżka):
  1. inquiries (nowy backend)          -> transaction_id
  2. checkout/build                     -> checkout_id + rate_uuid + checksum
  3. [PUT payment_method | GET pickup]  (równolegle, ThreadPoolExecutor)
  4. PUT pickup_details                 -> nowy checksum
  5. payment                            -> bramka

Bez Camoufox, bez selektorów. Screenshot bramki osobno (render_bramka.py).
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMP = "chrome136"  # sprawdzone 3x run 200 do bramki (13:29/14:57/15:07)

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


def _make_session():
    s = cr.Session(impersonate=IMP)
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
    return s


H = {"x-csrf-token": CSRF, "x-anon-id": ANON}


def main():
    s = _make_session()

    # 0) health
    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=H, impersonate=IMP, timeout=30)
    if r.status_code != 200:
        print(f"[ABORT] health {r.status_code}: {r.text[:120]}", flush=True)
        return
    step("health", http=200)

    # 1) catalog (scrapowanie — poza krytyczną ścieżką)
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=60&currency=PLN")
    r = s.get(url, headers=H, impersonate=IMP, timeout=30)
    item = None
    for it in r.json().get("items", []):
        u = it.get("user", {})
        if not u or it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        item = it
        break
    if item is None:
        print("BRAK itemu", flush=True)
        return
    item_id, seller_id = item["id"], item["user"]["id"]
    step("catalog", http=r.status_code, item_id=item_id, seller_id=seller_id)

    t_checkout = now_ms()

    # 2) NOWY backend: /messaging/main/inquiries -> transaction_id
    r = s.post("https://api.vinted.pl/messaging/main/inquiries",
               json={"item_ids": [str(item_id)], "receiver_id": str(seller_id)},
               headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
    j = r.json()
    txn_id = j.get("transaction_id")
    step("inquiries (nowy backend)", http=r.status_code, txn_id=txn_id)

    # 3) build -> checkout_id + rate_uuid + checksum
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": int(txn_id), "type": "transaction"}]},
               headers=H | {"referer": f"https://www.vinted.pl/items/{item_id}"},
               impersonate=IMP, timeout=30, allow_redirects=False)
    if r.status_code != 200:
        step("build", http=r.status_code, body=r.text[:200])
        results["blocked"] = True
        _save()
        return
    build = r.json()
    checkout_id = build.get("checkout", {}).get("id")
    ch_build = _find_checksum(build)
    comps = build.get("checkout", {}).get("components", {})
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    addr = comps.get("shipping_address", {}).get("address", {})
    coords = addr.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    step("build", http=200, checkout_id=checkout_id, rate_uuid=rate_uuid)

    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
               f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")

    # 4) RÓWNOLEGLE: PUT payment_method | GET pickup_points
    def put_payment_method():
        r = s.put(put_url, json={"components": {
            "additional_service": {},
            "payment_method": {"card_id": None, "pay_in_method_id": "12"},
            "shipping_address": {},
            "shipping_pickup_options": {"pickup_type": 1},
            "shipping_pickup_details": {},
        }}, headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
        try:
            return r.status_code, _find_checksum(r.json())
        except Exception:
            return r.status_code, []

    def get_pickup():
        r = s.get(pts_url, headers=H, impersonate=IMP, timeout=30)
        pp = r.json()
        spoints = (pp or {}).get("shipping_points") or []
        sug = (pp or {}).get("suggested_shipping_point_code")
        point = None
        for cand in spoints:
            sp = cand.get("point", {})
            if sug and sp.get("code") == sug:
                point = sp
                break
        if point is None and spoints:
            point = spoints[0].get("point", {})
        return r.status_code, point

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_put = ex.submit(put_payment_method)
        f_pts = ex.submit(get_pickup)
        put_status, ch_put = f_put.result()
        pts_status, point = f_pts.result()
    step("PUT payment_method | GET pickup (równolegle)",
         http=put_status, pickup_status=pts_status, point_code=point.get("code") if point else None)

    # 5) PUT pickup_details -> nowy checksum
    details = {}
    if rate_uuid:
        details["rate_uuid"] = rate_uuid
    if point:
        if point.get("code"):
            details["point_code"] = point["code"]
        if point.get("uuid"):
            details["point_uuid"] = point["uuid"]
    r = s.put(put_url, json={"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": details,
    }}, headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
    try:
        ch_final = _find_checksum(r.json())
    except Exception:
        ch_final = []
    step("PUT pickup_details", http=r.status_code, checksum=bool(ch_final))

    # 6) payment -> bramka
    checksum = (ch_final or ch_put or ch_build)[0] if (ch_final or ch_put or ch_build) else ""
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
    results["elapsed"]["checkout_only_ms"] = round(T_GATEWAY - t_checkout, 1)
    results["elapsed"]["to_gateway_ms"] = T_GATEWAY if success else None
    step("PAYMENT -> BRAMKA" if success else "PAYMENT (BLAD)",
         http=r.status_code, payment_status=pay_status,
         redirect=redirect_url[:100], success=success)

    _save()


def _save():
    out = BASE_DIR / "wynik_bench_gateway_opt.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {out}", flush=True)


if __name__ == "__main__":
    main()