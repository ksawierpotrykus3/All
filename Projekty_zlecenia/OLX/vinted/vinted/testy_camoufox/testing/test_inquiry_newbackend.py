# coding: utf-8
"""Nowy backend messaging: POST /messaging/main/inquiries - czy tworzy transakcje i blokuje item?"""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

ITEM = 9822946391  # swiezy item "Podrecznik geografia klasa 2"
SELLER = 3180795364

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

# 1. item przed
r = s.get(f"https://www.vinted.pl/api/v2/items/{ITEM}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"ITEM przed: http={r.status_code}")

# 2. POST inquiry (nowy backend)
try:
    r = s.post("https://www.vinted.pl/messaging/main/inquiries",
               json={"item_ids": [str(ITEM)], "receiver_id": SELLER},
               headers=H, impersonate=BrowserType.chrome146, timeout=30)
    out.append(f"POST /messaging/main/inquiries -> {r.status_code} {r.text[:400]}")
except Exception as e:
    out.append(f"POST inquiries ERR {e}")

# 3. item po
r = s.get(f"https://www.vinted.pl/api/v2/items/{ITEM}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"ITEM po inquiry: http={r.status_code}")

# 4. czy powstala transakcja? (konwersacje z tym itemem)
time.sleep(1)
try:
    r = s.get(f"https://www.vinted.pl/api/v2/conversations?item_id={ITEM}&per_page=5",
              headers=H, impersonate=BrowserType.chrome146, timeout=30)
    out.append(f"CONVERSATIONS -> {r.status_code} {r.text[:400]}")
except Exception as e:
    out.append(f"CONVERSATIONS ERR {e}")

Path(BASE_DIR / "inquiry_test_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
