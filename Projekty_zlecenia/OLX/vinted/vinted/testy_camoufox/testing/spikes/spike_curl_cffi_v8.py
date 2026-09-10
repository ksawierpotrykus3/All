# coding: utf-8
"""Spike 8: ostatnia szansa - dwufazowy flow cart -> checkout i endpointy items/*."""
import json
import sqlite3
import time
from pathlib import Path
from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
OUTPUT_TMP = Path(r"C:\Temp\wynik_spike_curl_cffi_v8.json")


def wczytaj_cookies(profil_dir):
    cookies = {}
    db = Path(profil_dir) / "cookies.sqlite"
    if not db.exists():
        return cookies
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%vinted.pl%'")
        for n, v in cur.fetchall():
            cookies[n] = v
    finally:
        conn.close()
    return cookies


def probe(name, url, method="GET", impersonate="chrome131", cookies=None, data=None, timeout=20):
    headers = {
        "Origin": "https://www.vinted.pl",
        "Referer": f"https://www.vinted.pl/items/{ITEM_ID}",
        "Accept": "application/json, text/plain, */*",
    }
    t0 = time.monotonic()
    try:
        if method == "GET":
            r = creq.get(url, headers=headers, cookies=cookies or {},
                         impersonate=impersonate, timeout=timeout)
        else:
            r = creq.post(url, headers=headers, cookies=cookies or {},
                          impersonate=impersonate, timeout=timeout, json=data)
        return {"name": name, "status": r.status_code, "elapsed_ms": round((time.monotonic()-t0)*1000, 1),
                "body_preview": r.text[:300] if r.text else ""}
    except Exception as e:
        return {"name": name, "error": repr(e)}


def main():
    cookies = wczytaj_cookies(PROFIL)
    csrf = cookies.get("access_token_web", "")[:36]
    result = {"started": time.strftime("%H:%M:%S"), "tests": []}

    # 1) Endpointy items/{id}/...
    for ep in [f"/api/v2/items/{ITEM_ID}/buy",
               f"/api/v2/items/{ITEM_ID}/reserve",
               f"/api/v2/items/{ITEM_ID}/checkout",
               f"/api/v2/items/{ITEM_ID}/buy_now",
               f"/api/v2/items/{ITEM_ID}/order",
               f"/api/v2/items/{ITEM_ID}/offer",
               f"/api/v2/items/{ITEM_ID}/add_to_cart"]:
        for method in ["POST", "GET"]:
            r = probe(f"{method}_{ep}", f"https://www.vinted.pl{ep}", method=method,
                      impersonate="chrome131", cookies=cookies,
                      data={"id": ITEM_ID, "type": "transaction"} if method == "POST" else None)
            result["tests"].append(r)

    # 2) Cart endpoints
    for ep in ["/api/v2/cart",
               "/api/v2/cart/items",
               "/api/v2/cart/checkout",
               "/api/v2/cart/checkout/build",
               "/api/v2/cart/purchase"]:
        r = probe(f"cart_{ep}", f"https://www.vinted.pl{ep}", method="POST",
                  impersonate="chrome131", cookies=cookies,
                  data={"item_id": ITEM_ID, "type": "transaction"})
        result["tests"].append(r)

    # 3) Dwufazowy flow: POST /cart + POST /purchases/checkout/build
    r1 = probe("flow_step1_cart", "https://www.vinted.pl/api/v2/cart/items", method="POST",
               impersonate="chrome131", cookies=cookies,
               data={"item_id": ITEM_ID, "quantity": 1})
    result["tests"].append(r1)
    r2 = probe("flow_step2_build", "https://www.vinted.pl/api/v2/purchases/checkout/build",
               method="POST", impersonate="chrome131", cookies=cookies,
               data={"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]})
    result["tests"].append(r2)

    # 4) Sprawdź GET /api/v2/items/{id} z item_id jako transaction_id (nie item_id)
    r = probe("items_get_short", f"https://www.vinted.pl/api/v2/items/{ITEM_ID}?fields[]=transaction",
              impersonate="chrome131", cookies=cookies)
    result["tests"].append(r)

    # 5) Bez cookies (sprawdzenie czy DataDome puszcza anonimowo)
    r = probe("anon_checkout", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="POST", impersonate="chrome131", cookies={},
              data={"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]})
    result["tests"].append(r)

    result["summary"] = {
        "total": len(result["tests"]),
        "captcha_403": sum(1 for r in result["tests"] if r.get("status") == 403),
        "not_found_404": sum(1 for r in result["tests"] if r.get("status") == 404),
        "passed_200": sum(1 for r in result["tests"] if r.get("status") == 200),
        "errors": sum(1 for r in result["tests"] if "error" in r),
    }
    result["finished"] = time.strftime("%H:%M:%S")
    OUTPUT_TMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2), flush=True)
    print(f"Zapisano {OUTPUT_TMP}", flush=True)


if __name__ == "__main__":
    main()
