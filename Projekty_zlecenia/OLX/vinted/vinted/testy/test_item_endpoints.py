import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from curl_cffi import requests as creq
import json

s = creq.Session(impersonate="chrome124")
r0 = s.get("https://www.vinted.pl/", timeout=15)
token = s.cookies.get("access_token_web")

headers = {
    "Authorization": f"Bearer {token}",
    "X-Anonymous-Id": s.cookies.get("anon_id", ""),
    "Accept": "application/json, text/plain, */*",
}

# Get a real fresh item_id from catalog
r_cat = s.get("https://www.vinted.pl/api/v2/catalog/items?order=newest_first&per_page=1", headers=headers)
item_id = r_cat.json()["items"][0]["id"]
print(f"Testing real fresh item_id: {item_id}")

item_endpoints = [
    f"https://www.vinted.pl/api/v2/items/{item_id}",
    f"https://www.vinted.pl/api/v2/items/{item_id}/details",
    f"https://www.vinted.pl/api/v2/items/{item_id}?localize=false",
    f"https://www.vinted.pl/api/v2/catalog/items/{item_id}",
    f"https://www.vinted.pl/api/v2/item/{item_id}",
    f"https://www.vinted.pl/api/v2/products/{item_id}",
    f"https://www.vinted.pl/api/v2/items/{item_id}/similar",
    f"https://www.vinted.pl/api/v2/items/{item_id}/photos",
]

print("=== TESTOWANIE ENDPOINTOW POJEDYNCZEGO PRZEDMIOTU ===")
for url in item_endpoints:
    r = s.get(url, headers=headers, timeout=10)
    print(f"{url.split('api/v2/')[-1]:45} -> HTTP {r.status_code} (Length: {len(r.content)} B)")
    if r.status_code == 200:
        print("   SUKCES! JSON:", r.text[:200])
