# coding: utf-8
"""Licznik bazy przez pagination.total_entries. READ-ONLY."""
import json, time, http.cookiejar
from curl_cffi import requests as creq

jar = http.cookiejar.MozillaCookieJar(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\cookies.txt")
jar.load(ignore_discard=True, ignore_expires=True)
def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate="chrome124")
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.vinted.pl/",
    "Origin": "https://www.vinted.pl",
})

SLEEP = 1.6

# rozne zapytania - sprawdzamy total_entries i czy da sie z boku policzyc cala baze
QUERIES = [
    ("cala baza (bez filtra)", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1"),
    ("search iphone", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&search_text=iphone"),
    ("search nike", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&search_text=nike"),
    ("kategoria? catalog_id", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&catalog_ids=5"),
    ("marka? brand_ids", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&brand_ids=53"),
]

for name, url in QUERIES:
    print("=" * 70)
    print(f"### {name}\n  {url}")
    try:
        r = s.get(url, cookies=cookie_dict(), timeout=25)
        j = r.json()
        print("STATUS:", r.status_code)
        if "pagination" in j:
            p = j["pagination"]
            print("PAGINATION:", json.dumps(p, ensure_ascii=False))
        else:
            print("KEYS:", list(j.keys()), "| body:", r.text[:200])
    except Exception as e:
        print("EXCEPTION:", repr(e))
    time.sleep(SLEEP)