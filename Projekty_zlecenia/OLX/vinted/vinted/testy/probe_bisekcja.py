# coding: utf-8
"""Bisekcja cenowa: czy price_from/price_to dziala i czy total schodzi < 960.
Dowod na mozliwosc policzenia calej bazy Vinted (jak z OLX)."""
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

print("=== BISEKCJA CENOWA ===")
tests = [
    ("cena 0-100", "price_from=0&price_to=100"),
    ("cena 100-200", "price_from=100&price_to=200"),
    ("cena 1000-2000", "price_from=1000&price_to=2000"),
    ("cena 5000-10000", "price_from=5000&price_to=10000"),
    ("cena >10000", "price_from=10000"),
    ("cena <50", "price_to=50"),
]
for name, q in tests:
    url = f"https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&{q}"
    te, tp, st = pag(url)
    print(f"{name}: status={st}, total_entries={te}, total_pages={tp}")
    time.sleep(SLEEP)

print("\n=== FILTR DATY (do segmentacji czasowej) ===")
# sprawdzamy czy sa parametry daty w formacie unix
tests2 = [
    ("status nowe? order", "order=newest_first"),
    ("order oldest", "order=oldest_first"),
]
for name, q in tests2:
    url = f"https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&{q}"
    te, tp, st = pag(url)
    print(f"{name}: status={st}, total_entries={te}, total_pages={tp}")
    time.sleep(SLEEP)

# pobierz pelny item by zobaczyc dostepne pola (do segmentacji)
print("\n=== POLA ITEMU (co mozna filtrowac) ===")
r = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1", cookies=cookie_dict(), timeout=25)
item = r.json()["items"][0]
print("ITEM KEYS:", list(item.keys()))
for k in ["price", "catalog_id", "brand_id", "size", "status", "created_at_ts", "title"]:
    if k in item:
        print(f"  {k} = {item[k]}")