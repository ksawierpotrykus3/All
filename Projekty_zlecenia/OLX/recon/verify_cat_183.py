# coding: utf-8
"""Rozstrzyga: category_id=183 to wszystkie auta czy tylko BMW? + jak dziala type==automotive."""
import collections
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def get(url):
    try:
        r = creq.get(url, impersonate=IMP, timeout=20)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:
        return -1, str(e)


def first_words(title, n=2):
    return " ".join((title or "").split()[:n])


# 1) Co zwraca category_id=183?
print("=== category_id=183 ===")
code, j = get(API + "?offset=0&limit=50&category_id=183")
if code == 200:
    data = j.get("data", [])
    cats = collections.Counter()
    brands = collections.Counter()
    for d in data:
        cats[(d.get("category") or {}).get("id")] += 1
        brands[first_words(d.get("title"))] += 1
    print(f"  zwrocono={len(data)} ofert")
    print(f"  rozklad category.id wsrod wynikow: {dict(cats)}")
    print(f"  pierwsze slowa tytulow: {dict(brands)}")
else:
    print(f"  code={code} body={str(j)[:200]}")

# 2) Co zwraca type==automotive przy ogolnej liscie?
print("\n=== query=bmw, rozklad category.id ===")
code, j = get(API + "?offset=0&limit=50&query=bmw")
if code == 200:
    data = j.get("data", [])
    cats = collections.Counter()
    for d in data:
        cats[(d.get("category") or {}).get("id")] += 1
    print(f"  query=bmw -> category.id: {dict(cats)}")

print("\n=== query=audi, rozklad category.id ===")
code, j = get(API + "?offset=0&limit=50&query=audi")
if code == 200:
    data = j.get("data", [])
    cats = collections.Counter()
    for d in data:
        cats[(d.get("category") or {}).get("id")] += 1
    print(f"  query=audi -> category.id: {dict(cats)}")

# 3) Czy category_id=183 daje tylko BMW, czy tez inne marki?
print("\n=== marki w category_id=183 (sprawdzam tytuly pod katem marki) ===")
code, j = get(API + "?offset=0&limit=50&category_id=183")
if code == 200:
    data = j.get("data", [])
    for d in data[:15]:
        t = (d.get("title") or "")[:60]
        cid = (d.get("category") or {}).get("id")
        typ = (d.get("category") or {}).get("type")
        print(f"  id={d.get('id')} cat={cid} type={typ} tytul={t!r}")