# coding: utf-8
"""Test v6 - pelny flow z pickup point: build -> GET nearby_pickup_points ->
PUT pickup_details {rate_uuid, point_code, point_uuid} -> payment -> status.

Endpoint punktow: api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}/nearby_pickup_points
"""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

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


def get_txn_status(txn_id):
    r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
              impersonate=BrowserType.chrome146, timeout=30)
    j = r.json()
    t = j.get("transaction", {})
    return t.get("status"), j


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


# 1) Zywy tani item
url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=8&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
target = None
for it in r.json().get("items", []):
    if it.get("status") != "sold" and it["user"]["id"] not in (3180346878,):
        target = it
        break
item_id = target["id"]
seller_id = target["user"]["id"]
print(f"[ITEM] {item_id} seller={seller_id} '{target.get('title','')[:40]}'")
results["item"] = {"id": item_id, "seller_id": seller_id}

# 2) Konwersacja + transakcja
r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
j = r.json()
conv_id = j["conversation"]["id"]
txn_id = j["conversation"]["transaction"]["id"]
st, _ = get_txn_status(txn_id)
print(f"[PO CONVERSATIONS] txn={txn_id} status={st}")
results["after_conversations"] = {"status": st}
time.sleep(0.3)

# 3) Build
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
lat = address.get("coordinates", {}).get("latitude")
lon = address.get("coordinates", {}).get("longitude")
st, _ = get_txn_status(txn_id)
print(f"[BUILD] checkout={checkout_id} status={st} rate_uuid={rate_uuid} so_id={so_id} "
      f"lat={lat} lon={lon}")
results["build"] = {"checkout_id": checkout_id, "txn_status": st, "checksum": ch,
                    "rate_uuid": rate_uuid, "shipping_order_id": so_id}
time.sleep(0.3)

# 4) PUT payment_method 12
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

# 5) GET nearby pickup points
if so_id:
    pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
               f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
    r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
    print(f"[PICKUP POINTS] {r.status_code} len={len(r.text)}")
    print(r.text[:1200])
    results["pickup_points"] = {"http": r.status_code, "body": r.text[:3000]}
    try:
        pp = r.json()
        # struktura: moze byc {"pickup_points":[...]} lub lista
        pts = pp.get("pickup_points") if isinstance(pp, dict) else pp
        if isinstance(pts, list) and pts:
            first = pts[0]
            pcode = first.get("code")
            puuid = first.get("uuid")
            print(f"[FIRST POINT] code={pcode} uuid={puuid} name={first.get('name')}")
            results["first_point"] = {"code": pcode, "uuid": puuid, "name": first.get("name")}
        else:
            print("[NO POINTS]", json.dumps(pp)[:800])
            results["first_point"] = None
    except Exception as e:  # noqa: BLE001
        print("[PTS PARSE ERR]", e)
        results["first_point"] = {"parse_error": str(e)}
else:
    print("[NO SHIPPING ORDER ID]")
    results["pickup_points"] = {"skipped": True}
time.sleep(0.3)

# 6) PUT pickup_details z rate_uuid + point
details = {}
if rate_uuid:
    details["rate_uuid"] = rate_uuid
fp = results.get("first_point") or {}
if fp.get("code"):
    details["point_code"] = fp["code"]
if fp.get("uuid"):
    details["point_uuid"] = fp["uuid"]
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
results["put_pickup_details"] = {"http": r.status_code, "details": details, "checksum": ch3,
                                 "body": r.text[:600]}
time.sleep(0.5)

# 7) Payment
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
print(f"[PAYMENT] {r.status_code} {r.text[:800]}")
results["payment"] = {"http": r.status_code, "body": r.text[:2500]}
time.sleep(2)

# 8) Status
st, jb = get_txn_status(txn_id)
t = jb.get("transaction", {})
print(f"[PO PAYMENT] txn_status={st}")
print(f"  is_reserved={t.get('is_reserved')} purchase_id={t.get('purchase_id')} "
      f"status_updated_at={t.get('status_updated_at')}")
results["after_payment"] = {"txn_status": st, "is_reserved": t.get("is_reserved"),
                            "purchase_id": t.get("purchase_id"),
                            "status_updated_at": t.get("status_updated_at"),
                            "body": json.dumps(jb)[:2000]}

# 9) Cleanup
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"[CLEANUP] {r.status_code} {r.text[:150]}")
results["cleanup"] = {"http": r.status_code, "body": r.text[:300]}

(BASE_DIR / "wynik_reservation_test_v6.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_reservation_test_v6.json")
