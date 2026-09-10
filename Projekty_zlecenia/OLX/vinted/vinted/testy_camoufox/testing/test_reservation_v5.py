# coding: utf-8
"""Test v5 - pelny flow jak frontend: build -> PUT payment_method 12 ->
PUT pickup_options pickup_type -> PUT pickup_details {rate_uuid, point_code, point_uuid}
-> POST payment (poprawny checksum, bez incognia) -> status (czy 220?).

Zrodla:
- 0yhhqgn4m5t2_.js: shipping_pickup_options:{pickup_type}, shipping_pickup_details:{rate_uuid,point_code,point_uuid}
- 0m6z: shippingPoint:{uuid,code,rate_uuid,...} w shipping_pickup_details
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

# 3) Build -> checkout, checksum, rate_uuid, point
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
ch = find_checksum(build)
st, _ = get_txn_status(txn_id)
print(f"[PO BUILD] checkout={checkout_id} status={st} checksum={ch}")

# wyciagnij shipping details z builda
pd = build.get("checkout", {}).get("components", {}).get("shipping_pickup_details", {})
pd_inner = pd.get("pickup_details", {})
rate_uuid = pd_inner.get("selected_rate_uuid")
spoint = pd_inner.get("shipping_point") or {}
point_code = spoint.get("code")
point_uuid = spoint.get("uuid")
spo = build.get("checkout", {}).get("components", {}).get("shipping_pickup_options", {})
selected_pickup = spo.get("selected_pickup_option")
print(f"[BUILD] rate_uuid={rate_uuid} point_code={point_code} point_uuid={point_uuid} "
      f"selected_pickup_option={selected_pickup}")
results["after_build"] = {"checkout_id": checkout_id, "txn_status": st, "checksum": ch,
                          "rate_uuid": rate_uuid, "point_code": point_code,
                          "point_uuid": point_uuid, "selected_pickup_option": selected_pickup}
time.sleep(0.3)

# 4) PUT payment_method 12
put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"


def put(comps):
    r = s.put(put_url, json={"components": comps}, headers=H,
              impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    try:
        pj = r.json()
        chx = find_checksum(pj)
    except Exception:  # noqa: BLE001
        pj, chx = {}, []
    return r.status_code, pj, chx


http, pj, ch2 = put({
    "additional_service": {},
    "payment_method": {"card_id": None, "pay_in_method_id": "12"},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": {},
})
st, _ = get_txn_status(txn_id)
print(f"[PUT payment_method] {http} status={st} checksum={ch2}")
results["put_payment_method"] = {"http": http, "txn_status": st, "checksum": ch2}
time.sleep(0.3)

# 5) PUT pickup_options pickup_type
pt = selected_pickup or 2
http, pj, ch3 = put({
    "additional_service": {},
    "payment_method": {},
    "shipping_address": {},
    "shipping_pickup_options": {"pickup_type": pt},
    "shipping_pickup_details": {},
})
st, _ = get_txn_status(txn_id)
print(f"[PUT pickup_type={pt}] {http} status={st} checksum={ch3}")
results["put_pickup_options"] = {"http": http, "pickup_type": pt, "txn_status": st, "checksum": ch3}
time.sleep(0.3)

# 6) PUT pickup_details rate_uuid + point
details = {}
if rate_uuid:
    details["rate_uuid"] = rate_uuid
if point_code:
    details["point_code"] = point_code
if point_uuid:
    details["point_uuid"] = point_uuid
http, pj, ch4 = put({
    "additional_service": {},
    "payment_method": {},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": details,
})
st, _ = get_txn_status(txn_id)
print(f"[PUT pickup_details {json.dumps(details)}] {http} status={st} checksum={ch4}")
results["put_pickup_details"] = {"http": http, "details": details, "txn_status": st, "checksum": ch4}
time.sleep(0.5)

# 7) POST payment z poprawnym checksum (najswiezszy), bez incognia
checksum = (ch4 or ch3 or ch2 or ch)[0] if (ch4 or ch3 or ch2 or ch) else ""
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
results["payment"] = {"http": r.status_code, "body": r.text[:2000]}
time.sleep(2)

# 8) Status po platnosci
st, jb = get_txn_status(txn_id)
t = jb.get("transaction", {})
print(f"[PO PAYMENT] txn_status={st}")
print(f"  is_reserved={t.get('is_reserved')} purchase_id={t.get('purchase_id')} "
      f"status_updated_at={t.get('status_updated_at')} debit_processed_at={t.get('debit_processed_at')}")
results["after_payment"] = {"txn_status": st, "is_reserved": t.get("is_reserved"),
                            "purchase_id": t.get("purchase_id"),
                            "status_updated_at": t.get("status_updated_at"),
                            "body": json.dumps(jb)[:2500]}

# 9) Cleanup
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"[CLEANUP] {r.status_code} {r.text[:150]}")
results["cleanup"] = {"http": r.status_code, "body": r.text[:300]}

(BASE_DIR / "wynik_reservation_test_v5.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_reservation_test_v5.json")
