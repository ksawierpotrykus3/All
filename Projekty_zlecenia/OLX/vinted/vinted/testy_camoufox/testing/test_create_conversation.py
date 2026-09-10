# coding: utf-8
"""Test tworzenia transakcji przez POST /api/v2/conversations (initiator=buy).

Na itemie juz w transakcji: sprawdza czy endpoint jest idempotentny i jaki zwraca
shape odpowiedzi (transaction_id).
"""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
ITEM_ID = 9807925466
SELLER_ID = 161574001
URL = "https://www.vinted.pl/api/v2/conversations"

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
    "referer": f"https://www.vinted.pl/items/{ITEM_ID}",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

body = {"initiator": "buy", "item_id": ITEM_ID, "opposite_user_id": SELLER_ID}
r = s.post(URL, json=body, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
print(f"[POST /conversations] {r.status_code}")
print(f"headers: {dict(r.headers)}")
print(f"body: {r.text[:4000]}")

# zapis wyniku
(BASE_DIR / "wynik_create_conversation.json").write_text(
    json.dumps({"status": r.status_code, "body": r.text[:4000], "headers": dict(r.headers)},
               ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_create_conversation.json")
