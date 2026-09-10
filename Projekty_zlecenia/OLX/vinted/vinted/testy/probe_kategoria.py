# coding: utf-8
"""Znalezc poprawna nazwe parametru kategorii. Najpierw pobrac prawdziwy
catalog_id z HTML itemu (JSON-LD), potem przetestowac go roznymi nazwami."""
import json, time, http.cookiejar, re
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

# 1) pobierz item z katalogu
r = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1", cookies=cookie_dict(), timeout=25)
item = r.json()["items"][0]
iid = item["id"]
print("ITEM id:", iid, "| url:", item.get("url"))

# 2) pobierz HTML itemu i wyciagnij catalog_id z JSON-LD
r2 = s.get(f"https://www.vinted.pl/items/{iid}", cookies=cookie_dict(), timeout=25)
html = r2.text
print("HTML len:", len(html), "status:", r2.status_code)

# szukaj catalog_id, category_id, cokolwiek z "catalog" w JSON-LD
for pat in [r'catalog_?id["\']?\s*:\s*["\']?(\d+)', r'catalog["\']?\s*:\s*["\']?(\d+)', r'category_?id["\']?\s*:\s*["\']?(\d+)', r'category["\']?\s*:\s*["\']?(\d+)']:
    ms = re.findall(pat, html, re.I)
    if ms:
        print(f"PATTERN {pat!r} ->", ms[:5])

# szukaj wszystkich "catalog" wystapien z kontekstem
print("\n=== wszystkie 'catalog' w HTML (kontekst) ===")
for m in re.finditer(r'.{20}catalog.{30}', html, re.I):
    print(m.group(0).replace("\n", " ")[:80])
    if m.start() > 500000:
        break

time.sleep(SLEEP)