# coding: utf-8
"""flow_speed_trials.py — warianty przyspieszenia flow do bramki.

Variant MINIMAL:  catalog(per_page=5) -> conversations -> build -> PAYMENT od razu
                  (bez payment_method/pickup_details - test czy checksum z builda wystarczy)
Variant PARALLEL: conversations -> build -> [payment_method || pickup_points] -> pickup_details -> PAYMENT

Mierzy czasy poszczegolnych requestow (ms) z precyzja do 1 ms.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_flow_speed_trials.json"


def wall():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


def make_session():
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
    return s


H = {"x-csrf-token": CSRF, "x-anon-id": ANON}


def find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(find_checksum(v))
    return hits


def pick_item(s, per_page=5):
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           f"?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page={per_page}&currency=PLN")
    r = s.get(url, headers=H, impersonate=BrowserType.firefox133, timeout=30)
    items = r.json().get("items", [])
    for it in items:
        if it.get("status") != "sold" and it.get("is_visible") is not False:
            return it
    return None


def flow(s, variant, timings):
    item = pick_item(s, per_page=5)
    if not item:
        return {"variant": variant, "error": "brak itemu"}
    item_id, seller_id = item["id"], item["user"]["id"]

    t0 = time.monotonic()
    r = s.post("https://www.vinted.pl/api/v2/conversations",
               json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
               headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
    timings["conversations"] = round((time.monotonic() - t0) * 1000)
    j = r.json()
    txn_id = j["conversation"]["transaction"]["id"]

    t0 = time.monotonic()
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
               headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
    timings["build"] = round((time.monotonic() - t0) * 1000)
    build = r.json()
    checkout_id = build.get("checkout", {}).get("id")
    ch = find_checksum(build)
    comps = build.get("checkout", {}).get("components", {})
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    addr = comps.get("shipping_address", {}).get("address", {})
    coords = addr.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    res = {"variant": variant, "item_id": item_id, "txn": txn_id, "checkout": checkout_id,
           "http": {"conversations": r.status_code, "build": r.status_code}}

    checksum = ch[0] if ch else ""

    if variant == "MINIMAL":
        # od razu PAYMENT na checksumie z builda (bez PUT-ow)
        t0 = time.monotonic()
        r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
                   json={"checksum": checksum, "payment_options": {"browser_info": {
                       "language": "pl", "color_depth": 24, "java_enabled": False,
                       "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
                   headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
        timings["payment"] = round((time.monotonic() - t0) * 1000)
        res["http"]["payment"] = r.status_code
        try:
            pj = r.json()
        except Exception:
            pj = {}
        res["payment_status"] = (pj.get("payment") or {}).get("status")
        res["redirect"] = ((pj.get("action") or {}).get("parameters") or {}).get("url", "")[:80]
        res["pay_body"] = r.text[:120]
        return res

    # PARALLEL: payment_method || pickup_points
    from concurrent.futures import ThreadPoolExecutor

    def put_payment_method():
        t0 = time.monotonic()
        rr = s.put(put_url, json={"components": {
            "additional_service": {}, "payment_method": {"card_id": None, "pay_in_method_id": "12"},
            "shipping_address": {}, "shipping_pickup_options": {}, "shipping_pickup_details": {}},
        }, headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
        try:
            c2 = find_checksum(rr.json())
        except Exception:
            c2 = []
        return round((time.monotonic() - t0) * 1000), rr.status_code, c2[0] if c2 else ""

    def get_points():
        if not so_id:
            return 0, None, None
        t0 = time.monotonic()
        rr = s.get(f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
                   f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}",
                   headers=H, impersonate=BrowserType.firefox133, timeout=30)
        pp = rr.json() if rr.status_code == 200 else {}
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
        return round((time.monotonic() - t0) * 1000), point, len(spoints)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(put_payment_method)
        f2 = ex.submit(get_points)
        pm_ms, pm_st, ch2 = f1.result()
        pts_ms, point, n_pts = f2.result()
    timings["payment_method||pickup_points"] = round((time.monotonic() - t0) * 1000)
    timings["  payment_method"] = pm_ms
    timings["  pickup_points"] = pts_ms
    res["http"]["payment_method"] = pm_st
    res["pickup_points_n"] = n_pts

    # pickup_details PUT
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
    t0 = time.monotonic()
    r = s.put(put_url, json={"components": {
        "additional_service": {}, "payment_method": {}, "shipping_address": {},
        "shipping_pickup_options": {}, "shipping_pickup_details": details},
    }, headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
    timings["pickup_details"] = round((time.monotonic() - t0) * 1000)
    res["http"]["pickup_details"] = r.status_code
    try:
        ch3 = find_checksum(r.json())
    except Exception:
        ch3 = []
    checksum = (ch3 or [ch2 or checksum])[0]

    # PAYMENT
    t0 = time.monotonic()
    r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
               json={"checksum": checksum, "payment_options": {"browser_info": {
                   "language": "pl", "color_depth": 24, "java_enabled": False,
                   "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
               headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
    timings["payment"] = round((time.monotonic() - t0) * 1000)
    res["http"]["payment"] = r.status_code
    try:
        pj = r.json()
    except Exception:
        pj = {}
    res["payment_status"] = (pj.get("payment") or {}).get("status")
    res["redirect"] = ((pj.get("action") or {}).get("parameters") or {}).get("url", "")[:80]
    return res


def main():
    s = make_session()
    results = {"ts": wall()}

    # Variant MINIMAL
    timings = {}
    res1 = flow(s, "MINIMAL", timings)
    res1["timings"] = timings
    results["MINIMAL"] = res1
    print(f"[MINIMAL] conversations={timings.get('conversations')}ms build={timings.get('build')}ms "
          f"payment={timings.get('payment')}ms -> {res1.get('http', {}).get('payment')} "
          f"{res1.get('payment_status')}", flush=True)

    # Variant PARALLEL
    timings = {}
    res2 = flow(s, "PARALLEL", timings)
    res2["timings"] = timings
    results["PARALLEL"] = res2
    print(f"[PARALLEL] conversations={timings.get('conversations')}ms build={timings.get('build')}ms "
          f"pm||pts={timings.get('payment_method||pickup_points')}ms pickup={timings.get('pickup_details')}ms "
          f"payment={timings.get('payment')}ms -> {res2.get('http', {}).get('payment')} "
          f"{res2.get('payment_status')}", flush=True)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano: {OUT}", flush=True)


if __name__ == "__main__":
    main()
