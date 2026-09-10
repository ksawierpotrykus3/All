# coding: utf-8
"""Proba odblokowania transakcji przez POST payment/failure."""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

CHECKOUT = "vsOqiMvvv0jPk91p39MXq"
TXN = 21905860558
CONV = 24722169871

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

# 1) POST payment/failure
url = f"https://www.vinted.pl/api/v2/purchases/{CHECKOUT}/checkout/payment/failure"
r = s.post(url, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
out.append(f"payment/failure -> {r.status_code} {r.text[:400]}")
time.sleep(1)

# 2) status transakcji
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{TXN}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
t = r.json().get("transaction", {})
out.append(f"STATUS={t.get('status')} ACTIONS={t.get('available_actions')}")
time.sleep(1)

# 3) proba DELETE conversations
r = s.delete(f"https://www.vinted.pl/api/v2/conversations/{CONV}", headers=H,
             impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
out.append(f"DELETE conv -> {r.status_code} {r.text[:300]}")

# 4) GET checkout - zobacz co zwraca (czy jest purchase_id / status)
r = s.get(f"https://www.vinted.pl/api/v2/purchases/{CHECKOUT}/checkout", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"GET checkout -> {r.status_code} {r.text[:1500]}")

(BASE_DIR / "unlock_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> unlock_out.txt")
