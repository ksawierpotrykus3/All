from curl_cffi import requests as creq
import json

s = creq.Session(impersonate="chrome124")

# 1. Warm up session
print("Pobieram stronę główną dla tokenów...")
r0 = s.get("https://www.vinted.pl/", timeout=15)
token = s.cookies.get("access_token_web")
print(f"Token access_token_web: {token[:30]}...")

# 2. Test headers with Bearer token
headers = {
    "Authorization": f"Bearer {token}",
    "X-Anonymous-Id": s.cookies.get("anon_id", ""),
    "Accept": "application/json, text/plain, */*",
}

endpoints = [
    ("GET", "https://www.vinted.pl/api/v2/catalog/filters", None),
    ("GET", "https://www.vinted.pl/api/v2/catalog/filters/facets?search_text=nike", None),
    ("GET", "https://www.vinted.pl/api/v2/catalog/faceted_categories", None),
    ("GET", "https://www.vinted.pl/api/v2/items/9784678171", None),
    ("POST", "https://www.vinted.pl/api/v2/purchases/checkout/build", {"purchase_items": [{"id": 9784678171, "type": "item"}]}),
]

print("\n=== TESTOWANIE ENDPOINTOW Z TOKENEM BEARER ===")
for method, url, payload in endpoints:
    if method == "GET":
        r = s.get(url, headers=headers, timeout=10)
    else:
        r = s.post(url, headers=headers, json=payload, timeout=10)
        
    print(f"[{method}] {url.split('api/v2/')[-1]:40} -> HTTP {r.status_code} (Size: {len(r.content)} B)")
    if r.status_code == 200:
        j = r.json()
        print("   SUKCES! Odpowiedź:", json.dumps(j, ensure_ascii=False)[:300])
    else:
        print("   Odpowiedź:", r.text[:200])
