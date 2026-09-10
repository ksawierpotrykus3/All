# coding: utf-8
"""Hybryda: Camoufox przechodzi DataDome na stronie itemu, potem curl_cffi robi checkout.

Hipoteza: wizyta w przegladarce rozwiazuje challenge DataDome, a potem czysty
curl_cffi moze wykonac checkout/build bez blokady.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

results = {"steps": []}

# --- 1) Camoufox: wejsc na strone itemu (rozwiazanie DataDome) ---
with Camoufox(persistent_context=True, headless=True,
              user_data_dir=str(PROFILE_DIR), os="windows",
              fingerprint_preset=True, humanize=True) as ctx:
    page = ctx.new_page()
    page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    # wejdz na dowolny item zeby wyzwolic requesty api
    page.goto("https://www.vinted.pl/catalog/44-kobiety?order=newest_first",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    cookies = ctx.cookies()
    print(f"Camoufox: {len(cookies)} cookies")

# --- 2) curl_cffi z cookies z przegladarki ---
s = cr.Session()
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
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

# swiezy item
r = s.get("https://www.vinted.pl/api/v2/catalog/items"
          "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
          headers=H, impersonate=BrowserType.chrome146, timeout=30)
it = r.json().get("items", [])[0]
item_id, seller_id = it["id"], it["user"]["id"]
print(f"item {item_id} seller={seller_id}")

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
txn = r.json()["conversation"]["transaction"]["id"]
print(f"conversations http={r.status_code} txn={txn}")

r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"build http={r.status_code}")
if r.status_code != 200:
    print(f"build body: {r.text[:300]}")
    results["build_status"] = r.status_code
    results["build_body_head"] = r.text[:300]
else:
    results["build_status"] = 200
    results["checkout_id"] = r.json().get("checkout", {}).get("id")
    print(f"checkout_id={results['checkout_id']}")

(BASE_DIR / "wynik_hybryda_datadome.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Zapisano: wynik_hybryda_datadome.json")
