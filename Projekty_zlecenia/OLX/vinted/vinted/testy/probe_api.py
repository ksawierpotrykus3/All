# coding: utf-8
"""Sonda Vinted API - z cookies usera. Bezpieczne testy READ-ONLY (katalog/szukaj)."""
import json
import time
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"

# wczytaj cookies z pliku Netscape
jar = http.cookiejar.MozillaCookieJar(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\cookies.txt")
jar.load(ignore_discard=True, ignore_expires=True)

def cookie_dict():
    d = {}
    for c in jar:
        d[c.name] = c.value
    return d

s = creq.Session(impersonate=IMP)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.vinted.pl/",
    "Origin": "https://www.vinted.pl",
})

# kilka znanych endpointow Vinted
ENDPOINTS = [
    ("katalog - nowe", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=20&order=newest_first"),
    ("katalog - cena desc", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=20&order=price_desc"),
    ("szukaj - test", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=20&search_text=iphone"),
    ("user me", "https://www.vinted.pl/api/v2/users/me"),
]

for name, url in ENDPOINTS:
    print("=" * 60)
    print(f"### {name}  ->  {url}")
    try:
        r = s.get(url, cookies=cookie_dict(), timeout=20)
        print("STATUS:", r.status_code)
        print("FINAL URL:", r.url[:120])
        ct = r.headers.get("content-type", "")
        print("CONTENT-TYPE:", ct)
        # DataDome / Cloudflare sygnaly
        for h in ["x-datadome", "x-datadome-isbot", "server", "cf-ray", "x-cache", "x-datadome-isbot-response"]:
            if h in r.headers:
                print(f"  HEADER {h}: {r.headers[h]}")
        body = r.text
        print("BODY (first 600):", body[:600])
        if "application/json" in ct:
            try:
                j = r.json()
                if isinstance(j, dict) and "items" in j:
                    print("ITEMS COUNT:", len(j["items"]))
                elif isinstance(j, dict):
                    print("JSON KEYS:", list(j.keys())[:20])
            except Exception as e:
                print("JSON PARSE ERR:", e)
    except Exception as e:
        print("EXCEPTION:", repr(e))
    time.sleep(1.5)