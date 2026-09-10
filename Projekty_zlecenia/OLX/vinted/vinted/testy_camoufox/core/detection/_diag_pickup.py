# coding: utf-8
"""Diagnostyka: czy GET api.vinted.pl/shipping-estimation/... pickup_points
przechodzi przy cookies z pliku (domena .vinted.pl) + chrome146 + bez Bearer."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# z poprzedniego udanego buildu (wynik_hybrid_e2e.json)
SO_ID = 24844514578
LAT, LON = 54.3475, 18.3613

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
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{SO_ID}"
       f"/nearby_pickup_points?country_code=PL&latitude={LAT}&longitude={LON}")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
print("http", r.status_code)
print("body", r.text[:400])