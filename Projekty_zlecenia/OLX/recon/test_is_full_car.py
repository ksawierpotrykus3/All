# coding: utf-8
"""Test: czy sygnatura _is_full_car lapie realne auta (nie czesci) na zywo."""
import sys
from pathlib import Path
from curl_cffi import requests as creq

sys.path.insert(0, str(Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\recon")))
import monitor_20min as m

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

# pobierz auta z roznych marek
for q in ["bmw", "opel", "audi", "volkswagen"]:
    r = creq.get(API + f"?offset=0&limit=50&query={q}", impersonate=IMP, timeout=15)
    j = r.json()
    auta = 0
    czesci = 0
    przyk = []
    for d in j.get("data", []):
        cat_type = (d.get("category") or {}).get("type")
        if cat_type != "automotive":
            continue
        if m._is_full_car(d):
            auta += 1
            if len(przyk) < 3:
                region = (d.get("location") or {}).get("region", {}).get("name", "")
                cena = None
                for p in d.get("params", []):
                    if p.get("key") == "price":
                        cena = p.get("value", {}).get("value")
                        break
                przyk.append(f"    AUTO {d.get('id')} {region} {cena}zl | {d.get('title','')[:40]!r}")
        else:
            czesci += 1
    print(f"\nquery={q}: pelne auta={auta}, czesci/akcesoria={czesci}")
    for p in przyk:
        print(p)