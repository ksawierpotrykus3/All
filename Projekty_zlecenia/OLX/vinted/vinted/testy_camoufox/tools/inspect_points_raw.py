# coding: utf-8
"""Surowo: pierwsze 2 elementy shipping_points z odpowiedzi pickup points."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

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

out = []
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

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
cj = r.json()["conversation"]
txn_id = cj["transaction"]["id"]
conv_id = cj["id"]

r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
comps = build["checkout"]["components"]
pd_inner = comps["shipping_pickup_details"].get("pickup_details", {})
rate_uuid = pd_inner.get("selected_rate_uuid")
so_id = comps["shipping_address"]["shipping_order_id"]
addr = comps["shipping_address"]["address"]
lat, lon = addr["coordinates"]["latitude"], addr["coordinates"]["longitude"]

pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
           f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
pp = r.json()
out.append(f"TOP KEYS: {list(pp.keys())}")
spoints = pp.get("shipping_points", [])
out.append(f"N points: {len(spoints)}")
for i, sp in enumerate(spoints[:2]):
    out.append(f"POINT[{i}] RAW: " + json.dumps(sp, ensure_ascii=False)[:2000])
out.append("SUGGESTED: " + json.dumps(pp.get("suggested_shipping_point_code")))

s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
         impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)

(BASE_DIR / "inspect_points_raw.txt").write_text("\n".join(out), encoding="utf-8")
print("OK")
