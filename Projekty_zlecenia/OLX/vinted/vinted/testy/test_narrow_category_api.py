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

# Subcategories that have very few items:
# 5490: typewriters (maszyny do pisania)
# 5489: paper shredders (niszczarki do papieru)
# 5484: laminators (laminatory)

narrow_cats = [5490, 5489, 5484]

print("=== TEST WASKICH KATEGORII W API /api/v2/catalog/items ===")
for cat in narrow_cats:
    for param_format in [f"catalog_ids={cat}", f"catalog_ids[]={cat}", f"catalog[]={cat}"]:
        url = f"https://www.vinted.pl/api/v2/catalog/items?{param_format}&per_page=20&order=newest_first"
        r = s.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            j = r.json()
            total = j.get("pagination", {}).get("total_entries")
            items = j.get("items", [])
            print(f"Format: {param_format:20} -> Total: {total} | Items count: {len(items)}")
            if items:
                print(f"   Przykładowy tytuł: '{items[0].get('title')}'")
        else:
            print(f"Format: {param_format:20} -> HTTP {r.status_code}")
