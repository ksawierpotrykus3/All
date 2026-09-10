# coding: utf-8
"""Rezerwacja itemu 9807925466 (aneta_003) przez curl_cffi - pelny flow do payment.
Bez cleanup - obserwacja blokady itemu w przegladarce po payment.
"""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

ITEM = 9807925466
SELLER = 161574001
results = {}

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


def get_txn_status(txn_id):
    r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
              impersonate=BrowserType.chrome146, timeout=30)
    t = r.json().get("transaction", {})
    return t.get("status"), t


# 1) POST /conversations (idempotentne)
r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(ITEM), "opposite_user_id": SELLER},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
j = r.json()
conv_id = j["conversation"]["id"]
txn_id = j["conversation"]["transaction"]["id"]
print(f"[CONVERSATIONS] conv={conv_id} txn={txn_id}")
results["conversations"] = {"conv_id": conv_id, "txn_id": txn_id}
time.sleep(0.3)

# 2) Build
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
ch = find_checksum(build)
comps = build.get("checkout", {}).get("components", {})
pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
rate_uuid = pd_inner.get("selected_rate_uuid")
so_id = comps.get("shipping_address", {}).get("shipping_order_id")
address = comps.get("shipping_address", {}).get("address", {})
coords = address.get("coordinates") or {}
lat, lon = coords.get("latitude"), coords.get("longitude")
print(f"[BUILD] checkout={checkout_id} rate_uuid={rate_uuid} so_id={so_id}")
results["build"] = {"checkout_id": checkout_id, "checksum": ch, "rate_uuid": rate_uuid,
                    "shipping_order_id": so_id, "http": r.status_code}
time.sleep(0.3)

# 3) PUT payment_method 12
put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {"card_id": None, "pay_in_method_id": "12"},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": {},
}}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
try:
    ch2 = find_checksum(r.json())
except Exception:  # noqa: BLE001
    ch2 = []
print(f"[PUT payment_method] {r.status_code} checksum={ch2}")
results["put_payment_method"] = {"http": r.status_code, "checksum": ch2}
time.sleep(0.3)

# 4) GET nearby pickup points
point = None
if so_id:
    pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
               f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
    r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
    pp = r.json()
    spoints = (pp or {}).get("shipping_points") or []
    sug = (pp or {}).get("suggested_shipping_point_code")
    print(f"[PICKUP POINTS] {r.status_code} n={len(spoints)} sug={sug}")
    for cand in spoints:
        sp_inner = cand.get("point", {})
        if sug and sp_inner.get("code") == sug:
            point = sp_inner
            break
    if point is None:
        for cand in spoints:
            sp_inner = cand.get("point", {})
            if rate_uuid and sp_inner.get("rate_uuid") == rate_uuid:
                point = sp_inner
                break
    if point is None and spoints:
        point = spoints[0].get("point", {})
    if point:
        print(f"  POINT: code={point.get('code')} rate_uuid={point.get('rate_uuid')}")
    results["pickup_points"] = {"http": r.status_code, "chosen": point and {
        "code": point.get("code"), "uuid": point.get("uuid"),
        "rate_uuid": point.get("rate_uuid")}}
    time.sleep(0.3)

# 5) PUT pickup_details
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
print(f"[PUT pickup_details] {json.dumps(details)}")
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": details,
}}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
try:
    ch3 = find_checksum(r.json())
except Exception:  # noqa: BLE001
    ch3 = []
print(f"  {r.status_code} checksum={ch3}")
results["put_pickup_details"] = {"http": r.status_code, "details": details, "checksum": ch3}
time.sleep(0.5)

# 6) Payment
checksum = (ch3 or ch2 or ch)[0] if (ch3 or ch2 or ch) else ""
pay_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
pay_body = {
    "checksum": checksum,
    "payment_options": {
        "browser_info": {
            "language": "pl", "color_depth": 24, "java_enabled": False,
            "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
        }
    },
}
r = s.post(pay_url, json=pay_body, headers=H, impersonate=BrowserType.chrome146,
           timeout=30, allow_redirects=False)
print(f"[PAYMENT] {r.status_code} {r.text[:500]}")
results["payment"] = {"http": r.status_code, "body": r.text[:2000]}
time.sleep(2)

# 7) Status
st, t = get_txn_status(txn_id)
print(f"[PO PAYMENT] txn_status={st} is_reserved={t.get('is_reserved')} "
      f"purchase_id={t.get('purchase_id')}")
results["after_payment"] = {"txn_status": st, "is_reserved": t.get("is_reserved"),
                            "purchase_id": t.get("purchase_id"),
                            "status_updated_at": t.get("status_updated_at")}

(BASE_DIR / "wynik_rez_9807925466.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_rez_9807925466.json (BEZ cleanup - item powinien byc zarezerwowany)")
