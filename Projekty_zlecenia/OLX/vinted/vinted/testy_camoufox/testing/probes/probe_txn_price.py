# coding: utf-8
"""Sprawdza cene/item transakcji 21923992228 (ta z payment 400 code 114)."""
import json
from pathlib import Path
from curl_cffi import requests as cr

BASE = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
TXN = 21923992228

s = cr.Session(impersonate="chrome136")
for c in json.loads((BASE / "cookies_profil.json").read_text(encoding="utf-8")):
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({"accept": "application/json", "locale": "pl-PL",
                  "x-csrf-token": CSRF, "x-anon-id": ANON})

r = s.get(f"https://www.vinted.pl/api/v2/transactions/{TXN}", impersonate="chrome136", timeout=30)
print("HTTP", r.status_code)
try:
    t = r.json().get("transaction", {})
    print("item_id:", t.get("item_id"))
    print("price:", json.dumps(t.get("price") or t.get("item_price"), ensure_ascii=False))
    print("status:", t.get("status"), t.get("status_title"))
    # wypisz klucze zawierajace price/amount
    import re
    raw = json.dumps(t, ensure_ascii=False)
    for m in re.finditer(r'"[^"]*(price|amount)[^"]*"\s*:\s*[^,}]+', raw):
        print("  ", m.group(0)[:120])
except Exception as e:
    print("parse err:", e, r.text[:300])