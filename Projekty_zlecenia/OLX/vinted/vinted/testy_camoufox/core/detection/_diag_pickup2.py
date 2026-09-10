# coding: utf-8
"""Pełna struktura odpowiedzi nearby_pickup_points — gdzie jest point_code/point_uuid."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
SO_ID = 24844514578
LAT, LON = 54.3475, 18.3613

s = cr.Session()
for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "referer": "https://www.vinted.pl/",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}
url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{SO_ID}"
       f"/nearby_pickup_points?country_code=PL&latitude={LAT}&longitude={LON}")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
data = r.json()
print("http", r.status_code)
print("top_keys", list(data.keys()) if isinstance(data, dict) else type(data))
# wypisz pierwszy element kazdej listy w top level
if isinstance(data, dict):
    for k, v in data.items():
        if isinstance(v, list) and v:
            print(f"\n--- {k} (n={len(v)}), first item keys:", list(v[0].keys()) if isinstance(v[0], dict) else type(v[0]))
            print(json.dumps(v[0], ensure_ascii=False, indent=2)[:1200])
        elif not isinstance(v, (list, dict)):
            print(f"{k} = {v}")