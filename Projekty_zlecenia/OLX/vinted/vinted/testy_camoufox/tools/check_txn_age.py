# coding: utf-8
"""Wiek transakcji status=1 - czy itemy wciaz zablokowane po X minutach."""
import json
import time
from datetime import datetime
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

TXNS = [
    (21905766891, 9824029893),
    (21905820221, 9824050339),
    (21905827430, 9819331568),
    (21905830067, 9824054052),
    (21905832457, 9824054898),
    (21905842574, 9817321308),
    (21905847167, 9824060492),
    (21905851448, 9824062043),
    (21905854215, 9824062669),
    (21905905489, 9824081370),
]
now = datetime.now().astimezone()
out = [f"NOW={now.isoformat(timespec='seconds')}"]
for txn, item in TXNS:
    r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn}", headers=H,
              impersonate=BrowserType.chrome146, timeout=30)
    status = None
    updated = None
    if r.status_code == 200:
        t = r.json().get("transaction", {})
        status = t.get("status")
        updated = t.get("status_updated_at")
    ri = s.get(f"https://www.vinted.pl/api/v2/items/{item}", headers=H,
               impersonate=BrowserType.chrome146, timeout=30)
    age = ""
    if updated:
        try:
            dt = datetime.fromisoformat(updated)
            age = f"age={(now - dt).total_seconds()/60:.1f}min"
        except Exception:
            pass
    line = (f"txn={txn} item={item} txn_http={r.status_code} status={status} "
            f"updated={updated} {age} item_http={ri.status_code}")
    out.append(line)
    print(line)
    time.sleep(0.3)
txt = "\n".join(out)
Path(BASE_DIR / "txn_age_out.txt").write_text(txt, encoding="utf-8")
print("OK -> txn_age_out.txt")
