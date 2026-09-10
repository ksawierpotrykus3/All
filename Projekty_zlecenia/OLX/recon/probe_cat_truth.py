# coding: utf-8
"""
Dowod kategorii: jaka category.id = CALE AUTA OSOBOWE, a jaka = MacBook.
Cel: zastapic zgadywanie type=="automotive" twarda kategoria.
"""
import collections
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def get_json(url, timeout=20):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def probe_cat(cat_id, label):
    code, j = get_json(API + f"?offset=0&limit=50&category_id={cat_id}")
    print(f"\n=== category_id={cat_id} ({label}) status={code} ===")
    if code != 200 or not j:
        print("  brak")
        return
    data = j.get("data", [])
    m = j.get("metadata", {})
    print(f"  zwrocono={len(data)}, visible_total_count={m.get('visible_total_count')}")
    cats = collections.Counter()
    for d in data:
        c = d.get("category") or {}
        cats[c.get("id")] += 1
    print(f"  rozklad category.id w wynikach: {cats.most_common(8)}")
    print("  tytuly (15):")
    for d in data[:15]:
        p = d.get("params") or []
        cena = next((x.get('value',{}).get('value') for x in p if x.get('key')=='price'), None)
        print(f"    id={d.get('id')} cena={cena} | {d.get('title','')[:55]!r}")


if __name__ == "__main__":
    probe_cat(183, "auta osobowe?")
    probe_cat(3102, "MacBook?")