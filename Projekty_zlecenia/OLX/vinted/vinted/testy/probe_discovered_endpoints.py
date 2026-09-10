import json
from curl_cffi import requests as creq

s = creq.Session(impersonate="chrome124")

endpoints_to_test = [
    ("GET", "https://www.vinted.pl/api/v2/catalog/filters"),
    ("GET", "https://www.vinted.pl/api/v2/catalog/filters/facets"),
    ("GET", "https://www.vinted.pl/api/v2/catalog/filters/search?filterSearchText=nike"),
    ("GET", "https://www.vinted.pl/api/v2/catalog/faceted_categories"),
    ("GET", "https://www.vinted.pl/api/v2/catalog/blocks"),
    ("GET", "https://www.vinted.pl/api/v2/offer/estimate_with_fees"),
    ("POST", "https://www.vinted.pl/api/v2/purchases/checkout/build"),
]

print("=== PROBOWANIE ODKRYTYCH ENDPOINTOW NA ZYWO ===")
for method, url in endpoints_to_test:
    try:
        if method == "GET":
            r = s.get(url, timeout=10)
        else:
            r = s.post(url, json={"purchase_items": [{"id": 123456, "type": "item"}]}, timeout=10)
            
        print(f"[{method}] {url.split('api/v2/')[-1]:35} -> HTTP {r.status_code} (Length: {len(r.content)} B)")
        if r.status_code in [200, 400, 401, 403, 422]:
            try:
                j = r.json()
                print("   Odpowiedź JSON:", str(j)[:200])
            except Exception:
                print("   Tekst:", r.text[:150])
    except Exception as e:
        print(f"[{method}] {url} -> Błąd: {e}")
