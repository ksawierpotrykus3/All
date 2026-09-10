# coding: utf-8
"""PEŁNY ŁAŃCUCH przez curl_cffi na nowej transakcji (żywy item z katalogu):
conversations -> build -> GET transaction (status 220?) -> PUT checkout -> anuluj.
"""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"

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

# 1) Nowa transakcja z poprzedniego testu
txn_id = 21905766891
item_id = 9824029893

# 2) BUILD na nowej transakcji
body = {"purchase_items": [{"id": txn_id, "type": "transaction"}]}
r = s.post(BUILD_URL, json=body, headers=H, impersonate=BrowserType.chrome146,
           timeout=30, allow_redirects=False)
print(f"[BUILD] {r.status_code}")
results["build"] = {"status": r.status_code, "body": r.text[:2000]}
checkout_id = None
try:
    build = r.json()
    checkout_id = build.get("checkout", {}).get("id")
    print(f"[BUILD] checkout_id={checkout_id}")
    print(f"[BUILD] keys={list(build.keys())}")
    print(f"[BUILD] components={list(build.get('checkout', {}).get('components', {}).keys())}")
except Exception as e:  # noqa: BLE001
    print(f"[BUILD] parse error: {e} raw={r.text[:800]}")
    results["build_parse_error"] = repr(e)

time.sleep(1)

# 3) Status transakcji po buildzie
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
print(f"[GET transaction] {r.status_code}")
results["transaction_status"] = {"status": r.status_code, "body": r.text[:600]}
try:
    tj = r.json()
    print(f"  status={tj.get('status')} id={tj.get('id')}")
except Exception as e:  # noqa: BLE001
    print(f"  parse error: {e}")

# 4) PUT checkout (puste komponenty)
if checkout_id:
    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    put_body = {"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {},
    }}
    r = s.put(put_url, json=put_body, headers=H, impersonate=BrowserType.chrome146,
              timeout=30, allow_redirects=False)
    print(f"[PUT checkout] {r.status_code} {r.text[:600]}")
    results["put_checkout"] = {"status": r.status_code, "body": r.text[:1000]}
    time.sleep(1)

# 5) ANULOWANIE transakcji (zwolnij item) - proba DELETE
for method, url in [
    ("DELETE", f"https://www.vinted.pl/api/v2/transactions/{txn_id}"),
    ("DELETE", f"https://www.vinted.pl/api/v2/conversations/24722073450"),
]:
    try:
        r = s.request(method, url, headers=H, impersonate=BrowserType.chrome146,
                      timeout=30, allow_redirects=False)
        print(f"[{method} {url.split('/')[-1]}] {r.status_code} {r.text[:400]}")
        results[f"cancel_{method}_{url.split('/')[-1]}"] = {"status": r.status_code, "body": r.text[:600]}
        if r.status_code < 400:
            break
    except Exception as e:  # noqa: BLE001
        print(f"[{method}] error: {e}")

(BASE_DIR / "wynik_full_chain_live.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_full_chain_live.json")
