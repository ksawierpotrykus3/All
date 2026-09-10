# coding: utf-8
"""Szybki async test: ile aut do 12k Mazowsze przybywa na swiezych ID."""
import asyncio
import sys
from pathlib import Path
from curl_cffi.requests import AsyncSession

sys.path.insert(0, str(Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\recon")))
import monitor_20min as m

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


async def main():
    # seed: max z listy
    async with AsyncSession(impersonate=IMP, timeout=15) as s:
        r = await s.get(API + "?offset=0&limit=50")
        mx = max(d["id"] for d in r.json()["data"])
    print(f"seed max_id={mx}")

    auta_all = 0
    auta_hit = 0
    przyklady = []

    sem = asyncio.Semaphore(20)

    async def fetch(sess, oid):
        async with sem:
            try:
                r = await sess.get(API + str(oid) + "/")
                if r.status_code == 200:
                    return oid, r.json().get("data")
                return oid, None
            except Exception:
                return oid, None

    # skan 1200 ID wstecz (co 1) asynchronicznie
    start = mx - 1200
    async with AsyncSession(impersonate=IMP, timeout=10) as sess:
        tasks = [fetch(sess, i) for i in range(start, mx)]
        results = await asyncio.gather(*tasks)

    for oid, d in results:
        if not d:
            continue
        cat = d.get("category") or {}
        if cat.get("type") != "automotive":
            continue
        if not m._is_full_car(d):
            continue
        auta_all += 1
        region = (d.get("location") or {}).get("region", {}).get("name", "")
        partner = (d.get("partner") or {}).get("code") or ""
        cena = None
        for p in d.get("params", []) or []:
            if p.get("key") == "price":
                cena = p.get("value", {}).get("value")
                break
        cena_f = m._parse_price(cena)
        if (partner != "otomoto_pl_form" and "mazowieck" in region.lower()
                and cena_f is not None and cena_f <= 12000):
            auta_hit += 1
            if len(przyklady) < 5:
                przyklady.append(f"  {oid} {region} {cena_f}zl | {d.get('title','')[:45]!r}")

    print(f"\nW 1200 ID wstecz: pelne auta={auta_all}, auta z filtrem (Mazowsze<=12k)={auta_hit}")
    for p in przyklady:
        print(p)


if __name__ == "__main__":
    asyncio.run(main())