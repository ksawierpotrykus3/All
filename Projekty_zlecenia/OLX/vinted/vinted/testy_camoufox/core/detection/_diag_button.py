# coding: utf-8
"""Tania detekcja przycisku 'Kup teraz' przez GET HTML (curl_cffi, bez Camoufox)."""
import json
import sys
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
s.headers.update({"accept": "text/html,application/xhtml+xml",
                  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"})

ids = [int(x) for x in sys.argv[1:]] or [9824858217, 9824858152, 9824858050, 9824858031, 9824858030]
for iid in ids:
    r = s.get(f"https://www.vinted.pl/items/{iid}", impersonate=BrowserType.chrome146, timeout=30)
    h = r.text
    has_buy = 'item-buy-button' in h or 'Kup teraz' in h or 'Kupuj' in h
    has_sold = 'sold' in h.lower() and 'przedane' in h.lower()
    print(iid, "http", r.status_code, "buy_button", has_buy, "len", len(h))