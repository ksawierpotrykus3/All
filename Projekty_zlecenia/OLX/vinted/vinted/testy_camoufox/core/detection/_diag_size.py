# coding: utf-8
"""Weryfikacja hipotezy: przycisk 'Kup teraz' widoczny tylko przy jednym rozmiarze.

Sprawdza size_title (i czy sa warianty rozmiarow) dla itemow w katalogu.
Porusza: itemy z wieloma rozmiarami wymagaja wyboru przed odslonieciem przycisku.
"""
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
       "?price_to=100&order=newest_first&page=1&per_page=60&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
items = r.json().get("items", [])
print("total", len(items))
# pelny klucz size / swatch / item_box
for it in items[:25]:
    box = it.get("item_box") or {}
    # szukaj kluczy zwiazanych z rozmiarem w item_box lub top-level
    size_keys = [k for k in it if 'size' in k.lower() or 'swatch' in k.lower() or 'variant' in k.lower()]
    print(it["id"], "size_title=", repr(it.get("size_title")),
          "box_keys=", list(box.keys()) if isinstance(box, dict) else type(box),
          "size_keys=", size_keys)