# coding: utf-8
"""Probe: znajdź category.id dla laptopów/telefonów/aut przez wyszukiwanie frazowe."""
import json
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def q(url):
    try:
        r = creq.get(url, impersonate=IMP, timeout=20)
        return r.status_code, r.json() if r.status_code == 200 else r.text[:200]
    except Exception as e:
        return -1, str(e)


def dump_cats(phrase, limit=3):
    code, j = q(API + f"?offset=0&limit={limit}&query={phrase}")
    print(f"\n=== query={phrase} code={code} ===")
    if code != 200:
        print("  ", j)
        return
    for d in j.get("data", []):
        cat = d.get("category", {})
        print(f"  id={d.get('id')} cat.id={cat.get('id')} cat.type={cat.get('type')} | {d.get('title','')[:50]}")


if __name__ == "__main__":
    for phrase in ["macbook", "macbook pro", "iphone", "bmw", "opel"]:
        dump_cats(phrase)