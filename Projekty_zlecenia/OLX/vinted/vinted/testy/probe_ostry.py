# coding: utf-8
"""OSTRY test: bzdurne ID filtrów. Jesli bzdurny brand_id/catalog_id/size_id
zwraca 960 ofert, to dowodzi ze parametr jest IGNOROWANY (bo nie moze byc 960
ofert dla nieistniejacego ID). Kontrola: search_text bzdurny = 0."""
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
BASE = "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1"

def probe(label, q):
    r = s.get(f"{BASE}&{q}" if q else BASE, cookies=cookie_dict(), timeout=25)
    j = r.json()
    p = j.get("pagination", {})
    items = j.get("items", [])
    # pokaz tez marke pierwszego itemu, zeby widziec czy faktycznie filtruje
    first_brand = items[0].get("brand_title") if items else "(brak)"
    print(f"{label}: total={p.get('total_entries')}, items={len(items)}, first_brand={first_brand!r}, status={r.status_code}")
    time.sleep(SLEEP)

print("=== KONTROLA (bez filtra) ===")
probe("bez filtra", "")

print("\n=== SEARCH_TEXT (kontrola: wiadomo ze dziala) ===")
probe("search_text=xyzqwerty999", "search_text=xyzqwerty999")

print("\n=== BZDURNE ID (dowod: jesli 960 = ignorowany) ===")
probe("brand_ids=999999999", "brand_ids=999999999")
probe("catalog_ids=999999999", "catalog_ids=999999999")
probe("size_ids=999999999", "size_ids=999999999")
probe("status_ids=999999999", "status_ids=999999999")
probe("price_from=1&price_to=2", "price_from=1&price_to=2")

print("\n=== CZY BRAND REALNIE FILTRUJE (porownaj marki) ===")
# pobierz 96 itemow z brand_ids=53 i sprawdz czy wszystkie maja ta sama marke
r = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=96&brand_ids=53", cookies=cookie_dict(), timeout=25)
items = r.json()["items"]
brands = {}
for it in items:
    b = it.get("brand_title", "(brak)")
    brands[b] = brands.get(b, 0) + 1
print("Marki przy brand_ids=53 (top 10):", list(brands.items())[:10])
print("Liczba unikalnych marek:", len(brands))