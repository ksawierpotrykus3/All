# coding: utf-8
"""
Diagnostyka: dlaczego detektor async ma 0 trafien mimo skanowania 2760 ID?

Skanuje okno ID, ktore przechodzil detektor, i wypisuje:
  - ile bylo 200
  - rozklad category.id
  - pierwsze tytuly
"""
import asyncio
import collections
from curl_cffi.requests import AsyncSession

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


async def main():
    start = 1093557520
    end = 1093558366
    count = end - start
    codes = collections.Counter()
    cats = collections.Counter()
    samples = []
    hits_200 = 0

    sem = asyncio.Semaphore(20)

    async def fetch(session, oid):
        async with sem:
            try:
                r = await session.get(API + str(oid) + "/")
                if r.status_code == 200:
                    d = r.json().get("data")
                    return oid, r.status_code, d
                return oid, r.status_code, None
            except Exception as e:  # noqa: BLE001
                return oid, -1, None

    async with AsyncSession(impersonate=IMP, timeout=10) as session:
        tasks = [fetch(session, i) for i in range(start, end)]
        results = await asyncio.gather(*tasks)

    for oid, code, data in results:
        codes[code] += 1
        if code == 200 and data:
            hits_200 += 1
            cat = (data.get("category") or {}).get("id")
            cats[cat] += 1
            if len(samples) < 10:
                samples.append(f"id={oid} cat={cat} | {data.get('title','')[:50]}")

    print(f"zakres {start}..{end} ({count} ID)")
    print(f"statusy: {dict(codes)}")
    print(f"200 z data: {hits_200}")
    print(f"rozklad category.id: {cats.most_common(15)}")
    print("przyklady:")
    for s in samples:
        print(f"  {s}")


if __name__ == "__main__":
    asyncio.run(main())