# coding: utf-8
"""Test endpointow anulowania transakcji (nowy backend messaging).

Proba odblokowania itemu 9824065306 (transakcja 21905860558, status 220,
konwersacja 24722169871 juz usunieta DELETE /conversations).
"""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

TXN = 21905860558
CONV = 24722169871
ITEM = 9824065306

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

cands = [
    ("DELETE", f"https://www.vinted.pl/messaging/main/inquiries/{CONV}", None),
    ("DELETE", f"https://www.vinted.pl/api/v2/messaging/main/inquiries/{CONV}", None),
    ("POST", f"https://www.vinted.pl/api/v2/conversations/{CONV}/cancel", {}),
    ("POST", f"https://www.vinted.pl/api/v2/transactions/{TXN}/abandon", {}),
    ("DELETE", f"https://www.vinted.pl/api/v2/transactions/{TXN}/items", None),
    ("POST", f"https://www.vinted.pl/api/v2/transactions/{TXN}/close", {}),
]
for method, url, body in cands:
    try:
        if method == "DELETE":
            r = s.delete(url, headers=H, impersonate=BrowserType.chrome146, timeout=30,
                         allow_redirects=False)
        else:
            r = s.post(url, json=body or {}, headers=H, impersonate=BrowserType.chrome146,
                       timeout=30, allow_redirects=False)
        out.append(f"{method} {url.split('vinted.pl')[-1]} -> {r.status_code} {r.text[:250]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{method} {url} -> ERR {e}")
    time.sleep(0.3)

# status po
r = s.get(f"https://www.vinted.pl/api/v2/transactions/{TXN}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"TXN po: http={r.status_code}")
if r.status_code == 200:
    t = r.json().get("transaction", {})
    out.append(f"  status={t.get('status')}")
r = s.get(f"https://www.vinted.pl/api/v2/items/{ITEM}", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"ITEM po: http={r.status_code}")

Path(BASE_DIR / "cancel2_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> cancel2_out.txt")
