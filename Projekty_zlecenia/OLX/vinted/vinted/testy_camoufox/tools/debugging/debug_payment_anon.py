# coding: utf-8
"""Debug: co dokladnie zwraca payment przy rotacji anon_id?"""
import json
import uuid
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"

anon_id = str(uuid.uuid4())
print(f"anon_id: {anon_id}")

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
H = {"x-csrf-token": CSRF, "x-anon-id": anon_id}

# item
r = s.get("https://www.vinted.pl/api/v2/catalog/items"
          "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
          headers=H, impersonate=BrowserType.chrome146, timeout=30)
it = r.json().get("items", [])[0]
item_id, seller_id = it["id"], it["user"]["id"]
print(f"item {item_id}")

# conversations
r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
txn = r.json()["conversation"]["transaction"]["id"]
print(f"txn {txn}")

# build
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"build HTTP: {r.status_code}")
print(f"build body (2000 znakow): {r.text[:2000]}")
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
print(f"checkout_id: {checkout_id}")
print(f"checkout keys: {list(build.get('checkout', {}).keys())}")

# PUT payment_method
r = s.put(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout",
          json={"components": {
              "additional_service": {},
              "payment_method": {"card_id": None, "pay_in_method_id": "12"},
              "shipping_address": {},
              "shipping_pickup_options": {},
              "shipping_pickup_details": {},
          }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"PUT payment_method: {r.status_code}")

# PUT pickup_details
comps = build.get("checkout", {}).get("components", {})
pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
rate_uuid = pd_inner.get("selected_rate_uuid")
so_id = comps.get("shipping_address", {}).get("shipping_order_id")
addr = comps.get("shipping_address", {}).get("address", {})
coords = addr.get("coordinates") or {}

pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
           f"/nearby_pickup_points?country_code=PL&latitude={coords.get('latitude')}&longitude={coords.get('longitude')}")
r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
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

details = {"rate_uuid": rate_uuid}
if point:
    if point.get("code"):
        details["point_code"] = point["code"]
    if point.get("uuid"):
        details["point_uuid"] = point["uuid"]
    if point.get("rate_uuid"):
        details["rate_uuid"] = point["rate_uuid"]

r = s.put(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout",
          json={"components": {
              "additional_service": {},
              "payment_method": {},
              "shipping_address": {},
              "shipping_pickup_options": {},
              "shipping_pickup_details": details,
          }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"PUT pickup_details: {r.status_code}")

# payment - PELNY WYNIK
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
ch = find_checksum(build)

r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
           json={"checksum": ch, "payment_options": {"browser_info": {
               "language": "pl", "color_depth": 24, "java_enabled": False,
               "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"\n=== PAYMENT ===")
print(f"HTTP: {r.status_code}")
print(f"Body: {r.text[:2000]}")
print(f"Headers: {dict(r.headers)}")
