# coding: utf-8
"""Sonda alternatywnych sciezek Vinted + licznik bazy. READ-ONLY, wolne tempo."""
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

def show(name, url, parse_json=True):
    print("=" * 70)
    print(f"### {name}\n  {url}")
    try:
        r = s.get(url, cookies=cookie_dict(), timeout=25)
        ct = r.headers.get("content-type", "")
        print("STATUS:", r.status_code, "| CT:", ct[:40], "| len:", len(r.text))
        if parse_json and "json" in ct:
            try:
                j = r.json()
                if isinstance(j, dict):
                    print("KEYS:", list(j.keys()))
                    # szukaj licznika bazy / total
                    for k in j.keys():
                        v = j[k]
                        if isinstance(v, (int, float)):
                            print(f"  NUM {k} = {v}")
                        elif isinstance(v, dict):
                            print(f"  DICT {k} keys: {list(v.keys())[:15]}")
                        elif isinstance(v, list):
                            print(f"  LIST {k} len={len(v)}")
                elif isinstance(j, list):
                    print("LIST len:", len(j))
            except Exception as e:
                print("JSON ERR:", e, "| body:", r.text[:300])
        else:
            print("BODY:", r.text[:300].replace("\n", " ")[:300])
    except Exception as e:
        print("EXCEPTION:", repr(e))
    time.sleep(SLEEP)

# 1) katalog - pelny dump kluczy (szukamy total/pagination)
show("katalog empty", "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1&search_text=")

# 2) search API v2 (inny endpoint)
show("search/items", "https://www.vinted.pl/api/v2/search/items?page=1&per_page=1&search_text=iphone")

# 3) aggregations / facety (czesto zawieraja total count)
show("catalog aggregations", "https://www.vinted.pl/api/v2/catalog/aggregations?search_text=iphone")

# 4) kategorie (lista, moze z licznikami)
show("categories", "https://www.vinted.pl/api/v2/categories")

# 5) promoted items
show("promoted items", "https://www.vinted.pl/api/v2/promoted/items?page=1&per_page=5")

# 6) sitemap (HTML, nie JSON) - liczba stron/ofert
show("sitemap.xml", "https://www.vinted.pl/sitemap.xml", parse_json=False)

# 7) user items (pierwszy item z katalogu -> jego user)
r = s.get("https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=1", cookies=cookie_dict(), timeout=25)
try:
    uid = r.json()["items"][0]["user"]["id"]
    show("user items", f"https://www.vinted.pl/api/v2/users/{uid}/items?page=1&per_page=5&order=newest_first")
except Exception as e:
    print("Nie pobrano usera:", repr(e))