"""
probe_build_isolated.py — Priorytet 0: izolowany test, czy build przechodzi przez curl_cffi.

Rozstrzyga sprzeczność Faza N (build 200) vs Faza M/sekcja 29 (build 403).
Izoluje zmienne:
  - swiezosc cookies (exp claim access_token_web)
  - impersonate (firefox133 vs chrome146)
  - swieza transakcja z POST /conversations (initiator=buy)

Kazda proba na OSOBNYM itemie (kazdy build = jedna transakcja), z logiem:
  status, x-datadome header, transaction_id swiezy?, interwal od poprzedniej proby.

UWAGA: tworzy trwale transakcje status 1 (item pozostaje wolny wg 20.8.8).
Nie robi paymentu ani checkoutu platnosci.
"""
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = BASE_DIR / "cookies_profil.json"
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"


def _decode_jwt_exp(token: str):
    """Dekoduje exp claim z JWT (bez weryfikacji podpisu)."""
    import base64
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get("exp")
    except Exception as e:
        return f"decode_error:{e}"


def _load_cookies() -> dict:
    return {c["name"]: c["value"] for c in json.loads(COOKIES_PATH.read_text(encoding="utf-8"))}


def _freshness(cookies: dict) -> str:
    at = cookies.get("access_token_web", "")
    if not at:
        return "BRAK access_token_web"
    exp = _decode_jwt_exp(at)
    now = int(time.time())
    if isinstance(exp, int):
        return f"exp={exp} now={now} delta={exp - now}s {'OK' if exp > now else 'WYGLASL'}"
    return str(exp)


def _session(cookies: dict):
    s = cr.Session()
    for name, value in cookies.items():
        try:
            s.cookies.set(name, value)
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "priority": "u=3",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    })
    at = cookies.get("access_token_web")
    if at:
        s.headers["authorization"] = f"Bearer {at}"
    return s


def _find_fresh_item(s: cr.Session) -> dict | None:
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?price_to=100&order=newest_first&page=1&per_page=40&currency=PLN")
    r = s.get(url, headers={"x-csrf-token": CSRF, "x-anon-id": ANON},
              impersonate=BrowserType.firefox133, timeout=30)
    for it in r.json().get("items", []):
        if it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        return {"item_id": it["id"], "seller_id": it["user"]["id"], "title": it.get("title", "")[:50]}
    return None


def _create_txn(s: cr.Session, item: dict, impersonate) -> dict | None:
    r = s.post("https://www.vinted.pl/api/v2/conversations",
               json={"initiator": "buy", "item_id": str(item["item_id"]),
                     "opposite_user_id": item["seller_id"]},
               headers={"x-csrf-token": CSRF, "x-anon-id": ANON},
               impersonate=impersonate, timeout=30, allow_redirects=False)
    if r.status_code != 200:
        return {"status": r.status_code, "raw": r.text[:200]}
    conv = r.json().get("conversation", {})
    txn = conv.get("transaction") or {}
    return {"status": 200, "transaction_id": txn.get("id")}


def _build(s: cr.Session, txn_id, item_id, impersonate) -> dict:
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
               headers={"x-csrf-token": CSRF, "x-anon-id": ANON,
                        "referer": f"https://www.vinted.pl/items/{item_id}"},
               impersonate=impersonate, timeout=30, allow_redirects=False)
    return {
        "status": r.status_code,
        "x_datadome": r.headers.get("x-datadome", ""),
        "location": r.headers.get("location", "")[:80],
        "body_head": r.text[:150],
    }


def main():
    cookies = _load_cookies()
    results = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cookie_freshness": _freshness(cookies),
        "probes": [],
    }
    print(f"Cookie freshness: {results['cookie_freshness']}")

    s = _session(cookies)

    # Alternuj impersonate: firefox133 -> chrome146 -> firefox133 -> chrome146
    sequence = ["firefox133", "chrome146", "firefox133", "chrome146"]
    # Interwal w sekundach rosnacy, zeby wyizolowac soft-ban od stalej blokady
    intervals = [2, 5, 10, 20]

    last_ts = time.monotonic()
    for i, impersonate in enumerate(sequence):
        # interwal przed proba (oprocz pierwszej)
        if i > 0:
            sleep_s = intervals[i - 1]
            print(f"\n  -> czekam {sleep_s}s (izolacja soft-ban / rate-limit)...")
            time.sleep(sleep_s)

        elapsed_since_prev = round(time.monotonic() - last_ts, 1)
        last_ts = time.monotonic()

        print(f"\n=== PROBA {i + 1}: impersonate={impersonate} (od poprzedniej {elapsed_since_prev}s) ===")
        item = _find_fresh_item(s)
        if item is None:
            results["probes"].append({"attempt": i + 1, "impersonate": impersonate,
                                      "error": "brak itemu"})
            print("  ! brak itemu")
            continue
        print(f"  item {item['item_id']} '{item['title']}'")

        txn = _create_txn(s, item, impersonate)
        if txn.get("status") != 200:
            results["probes"].append({"attempt": i + 1, "impersonate": impersonate,
                                      "item_id": item["item_id"], "txn": txn})
            print(f"  ! conversations {txn}")
            continue
        txn_id = txn["transaction_id"]
        print(f"  txn_id={txn_id} (swiezy)")

        b = _build(s, txn_id, item["item_id"], impersonate)
        b["attempt"] = i + 1
        b["impersonate"] = impersonate
        b["item_id"] = item["item_id"]
        b["transaction_id"] = txn_id
        b["elapsed_since_prev_s"] = elapsed_since_prev
        results["probes"].append(b)
        print(f"  BUILD: status={b['status']} datadome='{b['x_datadome']}'")

    out = BASE_DIR / "wynik_probe_build_isolated.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {out}")

    # Podsumowanie
    print("\n=== PODSUMOWANIE ===")
    for p in results["probes"]:
        print(f"  proba {p.get('attempt')}: {p.get('impersonate')} -> status {p.get('status')} "
              f"datadome='{p.get('x_datadome','')}'")


if __name__ == "__main__":
    main()