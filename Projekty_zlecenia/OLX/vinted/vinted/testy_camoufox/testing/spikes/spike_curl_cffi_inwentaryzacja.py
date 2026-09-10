# coding: utf-8
"""Spike: pełna inwentaryzacja endpointów Vinted przez curl_cffi.

Testuje 5 aspektów:
A) impersonate="chrome131" + minimum nagłówków — czy DataDome puszcza?
B) impersonate="chrome131" + komplet nagłówków z sesji Camoufox — czy przejdzie checkout/build?
C) Endpointy do inwentaryzacji: users/current, items/{id}, catalog/items, purchases/checkout/build
D) Rate-limit 429 dla różnych impersonate
E) Wariant hybrydowy: detection (curl_cffi) + checkout (Camoufox) — porównanie czasów

Spike ZAWSZE bezpieczny — kupuje tylko na własnym przedmiocie testowym,
kończy się na rezerwacji, nie płaci.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
COOKIES_PATH = Path(PROFIL) / "cookies.sqlite"
ITEM_ID = 9807925466
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"
OUTPUT = Path(__file__).resolve().parent.parent / "vinted" / "testy_camoufox" / "wynik_spike_curl_cffi.json"

# Nagłówki z żywej sesji (odczytane z Camoufox)
# Te klucze API są niezmienne dla konta zalogowanego
BASE_HEADERS = {
    "Origin": "https://www.vinted.pl",
    "Referer": "https://www.vinted.pl/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


def _wczytaj_cookies_firefox(profil_dir: str) -> dict[str, str]:
    """Czyta cookies z Firefox sqlite (moz_cookies). Bez zależności zewnętrznych."""
    import sqlite3
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


def _probe(name: str, url: str, method: str = "GET", headers=None, cookies=None,
           impersonate: str = "chrome131", data=None, timeout: int = 15):
    """Wykonuje pojedynczy request i mierzy czas + status + nagłówki odpowiedzi."""
    headers_full = {**BASE_HEADERS, **(headers or {})}
    t0 = time.monotonic()
    try:
        if method == "GET":
            r = creq.get(url, headers=headers_full, cookies=cookies or {}, impersonate=impersonate, timeout=timeout)
        else:
            r = creq.post(url, headers=headers_full, cookies=cookies or {}, impersonate=impersonate, timeout=timeout, json=data)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        # Zbierz istotne nagłówki odpowiedzi
        out_headers = {}
        for h in ("datadome", "x-vinted-locale", "x-request-id", "set-cookie", "content-type", "location"):
            v = r.headers.get(h)
            if v:
                out_headers[h] = v[:200]
        # Pierwsze 200 znaków body
        body_preview = r.text[:300] if r.text else ""
        return {
            "name": name,
            "url": url,
            "method": method,
            "impersonate": impersonate,
            "status": r.status_code,
            "elapsed_ms": elapsed,
            "resp_headers": out_headers,
            "body_preview": body_preview,
            "error": None,
        }
    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {"name": name, "status": None, "elapsed_ms": elapsed, "error": repr(e)}


def main():
    result = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "probes": []}

    # --- Przygotowanie cookies z profilu Firefox (jeśli istnieją) ---
    cookies = _wczytaj_cookies_firefox(PROFIL)
    result["cookies_loaded"] = len(cookies)
    result["cookie_names"] = sorted(cookies.keys())[:20] if cookies else []

    # ===========================================================
    # ASPEKT A: impersonate="chrome131" minimum — DataDome challenge?
    # ===========================================================
    for imp in ["chrome131", "chrome124", "chrome120", "safari17_0", "firefox133"]:
        r = _probe(f"A_{imp}_anon_users_current",
                   "https://www.vinted.pl/api/v2/users/current",
                   impersonate=imp)
        result["probes"].append(r)

    # ===========================================================
    # ASPEKT C: Inwentaryzacja endpointów (z cookies jeśli dostępne)
    # ===========================================================
    if cookies:
        # Endpoint 1: GET users/current (sesja)
        result["probes"].append(_probe(
            "C1_users_current", "https://www.vinted.pl/api/v2/users/current",
            impersonate="chrome131", cookies=cookies))
        # Endpoint 2: GET items/{id} (detale)
        result["probes"].append(_probe(
            "C2_item_details", f"https://www.vinted.pl/api/v2/items/{ITEM_ID}",
            impersonate="chrome131", cookies=cookies))
        # Endpoint 3: GET catalog/items (detection — to już działa)
        result["probes"].append(_probe(
            "C3_catalog", "https://www.vinted.pl/api/v2/catalog/items?per_page=5",
            impersonate="chrome131", cookies=cookies))
    else:
        result["note"] = "Brak cookies w profilu — pominięto endpointy wymagające sesji"

    # ===========================================================
    # ASPEKT D: Rate-limit test (10 szybkich requestów na catalog)
    # ===========================================================
    rl_results = []
    for i in range(8):
        r = _probe(f"D_rl_{i}", "https://www.vinted.pl/api/v2/catalog/items?per_page=1",
                   impersonate="chrome131", cookies=cookies)
        rl_results.append({"i": i, "status": r["status"], "ms": r["elapsed_ms"]})
        if r["status"] == 429:
            break
        time.sleep(0.3)
    result["rate_limit_test"] = rl_results

    # ===========================================================
    # ASPEKT B: checkout/build przez curl_cffi (kluczowe pytanie)
    # ===========================================================
    if cookies:
        csrf = cookies.get("access_token_web", "")[:36]  # zwykle token = UUID
        for body_style in ["transaction_only", "with_session"]:
            if body_style == "transaction_only":
                payload = {"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]}
            else:
                payload = {
                    "purchase_items": [{"id": ITEM_ID, "type": "transaction"}],
                    "shipping_country_code": "PL",
                    "locale": "pl-PL",
                }
            r = _probe(
                f"B_checkout_build_{body_style}",
                "https://www.vinted.pl/api/v2/purchases/checkout/build",
                method="POST",
                impersonate="chrome131",
                cookies=cookies,
                headers={"X-CSRF-Token": csrf} if csrf else None,
                data=payload,
            )
            result["probes"].append(r)

    # ===========================================================
    # ASPEKT E: porównanie czasów detection curl_cffi vs Camoufox (heurystyka)
    # ===========================================================
    # curl_cffi powinno być znacząco szybsze — mierzymy 5 requestów
    e_times = []
    for i in range(5):
        r = _probe(f"E_curl_{i}", "https://www.vinted.pl/api/v2/catalog/items?per_page=1",
                   impersonate="chrome131", cookies=cookies)
        e_times.append(r["elapsed_ms"])
    result["detection_curl_cffi_times_ms"] = e_times
    result["detection_camoufox_baseline_ms"] = 719  # z dokumentacji (p50)

    # ===========================================================
    # ZAPIS
    # ===========================================================
    result["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Zapisano: {OUTPUT}", flush=True)
    except Exception as e:
        # Fallback — zapisz do TMP (np. C:\Temp) i wypisz na stdout
        try:
            Path("C:/Temp/wynik_spike_curl_cffi.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Fallback zapis: C:/Temp/wynik_spike_curl_cffi.json", flush=True)
        except Exception:
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print(f"Cookies: {len(cookies)}", flush=True)
    print(f"Probes: {len(result['probes'])}", flush=True)
    print(json.dumps({
        "impersonate_pass": sum(1 for r in result["probes"] if r.get("status") == 200),
        "rate_limit_429": sum(1 for r in rl_results if r["status"] == 429),
        "checkout_build_status": next((r.get("status") for r in result["probes"] if r["name"].startswith("B_checkout_build_transaction")), None),
        "detection_avg_ms": round(sum(e_times) / len(e_times), 1) if e_times else None,
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
