# coding: utf-8
"""Weryfikacja poprawnych nazw parametrow ceny i kategorii.
Jesli parametr ma zla nazwe, bzdurna wartosc daje 960 (ignorowany).
Jesli dobra nazwe - bzdurna wartosc daje 0 (filtr dziala)."""
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
    r = s.get(f"{BASE}&{q}", cookies=cookie_dict(), timeout=25)
    j = r.json()
    p = j.get("pagination", {})
    items = j.get("items", [])
    first_price = items[0]["price"]["amount"] if items else "(brak)"
    first_brand = items[0].get("brand_title") if items else "(brak)"
    print(f"{label}: total={p.get('total_entries')}, first_price={first_price}, first_brand={first_brand!r}")
    time.sleep(SLEEP)

print("=== KONTROLA: bez filtra ===")
probe("bez filtra", "")

print("\n=== CENA: alternatywne nazwy (bzdurna wartosc powinna dac 0 jesli nazwa dobra) ===")
probe("price_min=1&price_max=2", "price_min=1&price_max=2")
probe("min_price=1&max_price=2", "min_price=1&max_price=2")
probe("price_from=1&price_to=2 (retest)", "price_from=1&price_to=2")
probe("price_from_pln=1&price_to_pln=2", "price_from_pln=1&price_to_pln=2")

print("\n=== KATEGORIA: alternatywne nazwy (bzdurny ID powinien dac 0 jesli nazwa dobra) ===")
probe("catalog_id=999999999", "catalog_id=999999999")
probe("catalog_ids=999999999 (retest)", "catalog_ids=999999999")
probe("category_ids=999999999", "category_ids=999999999")
probe("catalogue_ids=999999999", "catalogue_ids=999999999")
probe("catalog=999999999", "catalog=999999999")

print("\n=== PRAWDZIWA KATEGORIA: szukam catalog_id w itemie ===")
r = s.get(BASE, cookies=cookie_dict(), timeout=25)
item = r.json()["items"][0]
print("ITEM fields z kategoria/url/path:", {k: item.get(k) for k in ["url", "path", "id"] if k in item})