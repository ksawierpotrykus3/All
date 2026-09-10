# coding: utf-8
"""Stan itemu 9807925466 (Genesis Krypton 700) + stara transakcja 21872241924."""
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
out = []

r = s.get("https://www.vinted.pl/api/v2/items/9807925466", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"ITEM 9807925466 -> http={r.status_code}")
if r.status_code == 200:
    it = r.json().get("item", {})
    out.append(f"  title={it.get('title')} user_id={it.get('user', {}).get('id')} "
               f"status_id={it.get('status_id')} is_reserved={it.get('is_reserved')}")

r = s.get("https://www.vinted.pl/api/v2/transactions/21872241924", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"TXN 21872241924 -> http={r.status_code}")
if r.status_code == 200:
    t = r.json().get("transaction", {})
    out.append(f"  status={t.get('status')} status_updated_at={t.get('status_updated_at')} "
               f"item_id={t.get('item_id')} user_side={t.get('user_side')}")

Path(BASE_DIR / "item_9807925466_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
