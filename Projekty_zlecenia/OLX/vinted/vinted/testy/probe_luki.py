# coding: utf-8
"""Domkniecie luk: (1) kategoria catalog_ids z REALNYM waskim ID,
(2) sekwencyjnosc ID ofert (jak OLX), (3) czy order=newest_first sortuje."""
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
BASE = "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=96"

def get(url):
    r = s.get(url, cookies=cookie_dict(), timeout=25)
    return r.json() if r.status_code == 200 else None

# 1) KATEGORIA: catalog_ids z realnym waskim ID (2954 = boat shoes)
print("=== KATEGORIA catalog_ids (realne ID) ===")
for cid in [2954, 16, 1904, 5]:
    j = get(f"{BASE}&catalog_ids={cid}")
    if j:
        p = j.get("pagination", {})
        print(f"catalog_ids={cid}: total_entries={p.get('total_entries')}, total_pages={p.get('total_pages')}")
    time.sleep(SLEEP)

# 2) SEKWENCYJNOSC ID: pobierz 96 itemow, zobacz czy id rosna
print("\n=== SEKWENCYJNOSC ID OFERT ===")
j = get(f"{BASE}&order=newest_first")
if j:
    items = j["items"]
    ids = [it["id"] for it in items]
    print("pierwsze 5 ID:", ids[:5])
    print("ostatnie 5 ID:", ids[-5:])
    # czy rosnace? policz przejscia rosnace vs malejace
    inc = sum(1 for a, b in zip(ids, ids[1:]) if b > a)
    dec = sum(1 for a, b in zip(ids, ids[1:]) if b < a)
    print(f"rosnace: {inc}, malejace: {dec}, stale: {len(ids)-1-inc-dec}")
    print("min:", min(ids), "max:", max(ids), "rozstep:", max(ids)-min(ids))
    time.sleep(SLEEP)

# 2b) czy ID rosna globalnie w czasie? pobierz ponownie po chwili
print("\n=== ID W CZASIE (2 probki) ===")
j2 = get(f"{BASE}&order=newest_first")
if j2:
    ids2 = [it["id"] for it in j2["items"]]
    new_items = [i for i in ids2 if i not in ids]
    print("nowe ID miedzy probkami:", len(new_items), "| przyklady:", new_items[:3])
    time.sleep(SLEEP)

# 3) SORTOWANIE: order=newest_first vs oldest_first - czy zmienia kolejnosc
print("\n=== SORTOWANIE order ===")
j_new = get(f"{BASE}&order=newest_first")
j_old = get(f"{BASE}&order=oldest_first")
if j_new and j_old:
    ids_new = [it["id"] for it in j_new["items"]]
    ids_old = [it["id"] for it in j_old["items"]]
    print("newest_first 5 ID:", ids_new[:5])
    print("oldest_first 5 ID:", ids_old[:5])
    print("IDENTYCZNE listy:", ids_new == ids_old)
    print("odwrocone:", ids_new == list(reversed(ids_old)))