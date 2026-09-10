# coding: utf-8
"""Spike A1: Camoufox warmup + harvest WSZYSTKIE cookies + natychmiast curl_cffi checkout.

Kroki:
1) Start Camoufox (warmup ~30s, JS aktywny, DataDome rozwiązany)
2) Otwarcie strony przedmiotu (JS wykonuje cały incognia/fingerprint)
3) Harvest wszystkich cookies z page.context
4) Capture network: nagłówki checkout/build z Camoufox (szukamy x-incognia-request-token)
5) Natychmiast curl_cffi POST checkout/build z harvestowanymi cookies + skopiowanymi nagłówkami
6) Pomiar czasu od harvestu do datadome challenge (TTL cookies)
7) Powtórzenie po 30s/60s/120s dla pomiaru żywotności datadome
"""
import json
import time
import sqlite3
from pathlib import Path

from curl_cffi import requests as creq
from vintedbot.checkout import _get_context, close_context

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"
OUTPUT_TMP = Path(r"C:\Temp\wynik_spike_warmup_harvest.json")


def harvest_cookies_from_sqlite(profil: str) -> dict[str, str]:
    cookies = {}
    db = Path(profil) / "cookies.sqlite"
    if not db.exists():
        return cookies
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value FROM moz_cookies")
        for name, value in cur.fetchall():
            cookies[name] = value
    finally:
        conn.close()
    return cookies


def curl_cffi_checkout(cookies: dict, payload: dict, impersonate: str = "chrome131",
                        extra_headers: dict = None) -> dict:
    headers = {
        "Origin": "https://www.vinted.pl",
        "Referer": ITEM_URL,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        **(extra_headers or {}),
    }
    t0 = time.monotonic()
    try:
        r = creq.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
                       headers=headers, cookies=cookies,
                       impersonate=impersonate, timeout=20, json=payload)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {
            "status": r.status_code,
            "elapsed_ms": elapsed,
            "datadome_in_resp": "datadome" in r.headers,
            "body_preview": r.text[:400] if r.text else "",
            "resp_headers": {k: v[:200] for k, v in r.headers.items() if k.lower() in ("datadome", "x-request-id", "content-type", "location")},
        }
    except Exception as e:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {"status": None, "elapsed_ms": elapsed, "error": repr(e)}


