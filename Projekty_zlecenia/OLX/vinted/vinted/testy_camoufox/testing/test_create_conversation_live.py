# coding: utf-8
"""Test: znajdz zywy item z katalogu przez curl_cffi i utworz transakcje
przez POST /api/v2/conversations (initiator=buy). Pełny dowod na nowym itemie."""
import json
import time
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

results = {}

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

# 1) Katalog: nowe przedmioty, kategoria ubrania meskie koszulki (tanie)
url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?catalog_ids%5B%5D=44&order=newest_first&page=1&per_page=5&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
print(f"[CATALOG] {r.status_code} len={len(r.text)}")
results["catalog"] = {"status": r.status_code, "len": len(r.text)}

items = []
try:
    data = r.json()
    items = data.get("items", [])
    for it in items[:5]:
        print(f"  item {it['id']} | user {it['user']['id']} ({it['user']['login']}) "
              f"| price {it['price'].get('amount')} {it['price'].get('currency_code')} "
              f"| status {it.get('status')} | '{it.get('title','')[:40]}'")
except Exception as e:  # noqa: BLE001
    print(f"[CATALOG] parse error: {e}")
    print(r.text[:1500])

# 2) Wez pierwszy zywy item (status != sold, nie z naszego konta)
target = None
for it in items:
    if it.get("status") != "sold" and it["user"]["id"] not in (3180346878,):
        target = it
        break

if not target:
    print("\nBrak zywego itemu w wynikach - koniec.")
    results["error"] = "no live item"
else:
    item_id = target["id"]
    seller_id = target["user"]["id"]
    print(f"\n[TEST] uzywam item {item_id}, seller {seller_id}")

    # 3) POST /conversations initiator=buy
    body = {"initiator": "buy", "item_id": item_id, "opposite_user_id": seller_id}
    r = s.post("https://www.vinted.pl/api/v2/conversations", json=body, headers=H,
               impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    print(f"\n[POST /conversations] {r.status_code}")
    results["create_conversation"] = {"status": r.status_code, "body": r.text[:3000]}
    txn_id = None
    try:
        j = r.json()
        conv = j.get("conversation", {})
        txn = conv.get("transaction") or {}
        txn_id = txn.get("id")
        print(f"  conversation.id = {conv.get('id')}")
        print(f"  transaction.id = {txn_id}")
        print(f"  transaction.status = {txn.get('status')}")
        print(f"  transaction.purchase_id = {txn.get('purchase_id')}")
        print(f"  available_actions = {txn.get('available_actions')}")
        print(f"  item_id = {txn.get('item_id')}")
    except Exception as e:  # noqa: BLE001
        print(f"  parse error: {e}")
        print(f"  raw: {r.text[:1500]}")

    # 4) Status transakcji
    if txn_id:
        r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
                  impersonate=BrowserType.chrome146, timeout=30)
        print(f"\n[GET transaction {txn_id}] {r.status_code}")
        results["transaction_status"] = {"status": r.status_code, "body": r.text[:800]}
        try:
            tj = r.json()
            print(f"  status={tj.get('status')} id={tj.get('id')}")
        except Exception as e:  # noqa: BLE001
            print(f"  parse error: {e} {r.text[:300]}")

(BASE_DIR / "wynik_create_conversation_live.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nZapisano: wynik_create_conversation_live.json")
