# coding: utf-8
"""Diagnostyka: dlaczego auta (cat 183) nie wpadaja. Sprawdzam region i cene na zywo."""
import asyncio
import collections
from curl_cffi.requests import AsyncSession

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


async def main():
    start = 1093574000
    end = 1093582000
    codes = collections.Counter()
    cat183 = []
    region_counter = collections.Counter()
    price_counter = collections.Counter()

    sem = asyncio.Semaphore(20)

    async def fetch(session, oid):
        async with sem:
            try:
                r = await session.get(API + str(oid) + "/")
                if r.status_code == 200:
                    return oid, r.status_code, r.json().get("data")
                return oid, r.status_code, None
            except Exception as e:
                return oid, -1, None

    async with AsyncSession(impersonate=IMP, timeout=10) as session:
        tasks = [fetch(session, i) for i in range(start, end, 3)]  # co 3. ID (proba)
        results = await asyncio.gather(*tasks)

    for oid, code, data in results:
        codes[code] += 1
        if code == 200 and data:
            cat = (data.get("category") or {}).get("id")
            if cat == 183:
                region = (data.get("location") or {}).get("region", {}).get("name", "")
                price = None
                for p in data.get("params", []) or []:
                    if p.get("key") == "price":
                        price = p.get("value", {}).get("value")
                        break
                region_counter[region] += 1
                price_counter[str(price)] += 1
                if len(cat183) < 10:
                    cat183.append(f"id={oid} region={region!r} cena={price!r} | {data.get('title','')[:45]!r}")

    print(f"zakres prob: {start}..{end} co 3 (statusy: {dict(codes)})")
    print(f"\noferty cat=183 (auta): {sum(region_counter.values())}")
    print(f"regiony aut: {region_counter.most_common(10)}")
    print(f"ceny aut: {price_counter.most_common(10)}")
    print("przyklady aut:")
    for s in cat183:
        print(f"  {s}")


if __name__ == "__main__":
    asyncio.run(main())