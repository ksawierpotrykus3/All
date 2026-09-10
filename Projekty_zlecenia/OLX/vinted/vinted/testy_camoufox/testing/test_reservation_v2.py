# coding: utf-8
"""Powtorzenie testu rezerwacji z poprawnym parsowaniem statusu transakcji.

GET /transactions/{id} -> {"transaction": {"status": N, ...}}.
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
    try:
        j = r.json()
        t = j.get("transaction", {})
        return t.get("status"), j
    except Exception:  # noqa: BLE001
        return None, r.text[:500]


# 1) Zywy tani item
url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=5&currency=PLN")
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
results["after_conversations"] = {"status": st, "body": json.dumps(j)[:1500]}
time.sleep(0.3)

# 3) Build
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
st, _ = get_txn_status(txn_id)
print(f"[PO BUILD] checkout={checkout_id} txn_status={st}")
results["after_build"] = {"checkout_id": checkout_id, "txn_status": st,
                          "body": r.text[:4000]}
time.sleep(0.3)

# 4) PUT payment_method (Przelewy24, jak w HAR)
put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {"card_id": None, "pay_in_method_id": "12"},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": {},
}}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
st, _ = get_txn_status(txn_id)
print(f"[PO PUT payment_method] {r.status_code} txn_status={st}")
results["after_put_payment_method"] = {"http": r.status_code, "txn_status": st,
                                       "body": r.text[:1500]}
time.sleep(0.3)

# 5) Payment z poprawnym checksum z build (ale bez incognia i bez podania karty ->
#    Przelewy24 to bank transfer, moze nie zadziac bez incognia; ryzyko kontrolowane
#    bo metoda to przelew, nie karta)
import re
m = re.search(r'"checksum":"([^"]+)"', json.dumps(build))
checksum = m.group(1) if m else None
print(f"[CHECKSUM z build] {checksum}")
pay_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
pay_body = {
    "checksum": checksum or "",
    "payment_options": {
        "browser_info": {
            "language": "pl", "color_depth": 24, "java_enabled": False,
            "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
        }
    },
}
r = s.post(pay_url, json=pay_body, headers=H, impersonate=BrowserType.chrome146,
           timeout=30, allow_redirects=False)
print(f"[PAYMENT poprawny checksum, bez incognia] {r.status_code} {r.text[:600]}")
results["payment"] = {"http": r.status_code, "body": r.text[:2000]}
time.sleep(1)

# 6) Status po platnosci
st, body = get_txn_status(txn_id)
print(f"[PO PAYMENT] txn_status={st}")
results["after_payment"] = {"txn_status": st, "body": json.dumps(body)[:2500]}

# 7) Cleanup
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"[CLEANUP] {r.status_code} {r.text[:150]}")
results["cleanup"] = {"http": r.status_code, "body": r.text[:300]}

(BASE_DIR / "wynik_reservation_test_v2.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_reservation_test_v2.json")
