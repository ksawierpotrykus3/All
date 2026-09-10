# coding: utf-8
"""Sprawdz statusy wszystkich wczesniejszych transakcji testowych."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

TXNS = [21905766891, 21905820221, 21905827430, 21905830067, 21905832457,
        21905842574, 21905847167, 21905851448, 21905854215, 21905905489,
        21905860558]

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:  # noqa: BLE001
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
for txn in TXNS:
    r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn}", headers=H,
              impersonate=BrowserType.chrome146, timeout=30)
    if r.status_code == 200:
        t = r.json().get("transaction", {})
        out.append(f"[{txn}] http=200 status={t.get('status')} item={t.get('item_id')} "
                   f"title={str(t.get('item_title'))[:30]}")
    else:
        out.append(f"[{txn}] http={r.status_code}")

Path(BASE_DIR / "txn_states_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> txn_states_out.txt")
