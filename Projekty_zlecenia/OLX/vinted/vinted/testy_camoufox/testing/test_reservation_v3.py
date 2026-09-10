# coding: utf-8
"""Test v3 - pelna sekwencja PUT z HAR (pickup_type + rate_uuid) i szukanie checksum.

Pytanie: w ktorym kroku transakcja dostaje status 220 (reserved) i skad bierze sie
checksum. Odwzorowuje sekwencje HAR: build -> PUT payment_method 12 -> PUT pickup_type:1
-> PUT rate_uuid -> szukaj "checksum" w odpowiedziach -> status po kazdym kroku.
"""
import json
import re
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
    try:
        j = r.json()
        t = j.get("transaction", {})
        return t.get("status"), t.get("is_reserved"), j
    except Exception:  # noqa: BLE001
        return None, None, r.text[:300]


def find_checksum(obj):
    """Rekurencyjnie szukaj klucza 'checksum' w obiekcie."""
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


# 1) Zywy tani item (PL, wysylka krajowa — rate_uuid musi byc dostepny)
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
st, res, _ = get_txn_status(txn_id)
print(f"[PO CONVERSATIONS] txn={txn_id} status={st} is_reserved={res}")
results["after_conversations"] = {"status": st, "is_reserved": res}
time.sleep(0.3)

# 3) Build
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
st, res, _ = get_txn_status(txn_id)
ch = find_checksum(build)
print(f"[PO BUILD] checkout={checkout_id} txn_status={st} is_reserved={res} checksum={ch}")
results["after_build"] = {"checkout_id": checkout_id, "txn_status": st, "is_reserved": res,
                          "checksum": ch}
time.sleep(0.3)

# Pobierz rate_uuid z build response (shipping_pickup_options -> pickup_methods)
rate_uuid = None
try:
    spo = build["checkout"]["components"].get("shipping_pickup_options", {})
    methods = spo.get("pickup_methods") or spo.get("shipping_pickup_options") or []
    print("[PICKUP OPTIONS KEYS]", list(spo.keys())[:20])
    results["pickup_options"] = json.dumps(spo)[:1500]
    if isinstance(methods, list):
        for mth in methods:
            u = (mth.get("rates") or [{}])[0].get("uuid") if isinstance(mth.get("rates"), list) else None
            if u:
                rate_uuid = u
                break
    if not rate_uuid:
        # szukaj 'rate_uuid' w calym buildzie
        mm = re.findall(r'"rate_uuid":"([^"]+)"', json.dumps(build))
        rate_uuid = mm[0] if mm else None
except Exception as e:  # noqa: BLE001
    print("[PICKUP ERR]", e)
print(f"[RATE_UUID] {rate_uuid}")

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
    pj = r.json()
    ch = find_checksum(pj)
except Exception:  # noqa: BLE001
    pj, ch = {}, []
st, res, _ = get_txn_status(txn_id)
print(f"[PUT payment_method] {r.status_code} txn_status={st} is_reserved={res} checksum={ch}")
results["put_payment_method"] = {"http": r.status_code, "txn_status": st, "is_reserved": res,
                                 "checksum": ch, "body": r.text[:800]}
time.sleep(0.3)

# 5) PUT pickup_type:1
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {},
    "shipping_address": {},
    "shipping_pickup_options": {"pickup_type": 1},
    "shipping_pickup_details": {},
}}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
try:
    pj = r.json()
    ch = find_checksum(pj)
except Exception:  # noqa: BLE001
    pj, ch = {}, []
st, res, _ = get_txn_status(txn_id)
print(f"[PUT pickup_type] {r.status_code} txn_status={st} is_reserved={res} checksum={ch}")
results["put_pickup_type"] = {"http": r.status_code, "txn_status": st, "is_reserved": res,
                              "checksum": ch, "body": r.text[:800]}
time.sleep(0.3)

# 6) PUT rate_uuid (jesli mamy)
if rate_uuid:
    r = s.put(put_url, json={"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {"rate_uuid": rate_uuid},
    }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    try:
        pj = r.json()
        ch = find_checksum(pj)
    except Exception:  # noqa: BLE001
        pj, ch = {}, []
    st, res, _ = get_txn_status(txn_id)
    print(f"[PUT rate_uuid] {r.status_code} txn_status={st} is_reserved={res} checksum={ch}")
    results["put_rate_uuid"] = {"http": r.status_code, "txn_status": st, "is_reserved": res,
                                "checksum": ch, "body": r.text[:800]}
else:
    results["put_rate_uuid"] = {"skipped": True}
time.sleep(0.5)

# 7) Cleanup
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"[CLEANUP] {r.status_code} {r.text[:150]}")
results["cleanup"] = {"http": r.status_code, "body": r.text[:300]}

(BASE_DIR / "wynik_reservation_test_v3.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_reservation_test_v3.json")
