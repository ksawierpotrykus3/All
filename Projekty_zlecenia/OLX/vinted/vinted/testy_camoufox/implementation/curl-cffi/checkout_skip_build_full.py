# coding: utf-8
"""checkout_skip_build_full.py — PELNY flow BEZ checkout/build (conversations -> PUT -> payment).

Odkrycie: transakcja ma purchase_id w conversations (gdy checkout istnial), a PUT na tym
purchase_id dziala (200) BEZ builda. Test: czy da sie dojsc do bramki platnosci w 100%
bez endpointu checkout/build (glownego, ktory DataDome blokuje najczesciej).

Mierzy czas do BRAMKI (payment pending + redirect). Payment NIE jest finalizowany
(to samo co bench_curl_gateway: pending -> bramka, bez potwierdzenia).
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_skip_build_full.json"

ITEM_ID = 9807925466
SELLER_ID = 161574001

results = {"steps": []}
T0 = time.monotonic()


def now_ms():
    return round((time.monotonic() - T0) * 1000, 1)


def step(name, **extra):
    e = {"step": name, "elapsed_ms": now_ms()}
    e.update(extra)
    results["steps"].append(e)
    print(f"[{now_ms():>9.1f} ms] {name} {extra}", flush=True)


def find_checksum(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                return v
            r = find_checksum(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_checksum(v)
            if r:
                return r
    return None


def session_from(cookies):
    s = cr.Session()
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


s = session_from(json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")))
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

# 1. conversations -> purchase_id (bez builda!)
step("conversations")
r = s.post(
    "https://www.vinted.pl/api/v2/conversations",
    json={"initiator": "buy", "item_id": str(ITEM_ID), "opposite_user_id": SELLER_ID},
    headers=H, impersonate="chrome146", timeout=30, allow_redirects=False,
)
conv = r.json().get("conversation", {})
txn = conv.get("transaction") or {}
purchase_id = txn.get("purchase_id")
txn_id = txn.get("id")
step("conversations done", http=r.status_code, txn=txn_id,
     purchase_id=purchase_id, status=txn.get("status"))
if not purchase_id:
    step("BRAK purchase_id — nowa transakcja, build konieczny")
    results["result"] = {"error": "brak purchase_id (nowa transakcja)"}
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0)

put_url = f"https://www.vinted.pl/api/v2/purchases/{purchase_id}/checkout"
referer = f"https://www.vinted.pl/checkout?purchase_id={purchase_id}"

# 2. PUT payment_method — response zwraca komponenty (so_id, coords, selected_rate_uuid)
step("put payment_method")
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {"card_id": None, "pay_in_method_id": "12"},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": {},
}}, headers={**H, "referer": referer}, impersonate="chrome146",
    timeout=30, allow_redirects=False)
j = r.json() if r.status_code == 200 else {}
comps = j.get("checkout", {}).get("components", {})
ch_pm = find_checksum(j)
so_id = comps.get("shipping_address", {}).get("shipping_order_id")
addr = comps.get("shipping_address", {}).get("address", {})
coords = addr.get("coordinates") or {}
lat, lon = coords.get("latitude"), coords.get("longitude")
pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
rate_uuid = pd_inner.get("selected_rate_uuid")
step("put payment_method done", http=r.status_code, checksum=bool(ch_pm),
     so_id=so_id, lat=lat, lon=lon, rate_uuid=rate_uuid)
if r.status_code != 200 or not ch_pm:
    results["result"] = {"error": "PUT payment_method", "http": r.status_code,
                         "body": r.text[:300]}
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(1)

# 3. GET pickup points
point = {}
if so_id and lat and lon:
    step("pickup_points")
    pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
               f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
    rp = s.get(pts_url, headers={**H, "referer": referer}, impersonate="chrome146", timeout=30)
    pp = rp.json() if rp.status_code == 200 else {}
    spoints = (pp or {}).get("shipping_points") or []
    sug = (pp or {}).get("suggested_shipping_point_code")
    for cand in spoints:
        sp = cand.get("point", {})
        if sug and sp.get("code") == sug:
            point = sp
            break
    if not point and rate_uuid:
        for cand in spoints:
            sp = cand.get("point", {})
            if sp.get("rate_uuid") == rate_uuid:
                point = sp
                break
    if not point and spoints:
        point = spoints[0].get("point", {})
    step("pickup_points done", http=rp.status_code, n=len(spoints), sug=sug,
         point_code=point.get("code"))

# 4. PUT pickup_details
details = {}
if rate_uuid:
    details["rate_uuid"] = rate_uuid
if point:
    if point.get("code"):
        details["point_code"] = point["code"]
    if point.get("uuid"):
        details["point_uuid"] = point["uuid"]
step("put pickup_details", details=bool(details))
r2 = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": details,
}}, headers={**H, "referer": referer}, impersonate="chrome146",
    timeout=30, allow_redirects=False)
ch_pickup = find_checksum(r2.json()) if r2.status_code == 200 else None
step("put pickup_details done", http=r2.status_code, checksum=bool(ch_pickup))

final_checksum = ch_pickup or ch_pm
if not final_checksum:
    results["result"] = {"error": "brak checksum", "http": r2.status_code}
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(1)

# 5. POST payment -> BRAMKA (bez builda!)
step("payment")
r3 = s.post(f"{put_url}/payment", json={
    "checksum": final_checksum,
    "payment_options": {"browser_info": {
        "language": "pl", "color_depth": 24, "java_enabled": False,
        "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
    }},
}, headers={**H, "referer": referer}, impersonate="chrome146",
    timeout=30, allow_redirects=False)
pj = r3.json() if r3.status_code == 200 else {}
pay_status = (pj.get("payment") or {}).get("status")
nav = (pj.get("action") or {}).get("parameters") or {}
redirect_url = nav.get("url", "")
success = r3.status_code == 200 and pay_status == "pending" and bool(redirect_url)
step("PAYMENT -> BRAMKA" if success else "PAYMENT (BLAD)", http=r3.status_code,
     payment_status=pay_status, redirect=redirect_url[:100], success=success)
results["result"] = {
    "purchase_id": purchase_id, "txn": txn_id,
    "http": r3.status_code, "payment_status": pay_status,
    "redirect_url": redirect_url[:200], "success": success,
    "to_gateway_ms": now_ms() if success else None,
    "body": r3.text[:300] if r3.status_code != 200 else None,
}

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {OUT}", flush=True)
print(f"BEZ BUILDA -> BRAMKA: {success} ({now_ms():.0f} ms)", flush=True)
