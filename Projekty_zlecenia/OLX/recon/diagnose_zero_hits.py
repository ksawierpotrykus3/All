# coding: utf-8
"""
Diagnostyka: dlaczego monitor_20min.py ma 0 trafien.

Dowod inzynierski: skanuje ID wokol aktualnego max_id (wstecz + w przod)
i wypisuje SUROWY rozklad:
  - status 200 vs 404
  - category.id / category.type
  - region / cena / partner / tytul

Dzieki temu widac, czy filtry sa za waskie, czy ID w gore to luki (404).
"""
import collections
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def get_json(url, timeout=15):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def get_max_id():
    code, j = get_json(API + "?offset=0&limit=50")
    if code != 200 or not j:
        return None, f"code={code}"
    data = j.get("data", [])
    return max(d["id"] for d in data), "ok"


def main():
    mx, msg = get_max_id()
    print(f"max_id={mx} ({msg})")

    cat_counter = collections.Counter()
    type_counter = collections.Counter()
    region_counter = collections.Counter()
    partner_counter = collections.Counter()
    status_counter = collections.Counter()
    found_200 = 0

    # 1) wstecz od max_id: istniejace oferty (pokazuje rzeczywisty rozklad)
    print("\n=== SKAN WSTECZ (istniejace ID) ===")
    for oid in range(mx, mx - 300, -1):
        code, j = get_json(API + str(oid) + "/")
        status_counter[code] += 1
        if code == 200 and j:
            found_200 += 1
            cat = j.get("category") or {}
            loc = j.get("location") or {}
            region = (loc.get("region") or {}).get("name") or ""
            partner = (j.get("partner") or {}).get("code") or ""
            price = None
            for p in j.get("params", []) or []:
                if p.get("key") == "price":
                    price = p.get("value", {}).get("value")
                    break
            cat_counter[cat.get("id")] += 1
            type_counter[cat.get("type")] += 1
            region_counter[region] += 1
            partner_counter[partner] += 1
            if found_200 <= 25:
                print(f"  id={oid} cat.id={cat.get('id')} type={cat.get('type')} "
                      f"region={region} cena={price} partner={partner} "
                      f"| {j.get('title','')[:40]}")

    print(f"\n[wstecz 300] status: {dict(status_counter)}")
    print(f"[wstecz 300] 200={found_200}")
    print(f"cat.id top: {cat_counter.most_common(20)}")
    print(f"cat.type: {type_counter.most_common(10)}")
    print(f"region top: {region_counter.most_common(10)}")
    print(f"partner top: {partner_counter.most_common(10)}")

    # 2) w przod od max_id: co widzi detektor monitora
    print("\n=== SKAN W PRZOD (przyszle ID - co widzi detektor) ===")
    fwd_status = collections.Counter()
    fwd_200_cats = []
    fwd_200 = 0
    for oid in range(mx + 1, mx + 301):
        code, j = get_json(API + str(oid) + "/")
        fwd_status[code] += 1
        if code == 200 and j:
            fwd_200 += 1
            cat = j.get("category") or {}
            fwd_200_cats.append((oid, cat.get("id"), cat.get("type"), j.get("title", "")[:40]))
            if fwd_200 <= 15:
                print(f"  200! id={oid} cat.id={cat.get('id')} type={cat.get('type')} "
                      f"| {j.get('title','')[:50]}")
    print(f"[w przod 300] status: {dict(fwd_status)}, 200={fwd_200}")
    if fwd_200_cats:
        print(f"[w przod 300] trafienia 200: {fwd_200_cats}")


if __name__ == "__main__":
    main()