def main():
    result = {"started": time.strftime("%H:%M:%S"), "phases": []}
    payload = {"purchase_items": [{"id": ITEM_ID, "type": "transaction"}]}

    # === FAZA 1: WARMUP CAMOUFOX ===
    t0 = time.monotonic()
    ctx, is_fresh = _get_context(PROFIL, os_name="windows")
    warmup_ms = round((time.monotonic() - t0) * 1000, 1)
    result["phases"].append({"phase": "warmup_camoufox", "ms": warmup_ms, "is_fresh": is_fresh})
    print(f"[1] Warmup: {warmup_ms} ms (fresh={is_fresh})", flush=True)

    page = ctx.new_page()

    # Capture network - nagłówki checkout/build z prawdziwej przeglądarki
    camoufox_build_requests = []
    def on_request(req):
        if "checkout/build" in req.url:
            camoufox_build_requests.append({
                "method": req.method,
                "url": req.url,
                "headers": dict(req.headers),
                "post_data": req.post_data[:500] if req.post_data else "",
            })

    page.on("request", on_request)

    # === FAZA 2: OPEN ITEM PAGE (rozwiązuje DataDome, ładuje Incognia) ===
    t0 = time.monotonic()
    page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
    result["phases"].append({"phase": "goto_item", "ms": round((time.monotonic() - t0) * 1000, 1)})
    print(f"[2] Goto item: {round((time.monotonic()-t0)*1000, 1)} ms", flush=True)

    # Zamknij OneTrust
    try:
        page.evaluate("""() => {
            const btns = document.querySelectorAll('#onetrust-accept-btn-handler, .ot-sdk-container button');
            for (const b of btns) {
                const t = b.textContent ? b.textContent.toLowerCase() : '';
                if (/akcept|zgadzam|accept/.test(t)) { b.click(); return true; }
            }
            return false;
        }""")
    except Exception:
        pass

    page.wait_for_timeout(2000)

    # Sprawdź datadome cookie (kluczowe)
    cookies_before = page.context.cookies()
    datadome_before = next((c for c in cookies_before if c["name"] == "datadome"), None)
    result["phases"].append({
        "phase": "cookies_after_warmup",
        "count": len(cookies_before),
        "datadome": {
            "present": datadome_before is not None,
            "value_len": len(datadome_before["value"]) if datadome_before else 0,
            "domain": datadome_before["domain"] if datadome_before else None,
            "expires": datadome_before.get("expires") if datadome_before else None,
        },
    })
    print(f"[3] Cookies: {len(cookies_before)}, datadome_present={datadome_before is not None}", flush=True)

    # === FAZA 3: HARVEST COOKIES ===
    harvest_t0 = time.time()
    cookies_dict = {c["name"]: c["value"] for c in cookies_before}
    # Dodatkowo: sqlite na dysku (Camoufox może nie mieć ich w page.context jeśli HttpOnly)
    sqlite_cookies = harvest_cookies_from_sqlite(PROFIL)
    result["phases"].append({
        "phase": "harvest",
        "page_context_cookies": len(cookies_dict),
        "sqlite_cookies": len(sqlite_cookies),
        "diff_sqlite_minus_ctx": list(set(sqlite_cookies.keys()) - set(cookies_dict.keys()))[:10],
    })
    print(f"[4] Harvest: page_ctx={len(cookies_dict)}, sqlite={len(sqlite_cookies)}", flush=True)

    # === FAZA 4: CURL_CFFI NATYCHMIAST PO HARVEST ===
    t_harvest = time.monotonic()
    r_immediate = curl_cffi_checkout(cookies_dict, payload)
    result["phases"].append({"phase": "curl_immediate", "result": r_immediate,
                             "since_harvest_ms": round((time.monotonic() - t_harvest) * 1000, 1)})
    print(f"[5] Curl immediate: status={r_immediate['status']} ({r_immediate['elapsed_ms']} ms)", flush=True)

    # Z nagłówkami skopiowanymi z Camoufox (po wywołaniu build przez Camoufoxa)
    # Najpierw wywołaj build z Camoufoxa żeby zebrać nagłówki
    try:
        page.click('button[data-testid="item-buy-button"]', timeout=10000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  camoufox click err: {e!r}", flush=True)

    page.close()

    # Zamknij Camoufox żeby był czysty test curl_cffi (bez concurrent access)
    close_context(PROFIL)

    # === FAZA 5: TTL COOKIES - testy po czasie ===
    print("[6] TTL test...", flush=True)
    ttl_results = []
    for delay_s in [0, 30, 60, 120]:
        if delay_s > 0:
            time.sleep(delay_s - (ttl_results[-1]["actual_delay_s"] if ttl_results else 0))
        actual_delay = round(time.monotonic() - t_harvest, 1)
        r = curl_cffi_checkout(sqlite_cookies, payload)
        r["delay_s"] = delay_s
        r["actual_delay_s"] = actual_delay
        ttl_results.append(r)
        print(f"  +{delay_s}s: status={r['status']}", flush=True)

    result["ttl_test"] = ttl_results
    result["camoufox_build_requests"] = camoufox_build_requests[:3]  # max 3 nagłówki

    result["finished"] = time.strftime("%H:%M:%S")
    OUTPUT_TMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano {OUTPUT_TMP}", flush=True)
    print(f"Datadome po warmup: present={datadome_before is not None}", flush=True)
    print(f"TTL results: {[r['status'] for r in ttl_results]}", flush=True)


if __name__ == "__main__":
    main()
