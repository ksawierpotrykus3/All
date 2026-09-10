# coding: utf-8
"""
Audyt endpointu listy OLX /api/v1/offers/ — nie ufamy niczemu.

Sprawdza:
  A) strukture top-level odpowiedzi (klucze, dlugosci, skad 65 przy limit=50)
  B) realny zakres limitu (1..100) i kody bledow
  C) czy offset dziala (paginacja) i czy mozna wyciagnac wiecej niz 50
  D) domyslne sortowanie (pole sort/sort_order?) — po dacie? po czym?
  E) strukture pojedynczego elementu data (klucze, czy sa promowane osobno)
"""
from curl_cffi import requests as creq
import json

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def get(url, timeout=20):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        return r.status_code, r.json()
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def show_top(url):
    code, j = get(url)
    print(f"\n=== {url}\n  status={code}")
    if code != 200:
        print("  body:", str(j)[:300])
        return
    print("  top-level keys:", list(j.keys()))
    for k, v in j.items():
        if isinstance(v, list):
            print(f"    {k}: list len={len(v)}")
        elif isinstance(v, dict):
            print(f"    {k}: dict keys={list(v.keys())[:15]}")
        else:
            print(f"    {k}: {repr(v)[:120]}")
    data = j.get("data")
    if data:
        print("  data[0] keys:", list(data[0].keys()))
        d0 = data[0]
        print("  data[0] id:", d0.get("id"))
        print("  data[0] category:", json.dumps(d0.get("category"), ensure_ascii=False))
        print("  data[0] title:", (d0.get("title") or "")[:60])
        print("  data[0] created_time:", d0.get("created_time"))
        print("  data[0] url:", d0.get("url"))
        print("  data[0] promotion:", json.dumps(d0.get("promotion"), ensure_ascii=False)[:200])


def main():
    print("A) STRUKTURA TOP-LEVEL (limit=50&query=iphone)")
    show_top(API + "?offset=0&limit=50&query=iphone")

    print("\nB) ZAKRES LIMITU")
    for lim in (1, 5, 20, 50, 51, 60, 100, 101):
        code, j = get(API + f"?offset=0&limit={lim}&query=iphone")
        n = len(j.get("data", [])) if isinstance(j, dict) else "?"
        print(f"  limit={lim:4d} -> status={code} data_len={n}")

    print("\nC) PAGINACJA offset")
    for off in (0, 50, 100, 150):
        code, j = get(API + f"?offset={off}&limit=50&query=iphone")
        if isinstance(j, dict) and j.get("data"):
            first = j["data"][0]["id"]
            last = j["data"][-1]["id"]
            print(f"  offset={off:3d} -> status={code} n={len(j['data'])} first_id={first} last_id={last}")
        else:
            print(f"  offset={off:3d} -> status={code} body={str(j)[:120]}")

    print("\nD) SORTOWANIE / parametry")
    for params in ("sort=created_at:desc", "sort=date", "sort=created_time", "order=desc"):
        code, j = get(API + "?offset=0&limit=5&query=iphone&" + params)
        ids = [d["id"] for d in j.get("data", [])] if isinstance(j, dict) else None
        print(f"  {params:24s} -> status={code} ids={ids}")

    print("\nE) BEZ query (najnowsze cale OLX)")
    show_top(API + "?offset=0&limit=10")


if __name__ == "__main__":
    main()