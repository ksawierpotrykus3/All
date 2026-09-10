# coding: utf-8
"""Dowod: czy category.id=183 to BMW czy wszystkie auta? + jak odroznic auto od czesci."""
import collections
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

BRANDS = ["audi", "opel", "volkswagen", "ford", "skoda", "toyota", "renault",
          "mercedes", "fiat", "peugeot", "kia", "bmw"]


def get(url):
    try:
        r = creq.get(url, impersonate=IMP, timeout=15)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:
        return -1, str(e)


def params_keys(offer):
    return [p.get("key") for p in (offer.get("params") or [])]


for brand in BRANDS:
    code, j = get(API + f"?offset=0&limit=50&query={brand}")
    if code != 200 or not j:
        print(f"{brand}: code={code}")
        continue
    data = j.get("data", [])
    cats = collections.Counter()
    for d in data:
        cats[(d.get("category") or {}).get("id")] += 1
    # params keys pierwszego oferta automotive
    sample_keys = None
    sample_title = None
    for d in data:
        if (d.get("category") or {}).get("type") == "automotive":
            sample_keys = params_keys(d)
            sample_title = d.get("title", "")[:40]
            break
    print(f"{brand:12} category.id: {dict(cats)} | przyklad params: {sample_keys} | {sample_title!r}")