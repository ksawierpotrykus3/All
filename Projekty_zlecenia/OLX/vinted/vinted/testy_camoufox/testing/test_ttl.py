# coding: utf-8
"""Test TTL: cyklicznie sprawdzaj czy item wrocil do katalogu + status transakcji.

Item: 9824065306 (byl w statusie 200 -> payment/failure -> 220 -> DELETE conversations 200).
Pytanie: kiedy item wraca do katalogu (TTL rezerwacji)?
"""
import json
import time
from datetime import datetime
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

ITEM = 9824065306
TXN = 21905860558

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
logf = BASE_DIR / "ttl_log.txt"
out = []

start = time.time()
for i in range(40):  # co 45s -> do 30 min
    ts = datetime.now().strftime("%H:%M:%S")
    # item
    try:
        r = s.get(f"https://www.vinted.pl/api/v2/items/{ITEM}", headers=H,
                  impersonate=BrowserType.chrome146, timeout=30)
        item_state = f"http={r.status_code}"
        if r.status_code == 200:
            item_state += f" status={r.json().get('item', {}).get('status')}"
    except Exception as e:  # noqa: BLE001
        item_state = f"ERR {e}"
    # transakcja
    try:
        r = s.get(f"https://www.vinted.pl/api/v2/transactions/{TXN}", headers=H,
                  impersonate=BrowserType.chrome146, timeout=30)
        t = r.json().get("transaction")
        txn_state = f"txn_http={r.status_code}"
        if t:
            txn_state += f" status={t.get('status')}"
    except Exception as e:  # noqa: BLE001
        txn_state = f"txn ERR {e}"
    line = f"[{ts}] el={int(time.time()-start)}s item={item_state} | {txn_state}"
    print(line, flush=True)
    out.append(line)
    Path(logf).write_text("\n".join(out), encoding="utf-8")
    if item_state.startswith("http=200"):
        out.append(f"ITEM WRÓCIŁ po {int(time.time()-start)}s")
        Path(logf).write_text("\n".join(out), encoding="utf-8")
        print("ITEM WRÓCIŁ")
        break
    time.sleep(45)
else:
    out.append("KONIEC TESTU (nie wrocil)")
    Path(logf).write_text("\n".join(out), encoding="utf-8")

print("DONE -> ttl_log.txt")
