# coding: utf-8
"""Ile aut do 12k z Mazowsza faktycznie przybywa? Test na swiezych ID."""
import sys
from pathlib import Path
from curl_cffi import requests as creq

sys.path.insert(0, str(Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\recon")))
import monitor_20min as m

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

# skan ostatnich 500 ID wstecz (istniejace oferty) i policz auta spelniajace filtr
mx = None
r = creq.get(API + "?offset=0&limit=50", impersonate=IMP, timeout=15)
mx = max(d["id"] for d in r.json()["data"])
print(f"seed max_id={mx}")

auta_hit = 0
auta_all = 0
przyklady = []
for oid in range(mx, mx - 1500, -1):
    try:
        r = creq.get(API + str(oid) + "/", impersonate=IMP, timeout=10)
    except Exception:
        continue
    if r.status_code != 200:
        continue
    d = r.json().get("data")
    cat = d.get("category") or {}
    if cat.get("type") != "automotive":
        continue
    if not m._is_full_car(d):
        continue
    auta_all += 1
    # filtr jak w classify
    region = (d.get("location") or {}).get("region", {}).get("name", "")
    partner = (d.get("partner") or {}).get("code") or ""
    cena = None
    for p in d.get("params", []) or []:
        if p.get("key") == "price":
            cena = p.get("value", {}).get("value")
            break
    cena_f = m._parse_price(cena)
    if (partner != "otomoto_pl_form" and
        "mazowieck" in region.lower() and
        cena_f is not None and cena_f <= 12000):
        auta_hit += 1
        if len(przyklady) < 5:
            przyklady.append(f"  {oid} {region} {cena_f}zl | {d.get('title','')[:45]!r}")

print(f"\nW 1500 ID wstecz: pelne auta={auta_all}, z filtrem (Mazowsze<=12k)={auta_hit}")
for p in przyklady:
    print(p)