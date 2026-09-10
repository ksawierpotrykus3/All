# coding: utf-8
"""Test: czy POST /checkout/payment ustawia status transakcji 220 (reserved).

Bezpieczny: wysylamy PUSTY checksum -> gwarantowany TransactionChecksumMismatch
(bez obciazenia karty). Obserwujemy czy status przechodzi 1 -> 220.
Nastepnie cleanup: DELETE /conversations/{id}.
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

# 1) Tani zywy item z katalogu
url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=5&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
data = r.json()
items = data.get("items", [])
target = None
for it in items:
    if it.get("status") != "sold" and it["user"]["id"] not in (3180346878,):
        target = it
        break
if not target:
    print("Brak zywego itemu. Koniec.")
    raise SystemExit

item_id = target["id"]
seller_id = target["user"]["id"]
print(f"[ITEM] {item_id} seller={seller_id} '{target.get('title','')[:50]}' "
      f"cena={target.get('price',{}).get('amount')}")
results["item"] = {"id": item_id, "seller_id": seller_id, "title": target.get("title")}

# 2) Utworz transakcje
body = {"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id}
r = s.post("https://www.vinted.pl/api/v2/conversations", json=body, headers=H,
           impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
j = r.json()
conv = j.get("conversation", {})
txn = conv.get("transaction") or {}
txn_id = txn.get("id")
conv_id = conv.get("id")
print(f"[CONVERSATIONS] {r.status_code} txn={txn_id} status={txn.get('status')}")
results["create_conversation"] = {"status": r.status_code, "txn": txn_id, "conv": conv_id,
                                  "txn_status": txn.get("status")}

# 3) Build
body = {"purchase_items": [{"id": txn_id, "type": "transaction"}]}
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build", json=body, headers=H,
           impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
print(f"[BUILD] {r.status_code} checkout={checkout_id}")
results["build"] = {"status": r.status_code, "checkout_id": checkout_id,
                    "body": r.text[:5000]}
# szukamy checksum w odpowiedzi build
import re as _re
m = _re.search(r'checksum[^,]{0,120}', r.text)
if m:
    print(f"[BUILD] checksum-fragment: {m.group(0)[:150]}")
time.sleep(0.5)

# 4) Status transakcji po buildzie
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
st1 = r.json().get("status")
print(f"[TXN po buildzie] status={st1}")
results["txn_after_build"] = st1

# 5) PUT checkout z metoda platnosci (Przelewy24 jak w HAR)
put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
put_body = {"components": {
    "additional_service": {},
    "payment_method": {"card_id": None, "pay_in_method_id": "12"},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": {},
}}
r = s.put(put_url, json=put_body, headers=H, impersonate=BrowserType.chrome146,
          timeout=30, allow_redirects=False)
print(f"[PUT payment_method] {r.status_code}")
results["put_payment_method"] = {"status": r.status_code, "body": r.text[:1500]}
time.sleep(0.5)

# 6) POST /checkout/payment z PUSTYM checksum (bezpieczny - gwarantowany blad, brak platnosci)
pay_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
pay_body = {
    "checksum": "",
    "payment_options": {
        "browser_info": {
            "language": "pl", "color_depth": 24, "java_enabled": False,
            "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120,
        }
    },
}
r = s.post(pay_url, json=pay_body, headers=H, impersonate=BrowserType.chrome146,
           timeout=30, allow_redirects=False)
print(f"[PAYMENT pusty checksum] {r.status_code} {r.text[:800]}")
results["payment"] = {"status": r.status_code, "body": r.text[:1500]}
time.sleep(1)

# 7) Status transakcji po probie platnosci
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
st2 = r.json().get("status")
print(f"[TXN po platnosci] status={st2}  (1 -> 220 = rezerwacja przy platnosci)")
results["txn_after_payment"] = st2

# 8) Cleanup
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"[CLEANUP] {r.status_code} {r.text[:200]}")
results["cleanup"] = {"status": r.status_code, "body": r.text[:300]}

(BASE_DIR / "wynik_reservation_payment_test.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_reservation_payment_test.json")
