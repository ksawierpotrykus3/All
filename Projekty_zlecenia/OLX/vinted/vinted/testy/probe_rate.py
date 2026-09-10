# coding: utf-8
"""Test: szczegoly itemu + rate-limit katalogu. READ-ONLY, bezpieczne."""
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

# 1) szczegoly itemu - pobierz pierwszy item z katalogu
r = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1", cookies=cookie_dict(), timeout=20)
j = r.json()
item = j["items"][0]
iid = item["id"]
print("PIERWSZY ITEM:", iid, item["title"])

# szczegoly itemu (endpoint z webapp)
for ep in [
    f"https://www.vinted.pl/api/v2/items/{iid}",
    f"https://www.vinted.pl/api/v2/items/{iid}/details",
]:
    rr = s.get(ep, cookies=cookie_dict(), timeout=20)
    print(f"DETAIL {ep.split('/')[-1]}: STATUS {rr.status_code}, CT {rr.headers.get('content-type','')[:40]}, BODY {rr.text[:200]}")
    time.sleep(0.5)

# 2) rate-limit: szybkie 30 requestow katalogu pod rzad, patrzymy kiedy 403/429
print("\n=== RATE-LIMIT TEST (30 szybkich requestow) ===")
starts = time.time()
codes = {}
for i in range(30):
    rr = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1", cookies=cookie_dict(), timeout=20)
    c = rr.status_code
    codes[c] = codes.get(c, 0) + 1
    if c in (403, 429):
        print(f"  BLOKADA po {i+1} requestach: status {c}, body {rr.text[:150]}")
        break
    time.sleep(0.15)
print("WYNIKI KODOW:", codes, "w czasie", round(time.time()-starts,1), "s")