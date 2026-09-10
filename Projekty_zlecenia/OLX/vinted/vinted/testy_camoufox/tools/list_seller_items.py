# coding: utf-8
"""Lista itemow sprzedawcy 3180795364 przez publiczny endpoint - szukamy swiezych."""
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

r = s.get("https://www.vinted.pl/api/v2/users/3180795364/items?per_page=100&page=1",
          headers=H, impersonate=BrowserType.chrome146, timeout=30)
out = [f"http={r.status_code}"]
if r.status_code == 200:
    data = r.json()
    items = data.get("items", [])
    out.append(f"count={len(items)}")
    for it in items:
        out.append(f"  id={it.get('id')} title={it.get('title')} status_id={it.get('status_id')} "
                   f"is_reserved={it.get('is_reserved')} photo={str(it.get('photo', {}))[:60]}")
    total = data.get("pagination", {}).get("total_entries")
    out.append(f"total_entries={total}")
else:
    out.append(r.text[:300])
Path(BASE_DIR / "seller_items_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
