# coding: utf-8
"""Spike: 6 strategii curl_cffi dla checkout/build.

Wniosek z 12.8: czysty curl_cffi → 403 captcha. Teraz sprawdzam czy którakolwiek
z modyfikacji odblokuje DataDome dla checkout/build:

STRATEGIA 1: chrome131 + cookies Firefox (baseline powtórzonyy)
STRATEGIA 2: dodanie Sec-Fetch-* + Accept-Encoding (jak realna przeglądarka)
STRATEGIA 3: nagłówek x-incognia-request-token z placeholderem JWE
STRATEGIA 4: inny endpoint: /api/v2/transactions/{id}/offers (nie build)
STRATEGIA 5: POST z nagłówkiem x-requested-with: XMLHttpRequest
STRATEGIA 6: hybryda - najpierw Camoufox otwiera item (daje datadome cookie świeży),
             potem curl_cffi checkout z tym cookies

Kryterium sukcesu: status 200 (NIE 403 captcha) z purchase_id w body.
Spike zawsze bezpieczny - tylko własny przedmiot testowy, zatrzymuje się na rezerwacji.
"""
import json
import sqlite3
import time
from pathlib import Path

from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
OUTPUT_TMP = Path(r"C:\Temp\wynik_spike_curl_cffi_strategie.json")

BASE = {
    "Origin": "https://www.vinted.pl",
    "Referer": f"https://www.vinted.pl/items/{ITEM_ID}",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


def wczytaj_cookies(profil_dir: str) -> dict:
    cookies = {}
    db = Path(profil_dir) / "cookies.sqlite"
    if not db.exists():
        return cookies
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%vinted.pl%'")
        for name, value in cur.fetchall():
            cookies[name] = value
    finally:
        conn.close()
    return cookies


def probe(name, url, method="GET", impersonate="chrome131", cookies=None,
          headers=None, data=None, timeout=20):
    full_headers = {**BASE, **(headers or {})}
    t0 = time.monotonic()
    try:
        if method == "GET":
            r = creq.get(url, headers=full_headers, cookies=cookies or {},
                         impersonate=impersonate, timeout=timeout)
        else:
            r = creq.post(url, headers=full_headers, cookies=cookies or {},
                          impersonate=impersonate, timeout=timeout, json=data)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        body_preview = r.text[:500] if r.text else ""
        datadome_present = "datadome" in r.headers
        return {
            "name": name, "status": r.status_code, "elapsed_ms": elapsed,
            "datadome_cookie": datadome_present,
            "body_preview": body_preview, "error": None,
        }
    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {"name": name, "status": None, "elapsed_ms": elapsed, "error": repr(e)}


def main():
    cookies = wczytaj_cookies(PROFIL)
    csrf = cookies.get("access_token_web", "")[:36]
    payload = {"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]}
    results = {"started": time.strftime("%H:%M:%S"), "cookies_count": len(cookies), "strategie": []}

    # S1: baseline (chrome131 + cookies)
    r = probe("S1_baseline_chrome131", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="POST", impersonate="chrome131", cookies=cookies, data=payload)
    results["strategie"].append(r)

    # S2: dodanie Sec-Fetch-* + Accept-Encoding
    s2_headers = {
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    r = probe("S2_sec_fetch_chrome131", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="POST", impersonate="chrome131", cookies=cookies,
              headers=s2_headers, data=payload)
    results["strategie"].append(r)

    # S3: placeholder Incognia JWE (curl_cffi NIE MA SDK, ale może serwer to opcjonalnie sprawdza)
    s3_headers = {
        "x-incognia-request-token": "eyJhbGciOiJSU0EtT0FFUC0yNTYiLCJlbmMiOiJBMjU2R0NNIn0.placeholder.placeholder",
    }
    r = probe("S3_placeholder_incognia", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="POST", impersonate="chrome131", cookies=cookies,
              headers=s3_headers, data=payload)
    results["strategie"].append(r)

    # S4: alternatywny endpoint (mniej prawdopodobne, ale sprawdźmy)
    for alt_ep in [
        f"/api/v2/items/{ITEM_ID}/transaction/checkout/build",
        f"/api/v2/transactions/{ITEM_ID}/checkout/build",
        f"/api/v2/items/{ITEM_ID}/purchase",
        f"/api/v2/checkout/build",
        f"/api/v2/cart/items/{ITEM_ID}/checkout",
    ]:
        r = probe(f"S4_{alt_ep}", f"https://www.vinted.pl{alt_ep}",
                  method="POST", impersonate="chrome131", cookies=cookies, data=payload)
        results["strategie"].append(r)

    # S5: XMLHttpRequest header (stare API często go wymaga)
    s5_headers = {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-Token": csrf,
    }
    r = probe("S5_xmlhttprequest", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="POST", impersonate="chrome131", cookies=cookies,
              headers=s5_headers, data=payload)
    results["strategie"].append(r)

    # S6: pełna replikacja sesji Camoufox (wszystkie cookies + csrf + sekcje)
    s6_headers = {
        **s2_headers,
        "x-incognia-request-token": "placeholder",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-Token": csrf,
    }
    r = probe("S6_full_replica", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="POST", impersonate="chrome131", cookies=cookies,
              headers=s6_headers, data=payload)
    results["strategie"].append(r)

    # Analiza - które strategie uniknęły 403
    results["summary"] = {
        "total_strategies": len(results["strategie"]),
        "passed_200": sum(1 for r in results["strategie"] if r["status"] == 200),
        "captcha_403": sum(1 for r in results["strategie"] if r["status"] == 403),
        "other_status": sum(1 for r in results["strategie"] if r["status"] not in (200, 403)),
    }
    results["finished"] = time.strftime("%H:%M:%S")
    OUTPUT_TMP.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TMP.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results["summary"], ensure_ascii=False, indent=2), flush=True)
    print("Zapisano " + str(OUTPUT_TMP), flush=True)
    print("Statusy: " + ", ".join(
        f"{r['name']}={r['status']}" for r in results["strategie"]), flush=True)


if __name__ == "__main__":
    main()
