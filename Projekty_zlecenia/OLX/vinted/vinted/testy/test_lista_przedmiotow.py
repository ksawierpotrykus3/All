# coding: utf-8
"""BEZPIECZNY odczyt listy przedmiotów konta konto_A (GET users/{id}/items).
Tylko odczyt — zero rezerwacji, zero POST."""
import json
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"
COOKIES = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_fresh.txt"
USER_ID = 111111111

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

# kilka mozliwych wzorcow listy przedmiotow
candidates = [
    f"https://www.vinted.pl/api/v2/catalog/items?user_id={USER_ID}&page=1&per_page=20",
    f"https://www.vinted.pl/api/v2/catalog/items?user_id={USER_ID}",
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
        print("BODY (first 500):", body[:500])
        if r.status_code == 200 and "application/json" in ct:
            try:
                j = r.json()
                items = j.get("items", [])
                print("LICZBA PRZEDMIOTOW:", len(items))
                for it in items[:10]:
                    print("  - id:", it.get("id"), "| tytul:", (it.get("title") or "")[:40], "| cena:", it.get("price"))
            except Exception as e:
                print("PARSE ERR:", e)
    except Exception as e:
        print("EXCEPTION:", repr(e))