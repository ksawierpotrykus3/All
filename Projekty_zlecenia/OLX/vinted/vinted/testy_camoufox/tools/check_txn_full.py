# coding: utf-8
"""Pelny obiekt transakcji 21905860558 - szukamy pol wygasniecia / akcji zwolnienia."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
TXN = 21905860558

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
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

r = s.get(f"https://www.vinted.pl/api/v2/transactions/{TXN}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out = [f"http={r.status_code}"]
if r.status_code == 200:
    t = r.json().get("transaction", {})
    # plaskie pola
    out.append("KEYS:")
    for k, v in t.items():
        if not isinstance(v, (dict, list)):
            out.append(f"  {k} = {v}")
    for key in ("payment", "purchase", "shipping", "status_tracking", "timestamps"):
        if isinstance(t.get(key), dict):
            out.append(f"--- {key} ---")
            for k, v in t[key].items():
                if not isinstance(v, (dict, list)):
                    out.append(f"  {k} = {v}")
    out.append(f"--- ACTIONS: {t.get('actions')} ---")
Path(BASE_DIR / "txn_full_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> txn_full_out.txt")
