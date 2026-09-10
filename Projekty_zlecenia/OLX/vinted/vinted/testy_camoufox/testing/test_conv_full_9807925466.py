# coding: utf-8
"""Pelna odpowiedz POST /conversations na item 9807925466 + lista transakcji."""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

ITEM = 9807925466
SELLER = 161574001

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

r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(ITEM),
                 "opposite_user_id": SELLER, "brand_id": 1,
                 "catalog_id": 3588, "color_id": 1, "status_id": 4, "size_id": None},
           headers=H, impersonate=BrowserType.chrome146, timeout=30,
           allow_redirects=False)
out.append(f"POST /conversations -> {r.status_code}")
out.append(json.dumps(r.json(), ensure_ascii=False)[:1500])
time.sleep(1)

Path(BASE_DIR / "conv_full_9807925466_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
