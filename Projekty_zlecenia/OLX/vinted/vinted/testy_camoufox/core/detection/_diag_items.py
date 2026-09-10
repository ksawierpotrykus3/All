# coding: utf-8
"""Diagnostyka: dostepnosc itemow + struktura builda (pickup points)."""
import json
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
    except Exception:
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?price_to=100&order=newest_first&page=1&per_page=50&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
print("catalog http", r.status_code)
items = r.json().get("items", [])
print("total items", len(items))
for it in items[:15]:
    print(it["id"], "visible=" + str(it.get("is_visible")),
          "status=" + str(it.get("status")),
          "fav=" + str(it.get("favourite_count")),
          repr(it.get("title", "")[:38]))