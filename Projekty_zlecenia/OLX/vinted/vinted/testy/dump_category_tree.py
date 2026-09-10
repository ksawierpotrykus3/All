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

r = s.get("https://www.vinted.pl/api/v2/catalog/faceted_categories", headers=headers, timeout=10)
if r.status_code == 200:
    data = r.json()
    print("=== STRUKTURA KATEGORII W API ===")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])

r_filters = s.get("https://www.vinted.pl/api/v2/catalog/filters", headers=headers, timeout=10)
if r_filters.status_code == 200:
    print("\n=== WSZYSTKIE FILTRY W API ===")
    filters = r_filters.json().get("filters", [])
    for f in filters:
        print(f"Filter: code='{f.get('code')}', title='{f.get('title')}', id={f.get('id')}, selection_type='{f.get('selection_type')}'")
