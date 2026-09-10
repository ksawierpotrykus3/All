# coding: utf-8
"""Diagnostyka metod platnosci checkout (GET, bezpieczne - bez build/payment)."""
import json
from pathlib import Path
from curl_cffi import requests as cr

BASE = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

s = cr.Session(impersonate="chrome136")
for c in json.loads((BASE / "cookies_profil.json").read_text(encoding="utf-8")):
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({"accept": "application/json", "locale": "pl-PL",
                  "x-csrf-token": CSRF, "x-anon-id": ANON,
                  "origin": "https://www.vinted.pl", "referer": "https://www.vinted.pl/"})

for url in [
    "https://www.vinted.pl/api/v2/configurations/checkout",
    "https://www.vinted.pl/configurations/checkout",
]:
    r = s.get(url, impersonate="chrome136", timeout=30)
    print(f"\n=== {url} -> HTTP {r.status_code} ===")
    if r.status_code == 200:
        print("BODY:", r.text)
    else:
        print("BODY:", r.text[:200])