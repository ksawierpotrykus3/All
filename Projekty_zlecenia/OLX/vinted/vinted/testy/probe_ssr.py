# coding: utf-8
"""Sprawdz HTML strony kategorii pod katem osadzonego JSON (__NEXT_DATA__).
Strona kategorii renderuje oferty server-side, wiec prawdziwy licznik i oferty
sa w HTML, nie w /api/v2/catalog/items."""
import json, time, http.cookiejar, re
from curl_cffi import requests as creq

jar = http.cookiejar.MozillaCookieJar(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\cookies.txt")
jar.load(ignore_discard=True, ignore_expires=True)
def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate="chrome124")
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
})

url = "https://www.vinted.pl/catalog?catalog%5B%5D=1904&page=1"
print("POBIERAM:", url)
r = s.get(url, cookies=cookie_dict(), timeout=30)
print("STATUS:", r.status_code, "| len:", len(r.text))

html = r.text

# 1) __NEXT_DATA__
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
print("\n__NEXT_DATA__ obecny:", bool(m))
if m:
    try:
        data = json.loads(m.group(1))
        print("NEXT_DATA klucze top:", list(data.keys()))
        props = data.get("props", {})
        print("props klucze:", list(props.keys()) if isinstance(props, dict) else type(props))
        # zrzuc sciezke do items/catalog
        s_json = json.dumps(data)
        for key in ["total_entries", "total_pages", "total_items", "item_count", "total_count"]:
            idx = s_json.find(f'"{key}"')
            if idx != -1:
                print(f"  ZNALEZIONO {key}: ...{s_json[idx:idx+120]}...")
    except Exception as e:
        print("PARSE NEXT_DATA err:", e)

# 2) szukaj licznika ofert w calym HTML (pattern "total" lub "wyniki")
print("\n=== szukam licznika w HTML ===")
for pat in [r'([\d\s]+)\s*(?:wynik|przedmiot|oferta)', r'total[_a-z]*["\']?\s*[:=]\s*(\d+)']:
    for mm in re.finditer(pat, html, re.I):
        print("  ", mm.group(0)[:80])
        if mm.start() > 100000:
            break

# 3) czy oferty sa w HTML (item title)
print("\n=== pierwsze itemy w HTML? ===")
for mm in re.finditer(r'"title"\s*:\s*"([^"]{5,60})"', html):
    print("  title:", mm.group(1)[:60])
    if mm.start() > 50000:
        break

with open("katalog_1904.html", "w", encoding="utf-8") as f:
    f.write(html)
print("\nHTML zapisany do katalog_1904.html")