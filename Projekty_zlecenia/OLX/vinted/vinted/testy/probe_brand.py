# coding: utf-8
"""Czy filtr brand_id / size obniza total_entries ponizej 960? Domkniecie tematu segmentacji."""
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

def pag(url):
    r = s.get(url, cookies=cookie_dict(), timeout=25)
    j = r.json()
    p = j.get("pagination", {})
    return p.get("total_entries"), p.get("total_pages"), r.status_code

# najpierw pobierz realne brand_id i size z pierwszych itemow
r = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=96", cookies=cookie_dict(), timeout=25)
items = r.json()["items"]
brands = {}
sizes = {}
for it in items:
    b = it.get("brand_title")
    if b:
        brands[b] = brands.get(b, 0) + 1
    sz = it.get("size_title")
    if sz:
        sizes[sz] = sizes.get(sz, 0) + 1
print("MARKI w pierwszych 96:", list(brands.items())[:10])
print("ROZMIARY w pierwszych 96:", list(sizes.items())[:10])

# testujemy rozne warianty parametru marki
print("\n=== TEST MARKI / ROZMIARU ===")
tests = [
    ("brand_ids=53", "brand_ids=53"),
    ("brand_ids=53 tylko katalog", "brand_ids=53&search_text="),
    ("catalog_ids=5 (kategoria 5)", "catalog_ids=5"),
    ("catalog_ids=1904 (ubrania?)", "catalog_ids=1904"),
    ("status_ids", "status_ids=6"),
    ("size_ids=208", "size_ids=208"),
]
for name, q in tests:
    url = f"https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&{q}"
    te, tp, st = pag(url)
    print(f"{name}: status={st}, total_entries={te}, total_pages={tp}")
    time.sleep(SLEEP)

# sprawdzmy czy jakikolwiek filtr obniza te 960
print("\n=== POJEDYNCZY WYNIK vs 960 ===")
r2 = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&search_text=xyzqwerty123", cookies=cookie_dict(), timeout=25)
j2 = r2.json()
print("search bez sensu 'xyzqwerty123':", j2.get("pagination", {}).get("total_entries"), "items", len(j2.get("items", [])))