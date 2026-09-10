# coding: utf-8
"""Wydobadz z HTML strony kategorii: gdzie sa oferty i licznik.
Szuka wzorcow JSON (self.__next_f.push, window.__, itd)."""
import re

html = open(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\katalog_1904.html", encoding="utf-8", errors="ignore").read()
print("len:", len(html))

# 1) self.__next_f.push - Next.js 13+ App Router
print("\n=== self.__next_f.push ===")
ms = re.findall(r'self\.__next_f\.push', html)
print("wystapien:", len(ms))

# 2) window.__ jakiekolwiek
for m in re.finditer(r'(window|self)\.(__[A-Za-z_]+)', html):
    print("GLOBAL:", m.group(1) + "." + m.group(2))

# 3) szukaj liczb podobnych do ID ofert (9-10 cyfr) z kontekstem
print("\n=== 9-10 cyfrowe ID w HTML (kontekst) ===")
seen = set()
for m in re.finditer(r'(\d{9,10})', html):
    s = m.start()
    ctx = html[max(0,s-30):s+30]
    key = m.group(1)
    if key not in seen and not ctx.startswith(("0","1")):  # pomin timestampy
        seen.add(key)
        print(f"  ...{ctx}...".replace("\n"," "))
        if len(seen) > 15:
            break

# 4) "item" wystapienia
print("\n=== 'item' w HTML ===")
print("count 'item':", html.lower().count("item"))
print("count 'items':", html.lower().count("items"))
print("count 'catalog':", html.lower().count("catalog"))
print("count 'price':", html.lower().count("price"))

# 5) schemat JSON-LD
print("\n=== JSON-LD scripts ===")
for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
    print("JSON-LD:", m.group(1)[:200].replace("\n"," "))

# 6) pierwsze 5000 znakow (zeby zobaczyc strukture)
print("\n=== PIERWSZE 3000 znakow ===")
print(html[:3000])