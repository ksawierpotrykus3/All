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

# Test known categories:
# 2050: Buty męskie / Sneakersy
# 79: Swetry męskie
# 97: Zegarki męskie
# 5591: Piłki do futbolu australijskiego

cats = [
    (2050, "Sneakersy męskie"),
    (79, "Swetry męskie"),
    (97, "Zegarki męskie"),
    (5591, "Futbol australijski - piłki")
]

print("=== POTWIERDZENIE DZIALANIA FILTRA KATEGORII catalog_ids W JSON API ===")
for cid, name in cats:
    url = f"https://www.vinted.pl/api/v2/catalog/items?catalog_ids={cid}&per_page=5&order=newest_first"
    r = s.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        j = r.json()
        total = j.get("pagination", {}).get("total_entries")
        items = j.get("items", [])
        print(f"\nKategoria: {name} (ID {cid}) -> Total: {total}, Otrzymano: {len(items)}")
        for it in items:
            print(f"  - [{it.get('id')}] {it.get('title')} | Brand: {it.get('brand_title')} | Price: {it.get('price',{}).get('amount')} PLN")
    else:
        print(f"Kategoria: {name} -> Błąd HTTP {r.status_code}")
