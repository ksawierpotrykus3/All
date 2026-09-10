# coding: utf-8
"""BEZPIECZNA weryfikacja wlasciciela przedmiotu 9782578256 (tylko GET)."""
import json
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"
COOKIES = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_fresh.txt"
ITEM_ID = 9782578256
ACCOUNT_ID = 111111111

jar = http.cookiejar.MozillaCookieJar(COOKIES)
jar.load(ignore_discard=True, ignore_expires=True)

def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate=IMP)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.vinted.pl/",
    "Origin": "https://www.vinted.pl",
})

candidates = [
    f"https://www.vinted.pl/api/v2/catalog/items?search_text=&page=1&per_page=1&ids={ITEM_ID}",
    f"https://www.vinted.pl/api/v2/items/{ITEM_ID}",
    f"https://www.vinted.pl/api/v2/items/{ITEM_ID}/details",
    f"https://www.vinted.pl/api/v2/catalog/items?ids={ITEM_ID}",
]

for url in candidates:
    print("=" * 60)
    print("### GET", url)
    try:
        r = s.get(url, cookies=cookie_dict(), timeout=20)
        print("STATUS:", r.status_code)
        ct = r.headers.get("content-type", "")
        print("CONTENT-TYPE:", ct)
        body = r.text
        print("BODY (first 400):", body[:400])
        if r.status_code == 200 and "application/json" in ct:
            try:
                j = r.json()
                items = j.get("items", [j])
                if isinstance(items, list):
                    for it in items[:5]:
                        u = it.get("user", {})
                        owner = u.get("id")
                        print("  item_id:", it.get("id"), "| login:", u.get("login"), "| owner_id:", owner)
                        print("  >>> WLASCICIEL = KONTO:", owner == ACCOUNT_ID)
            except Exception as e:
                print("PARSE ERR:", e)
    except Exception as e:
        print("EXCEPTION:", repr(e))