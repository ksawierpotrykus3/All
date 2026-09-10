# coding: utf-8
"""
Test asynchronicznego skanowania ID OLX (curl_cffi AsyncSession).

Cel: zmierzyc, jakie tempo (req/s) wytrzyma OLX bez blokady 403,
i czy asynchroniczne skanowanie nadaza za kreacja ~2.2 ID/s.

Skan 300 ID: mierz czas, statusy, tempo.
"""
import asyncio
import time
from curl_cffi.requests import AsyncSession

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


async def scan(start_id, count, concurrency):
    sem = asyncio.Semaphore(concurrency)
    codes = {}

    async def fetch(oid):
        async with sem:
            try:
                async with AsyncSession(impersonate=IMP, timeout=10) as s:
                    r = await s.get(API + str(oid) + "/")
                return oid, r.status_code
            except Exception as e:  # noqa: BLE001
                return oid, -1

    tasks = [fetch(start_id + i) for i in range(count)]
    results = await asyncio.gather(*tasks)
    for oid, code in results:
        codes[code] = codes.get(code, 0) + 1
    return codes


async def main():
    concurrency = 20
    count = 300
    # seed: aktualne max_id
    async with AsyncSession(impersonate=IMP, timeout=15) as s:
        r = await s.get(API + "?offset=0&limit=50")
        mx = max(d["id"] for d in r.json()["data"])
    print(f"seed max_id={mx}, skan {count} ID od {mx+1}, conc={concurrency}")

    t0 = time.time()
    codes = await scan(mx + 1, count, concurrency)
    dt = time.time() - t0

    n200 = codes.get(200, 0)
    print(f"\n=== WYNIK ===")
    print(f"przeskanowano={count} w {dt:.2f}s")
    print(f"tempo={count/dt:.2f} ID/s")
    print(f"nowe ogloszenia (200)={n200}")
    print(f"statusy={codes}")
    if codes.get(403):
        print("BLOKADA 403 - za duze tempo!")
    else:
        print("Brak 403 - tempo OK")


if __name__ == "__main__":
    asyncio.run(main())