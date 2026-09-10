# coding: utf-8
"""Czy DELETE /conversations na transakcji status=1 usuwa transakcje i odblokowuje item?"""
import json
import time
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

# 1) item + konwersacja
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
out.append(f"[ITEM] {item_id}")

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
cj = r.json()["conversation"]
txn_id = cj["transaction"]["id"]
conv_id = cj["id"]
out.append(f"[TXN] {txn_id} conv={conv_id} status={cj['transaction']['status']}")

# item przed
r = s.get(f"https://www.vinted.pl/api/v2/items/{item_id}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"ITEM przed cleanup: http={r.status_code}")

# DELETE conv
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{conv_id}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
out.append(f"DELETE conv: {r.status_code} {r.text[:150]}")
time.sleep(1)

# transakcja po
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"TXN po cleanup: http={r.status_code}")

# item po
r = s.get(f"https://www.vinted.pl/api/v2/items/{item_id}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"ITEM po cleanup: http={r.status_code}")
if r.status_code == 200:
    out.append(f"  status={r.json().get('item', {}).get('status')}")

(BASE_DIR / "cleanup_status1_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> cleanup_status1_out.txt")
