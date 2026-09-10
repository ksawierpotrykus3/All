# coding: utf-8
"""Spike 7: curl_cffi z cookie datadome z vinted.fr (subdomena domeny nadrzędnej).

Obserwacja z poprzedniego spike'a: datadome_cookie=false mimo że cookie istnieje
w profilu Firefox — domena cookie to .vinted.fr, żądanie idzie do .vinted.pl.

Test:
1) Jakie domeny mają cookies datadome/access_token_web/anon_id w profilu Firefox?
2) Czy dodanie cookies z .vinted.fr do żądania do .vinted.pl coś zmienia?
3) Czy istnieje endpoint "purchase" między katalogiem a checkout?
4) Czy endpoint /api/v2/purchases/{id} GET pozwala na podgląd istniejącej rezerwacji?
"""
import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
OUTPUT_TMP = Path(r"C:\Temp\wynik_spike_curl_cffi_v7.json")


def inspect_cookies(profil_dir: str) -> dict:
    """Zwraca mapę: cookie_name -> lista domen."""
    db = Path(profil_dir) / "cookies.sqlite"
    cookies = {}
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value, host FROM moz_cookies")
        for name, value, host in cur.fetchall():
            cookies.setdefault(name, []).append({"host": host, "value_len": len(value)})
    finally:
        conn.close()
    return cookies


def wczytaj_cookies_domena(profil_dir: str, domena_fragment: str) -> dict:
    cookies = {}
    db = Path(profil_dir) / "cookies.sqlite"
    if not db.exists():
        return cookies
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE ?",
                          (f"%{domena_fragment}%",))
        for name, value in cur.fetchall():
            cookies[name] = value
    finally:
        conn.close()
    return cookies


def probe(name, url, method="GET", impersonate="chrome131", cookies=None,
          headers=None, data=None, timeout=20):
    full_headers = {
        "Origin": "https://www.vinted.pl",
        "Referer": f"https://www.vinted.pl/items/{ITEM_ID}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        **(headers or {}),
    }
    t0 = time.monotonic()
    try:
        if method == "GET":
            r = creq.get(url, headers=full_headers, cookies=cookies or {},
                         impersonate=impersonate, timeout=timeout)
        else:
            r = creq.post(url, headers=full_headers, cookies=cookies or {},
                          impersonate=impersonate, timeout=timeout, json=data)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {
            "name": name, "status": r.status_code, "elapsed_ms": elapsed,
            "body_preview": r.text[:400] if r.text else "",
        }
    except Exception as e:
        return {"name": name, "status": None, "error": repr(e)}


def main():
    result = {"started": time.strftime("%H:%M:%S")}

    # 1) Inspekcja domen cookies
    result["cookies_inspect"] = inspect_cookies(PROFIL)

    # 2) Cookies z różnych domen vinted
    cookies_pl = wczytaj_cookies_domena(PROFIL, "vinted.pl")
    cookies_fr = wczytaj_cookies_domena(PROFIL, "vinted.fr")
    cookies_all_vinted = wczytaj_cookies_domena(PROFIL, "vinted")
    result["cookies_count"] = {
        "vinted.pl": len(cookies_pl),
        "vinted.fr": len(cookies_fr),
        "any_vinted": len(cookies_all_vinted),
    }

    # 3) Checkout z cookies fr (subdomena - może curl_cffi to akceptuje)
    payload = {"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]}
    csrf = (cookies_fr.get("access_token_web") or cookies_pl.get("access_token_web", ""))[:36]
    s3_headers = {"X-CSRF-Token": csrf} if csrf else {}

    result["checkout_attempts"] = []
    for variant_name, cookies_use in [
        ("vinted_pl_only", cookies_pl),
        ("vinted_fr_only", cookies_fr),
        ("vinted_all", cookies_all_vinted),
    ]:
        r = probe(f"checkout_{variant_name}",
                  "https://www.vinted.pl/api/v2/purchases/checkout/build",
                  method="POST", impersonate="chrome131",
                  cookies=cookies_use, headers=s3_headers, data=payload)
        result["checkout_attempts"].append(r)

    # 4) Sprawdzenie endpointu purchase (preview)
    result["purchase_endpoint_tests"] = []
    for ep in [
        f"/api/v2/purchases?transaction_id={ITEM_ID}",
        f"/api/v2/users/3180346878/purchases",
        f"/api/v2/items/{ITEM_ID}/transactions",
        f"/api/v2/items/{ITEM_ID}/purchase_status",
    ]:
        r = probe(f"purchase_{ep}", f"https://www.vinted.pl{ep}",
                  impersonate="chrome131", cookies=cookies_all_vinted)
        result["purchase_endpoint_tests"].append(r)

    # 5) Bezpośredni endpoint /purchases/eWjYk_Oxxq3qOpWC4gee4 (znany purchase_id)
    r = probe("purchase_by_id",
              "https://www.vinted.pl/api/v2/purchases/eWjYk_Oxxq3qOpWC4gee4",
              impersonate="chrome131", cookies=cookies_all_vinted)
    result["purchase_by_id"] = r

    # 6) Endpoint /api/v2/catalog/items/{id} (pełne detale, inny niż items/{id})
    r = probe("catalog_item_by_id",
              f"https://www.vinted.pl/api/v2/catalog/items/{ITEM_ID}",
              impersonate="chrome131", cookies=cookies_all_vinted)
    result["catalog_item"] = r

    result["finished"] = time.strftime("%H:%M:%S")
    OUTPUT_TMP.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "cookies_pl": len(cookies_pl),
        "cookies_fr": len(cookies_fr),
        "cookies_all": len(cookies_all_vinted),
        "checkout_statuses": [r["status"] for r in result["checkout_attempts"]],
        "purchase_id_status": result["purchase_by_id"]["status"],
        "catalog_item_status": result["catalog_item"]["status"],
        "purchase_endpoints": [r["status"] for r in result["purchase_endpoint_tests"]],
    }, ensure_ascii=False, indent=2), flush=True)
    print(f"Zapisano {OUTPUT_TMP}", flush=True)


if __name__ == "__main__":
    main()
