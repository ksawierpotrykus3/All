# coding: utf-8
"""_probe_firefox135_health.py — bezpieczny test spójności stacku firefox135.

Tylko GET-y publiczne (health + catalog), zero akcji transakcyjnych.
Potwierdza, że curl_cffi impersonate=firefox135 + aktualne cookies_profil.json
(zalogowana sesja z profilu 135, BEZ datadome) przechodzi przez DataDome.
"""
import json
from pathlib import Path
from curl_cffi import requests as cr

BASE = Path(__file__).resolve().parent
COOKIES = BASE / "cookies_profil.json"

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"


def main():
    s = cr.Session(impersonate="firefox135")
    for c in json.loads(COOKIES.read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
    })
    h = {"x-csrf-token": CSRF, "x-anon-id": ANON}

    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=h, timeout=30)
    print(f"health: status={r.status_code}")
    if r.status_code == 200:
        u = r.json().get("user", {})
        print(f"  zalogowany: {u.get('login')} id={u.get('id')}")
    else:
        print(f"  body: {r.text[:200]}")

    r2 = s.get(
        "https://www.vinted.pl/api/v2/catalog/items"
        "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
        headers=h, timeout=30)
    print(f"catalog: status={r2.status_code} itemy={len(r2.json().get('items') or []) if r2.status_code == 200 else '-'}")
    if r2.status_code != 200:
        print(f"  body: {r2.text[:200]}")


if __name__ == "__main__":
    main()