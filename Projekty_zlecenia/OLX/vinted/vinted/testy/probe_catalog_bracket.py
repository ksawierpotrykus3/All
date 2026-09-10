# coding: utf-8
"""Weryfikacja parametru kategorii: catalog[]=ID (z nawiasami, jak w referrerze przegladarki)."""
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

def probe(label, url):
    r = s.get(url, cookies=cookie_dict(), timeout=25)
    j = r.json()
    p = j.get("pagination", {})
    items = j.get("items", [])
    print(f"{label}: total={p.get('total_entries')}, items={len(items)}, status={r.status_code}")
    time.sleep(SLEEP)

print("=== KONTROLA ===")
probe("bez filtra", BASE)

print("\n=== KATEGORIA: catalog[] (prawdziwa nazwa z przegladarki) ===")
# 1904 = women (z breadcrumb), 16 = shoes
probe("catalog[]=1904 (women)", f"{BASE}&catalog%5B%5D=1904")
probe("catalog[]=16 (shoes)", f"{BASE}&catalog%5B%5D=16")
probe("catalog[]=999999999 (bzdurny)", f"{BASE}&catalog%5B%5D=999999999")

print("\n=== DOWOD: sprawdz czy kategoria obniza total < 960 ===")
# jesli kategoria dziala, total dla waskiej kategorii (np. boat shoes 2954) bedzie maly
probe("catalog[]=2954 (boat shoes)", f"{BASE}&catalog%5B%5D=2954")