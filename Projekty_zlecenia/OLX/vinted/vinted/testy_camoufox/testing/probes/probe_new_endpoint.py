# coding: utf-8
"""Diagnostyka NOWEGO endpointu /messaging/main/inquiries vs starego /conversations.

Bez checkout/build/payment — tylko tworzenie konwersacji (bezpieczne, bez ryzyka
soft-banu transakcyjnego). Mierzy czas i porównuje odpowiedzi obu backendow.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMP = "chrome136"
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}


def _session():
    s = cr.Session(impersonate=IMP)
    for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
    })
    return s


def find_item(s):
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")
    r = s.get(url, headers=H, impersonate=IMP, timeout=30)
    for it in r.json().get("items", []):
        u = it.get("user", {})
        if not u or it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        return it["id"], it["user"]["id"]
    return None, None


def main():
    s = _session()
    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=H, impersonate=IMP, timeout=30)
    print("health:", r.status_code)
    if r.status_code != 200:
        print(r.text[:200])
        return

    item_id, seller_id = find_item(s)
    print(f"item={item_id} seller={seller_id}")
    if not item_id:
        print("BRAK itemu")
        return

    # --- 1) NOWY backend: /messaging/main/inquiries (api.vinted.pl) ---
    t0 = time.monotonic()
    try:
        r = s.post("https://api.vinted.pl/messaging/main/inquiries",
                   json={"item_ids": [str(item_id)], "receiver_id": str(seller_id)},
                   headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
        dt_ms = (time.monotonic() - t0) * 1000
        body = r.text[:600]
        print(f"\n[NOWY /messaging/main/inquiries] http={r.status_code} | {dt_ms:.0f} ms")
        print("BODY:", body)
    except Exception as e:
        print(f"\n[NOWY] blad: {e}")

    # --- 2) STARY backend: /conversations (www.vinted.pl) ---
    t0 = time.monotonic()
    try:
        r = s.post("https://www.vinted.pl/api/v2/conversations",
                   json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
                   headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
        dt_ms = (time.monotonic() - t0) * 1000
        print(f"\n[STARY /conversations] http={r.status_code} | {dt_ms:.0f} ms")
        print("BODY:", r.text[:600])
    except Exception as e:
        print(f"\n[STARY] blad: {e}")


if __name__ == "__main__":
    main()