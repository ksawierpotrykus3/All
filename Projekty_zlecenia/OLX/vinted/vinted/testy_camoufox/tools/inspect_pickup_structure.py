# coding: utf-8
"""Sprawdz strukture shipping_pickup_options / shipping_pickup_details w build response."""
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
print(f"[ITEM] {item_id} seller={seller_id} country={target['user'].get('country_code')}")
print(f"[ITEM] currency={target.get('currency')} total_item_price={target.get('total_item_price')}")

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
j = r.json()
txn_id = j["conversation"]["transaction"]["id"]
conv_id = j["conversation"]["id"]
print(f"[TXN] {txn_id} conv={conv_id}")

r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
checkout = build.get("checkout", {})
comps = checkout.get("components", {})
print("\n=== COMPONENT KEYS ===", list(comps.keys()))
print("\n=== CHECKOUT TOP KEYS ===", list(checkout.keys()))

for key in ["shipping_pickup_options", "shipping_pickup_details", "shipping_address",
            "shipping_contact", "payment_method", "additional_service", "pay_button_v2"]:
    if key in comps:
        print(f"\n=== {key} ===")
        print(json.dumps(comps[key], ensure_ascii=False)[:2500])

# cleanup
s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
         impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print("\n[CLEANUP done]")
