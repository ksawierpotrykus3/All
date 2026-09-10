# coding: utf-8
"""
Dowod: co naprawde zawiera kategoria 2298 (iPhone?) i jak wyglada
rozklad category.id w automotive (cale auta vs czesci).

Pytania do rozstrzygniecia:
  1. cat 2298 = tylko iPhone, czy wszystkie telefony (Samsung/Xiaomi...)?
  2. Ktore category.id w category.type="automotive" to CALE AUTA,
     a ktore to czesci/akcesoria?
  3. Format pola ceny - czy sa spacje/formaty lamiace float()?
"""
import collections
import json
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def get_json(url, timeout=20):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def probe_cat(cat_id, label, limit=50):
    url = API + f"?offset=0&limit={limit}&category_id={cat_id}"
    code, j = get_json(url)
    print(f"\n=== cat_id={cat_id} ({label}) status={code} ===")
    if code != 200 or not j:
        print("  brak odpowiedzi")
        return
    data = j.get("data", [])
    m = j.get("metadata", {})
    print(f"  zwrocono={len(data)}, visible_total_count={m.get('visible_total_count')}, total_elements={m.get('total_elements')}")
    cats = collections.Counter()
    for d in data[:65]:
        c = d.get("category") or {}
        cats[(c.get("id"), c.get("type"))] += 1
    print(f"  rozklad category(id,type) w wynikach: {cats.most_common(10)}")
    print("  tytuly (pierwsze 20):")
    for d in data[:20]:
        print(f"    {d.get('title','')[:60]!r}")


def probe_automotive():
    # pobierz oferty automotive i zbierz category.id
    code, j = get_json(API + "?offset=0&limit=50&query=bmw")
    if code != 200 or not j:
        print("brak danych automotive")
        return
    data = j.get("data", [])
    cats = collections.Counter()
    samples = {}
    for d in data:
        c = d.get("category") or {}
        if c.get("type") == "automotive":
            cats[c.get("id")] += 1
            samples.setdefault(c.get("id"), d.get("title", "")[:50])
    print("\n=== automotive: category.id rozklad (query=bmw) ===")
    for cid, n in cats.most_common(20):
        print(f"  cat.id={cid} n={n} | przyklad: {samples[cid]!r}")


def probe_price_formats():
    code, j = get_json(API + "?offset=0&limit=50&category_id=203")
    if code != 200 or not j:
        print("brak danych ceny")
        return
    fmt = collections.Counter()
    examples = {}
    for d in j.get("data", []):
        for p in d.get("params", []) or []:
            if p.get("key") == "price":
                v = p.get("value", {}).get("value")
                vstr = str(v)
                if " " in vstr or "," in vstr:
                    key = "SPACJA/PRZECINEK"
                elif v is None:
                    key = "NONE"
                else:
                    key = "czysta liczba"
                fmt[key] += 1
                examples.setdefault(key, vstr)
                break
    print("\n=== formaty cen (cat 203 auta) ===")
    for k, n in fmt.most_common():
        print(f"  {k}: {n} | przyklad={examples[k]!r}")


if __name__ == "__main__":
    probe_cat(2298, "iPhone?")
    probe_automotive()
    probe_price_formats()