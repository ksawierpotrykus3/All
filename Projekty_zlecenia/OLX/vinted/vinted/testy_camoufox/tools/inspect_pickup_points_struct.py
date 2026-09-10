# coding: utf-8
"""Zbadaj strukture odpowiedzi nearby_pickup_points - wynik do pliku."""
import json
import re
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

out = []

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
out.append(f"[ITEM] {item_id} seller={seller_id}")

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
cj = r.json()["conversation"]
txn_id = cj["transaction"]["id"]
conv_id = cj["id"]
out.append(f"[TXN] {txn_id} conv={conv_id}")

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
out.append(f"[BUILD] rate_uuid={rate_uuid} so_id={so_id} lat={lat} lon={lon}")

pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
           f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
out.append(f"[PICKUP POINTS] http={r.status_code}")
pp = r.json()
out.append(f"TOP KEYS: {list(pp.keys())}")
rates = pp.get("shipping_rates", [])
out.append(f"RATES: {len(rates)}")
for i, rate in enumerate(rates[:3]):
    rk = list(rate.keys())
    out.append(f" RATE[{i}] KEYS: {rk}")
    if "pickup_points" in rate:
        pts = rate["pickup_points"]
        out.append(f"  pickup_points: {len(pts)}")
        if pts:
            out.append("  first point: " + json.dumps(pts[0], ensure_ascii=False)[:1500])
# czy gdzies jest 'code' / 'point'
txt = json.dumps(pp)
for kw in ["pickup_points", "point_code", '"code"', "points"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), txt)][:5]
    out.append(f"kw={kw} at {idxs}")

try:
    s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    out.append("[CLEANUP done]")
except Exception as e:  # noqa: BLE001
    out.append(f"[CLEANUP err] {e}")

(BASE_DIR / "inspect_pickup_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> inspect_pickup_out.txt")
