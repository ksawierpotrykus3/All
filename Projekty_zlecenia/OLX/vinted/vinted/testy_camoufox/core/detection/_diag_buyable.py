# coding: utf-8
"""Ktore pola w katalogu wskazuja, ze item ma przycisk 'Kup teraz' (buyable)."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

s = cr.Session()
for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({"accept": "application/json", "content-type": "application/json",
                  "locale": "pl-PL", "origin": "https://www.vinted.pl"})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}
url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?price_to=100&order=newest_first&page=1&per_page=50&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
items = r.json().get("items", [])
# wypisz klucze pierwszego itemu + szukaj flag typu buy/can_purchase
print("item keys:", list(items[0].keys()))
for it in items[:10]:
    # zbierz klucze z 'buy', 'purchase', 'can', 'available', 'reserved'
    flags = {k: it.get(k) for k in it if any(w in k.lower() for w in ('buy', 'purchase', 'can_', 'reserved', 'available', 'visible', 'status'))}
    print(it["id"], repr(it.get("title", "")[:25]), flags)