# coding: utf-8
"""Szukamy itemu 9807925466 w katalogu (API) - pelny JSON elementu."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "referer": "https://www.vinted.pl/",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

r = s.get("https://www.vinted.pl/api/v2/catalog/items?search_text=genesis%20krypton%20700"
          "&page=1&per_page=96&order=relevance",
          headers=H, impersonate=BrowserType.chrome146, timeout=30)
out = [f"http={r.status_code}"]
data = r.json()
found = None
for it in data.get("items", []):
    if it.get("id") == 9807925466:
        found = it
        break
if found is None:
    out.append("ITEM 9807925466 NIE znaleziony w wynikach katalogu!")
    out.append(f"count={len(data.get('items', []))}")
else:
    keys = ["id", "title", "status", "is_visible", "is_reserved", "favourite_count",
            "available_actions", "seller_id", "total_item_price", "price", "brand_title",
            "catalog_id", "path", "photo", "user"]
    for k in keys:
        if k in found:
            v = found[k]
            if k in ("available_actions", "price", "user", "photo"):
                v = json.dumps(v, ensure_ascii=False)[:300]
            out.append(f"  {k} = {v}")
    # wszelkie flagi rezerwacji / zakupu
    for k, v in found.items():
        if isinstance(v, bool) or "reserv" in k or "status" in k or "sold" in k:
            out.append(f"  [flaga] {k} = {v}")
    out.append(f"count={len(data.get('items', []))}")
Path(BASE_DIR / "catalog_search_9807925466_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
