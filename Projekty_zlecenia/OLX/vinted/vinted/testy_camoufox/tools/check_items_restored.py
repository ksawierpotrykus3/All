# coding: utf-8
"""Sprawdz czy item 9824065306 (po cleanupie) wrocil do katalogu."""
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

for item in [9824065306, 9824054898, 9824062669]:
    try:
        r = s.get(f"https://www.vinted.pl/api/v2/items/{item}", headers=H,
                  impersonate=BrowserType.chrome146, timeout=30)
        if r.status_code == 200:
            it = r.json().get("item", {})
            print(f"[{item}] http=200 status={it.get('status')} title={it.get('title')}")
        else:
            print(f"[{item}] http={r.status_code}")
    except Exception as e:  # noqa: BLE001
        print(f"[{item}] ERR {e}")
