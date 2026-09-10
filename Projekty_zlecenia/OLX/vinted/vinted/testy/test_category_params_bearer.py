from curl_cffi import requests as creq
import json

s = creq.Session(impersonate="chrome124")

# Warm up
r0 = s.get("https://www.vinted.pl/", timeout=15)
token = s.cookies.get("access_token_web")

headers = {
    "Authorization": f"Bearer {token}",
    "X-Anonymous-Id": s.cookies.get("anon_id", ""),
    "Accept": "application/json, text/plain, */*",
}

# Test different category parameters on /api/v2/catalog/items
category_params = [
    "catalog_ids=1904",
    "catalog_id=1904",
    "category_id=1904",
    "category_ids=1904",
    "catalog[]=1904",
    "catalog_ids[]=1904",
    "category_ids[]=1904",
    "attribute_ids[catalog]=1904",
    "attribute_ids[catalog][]=1904",
]

print("=== TEST PARAMETROW KATEGORII NA /api/v2/catalog/items Z TOKENEM BEARER ===")
for p in category_params:
    url = f"https://www.vinted.pl/api/v2/catalog/items?{p}&per_page=10&order=newest_first"
    r = s.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        j = r.json()
        items = j.get("items", [])
        total = j.get("pagination", {}).get("total_entries")
        print(f"Param: {p:35} -> HTTP 200 | total_entries: {total} | items count: {len(items)}")
        if items:
            print(f"   First item title: {items[0].get('title')[:30]} | user: {items[0].get('user',{}).get('login')}")
    else:
        print(f"Param: {p:35} -> HTTP {r.status_code}")
