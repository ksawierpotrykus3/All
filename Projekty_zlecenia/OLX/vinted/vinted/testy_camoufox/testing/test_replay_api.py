# coding: utf-8
"""Test architektury: czy creds zebrane RAZ z przegladarki da sie uzyc przez czyste API.

Faza 1: Camoufox headless -> zaladuj strone przedmiotu, kliknij 'Kup teraz',
        przechwyc pelny request checkout/build (token Incognia, cookies, transaction_id).
Faza 2: odtworz TEN SAM request przez curl_cffi (czyste HTTP, bez przegladarki),
        z identycznymi naglowkami + cookies + payload. Porownaj odpowiedzi.

Jesli faza 2 daje inny wynik niz 'missing incognia'/'401', to znaczy ze token Incognia
+ cookies dzialaja poza przegladarka -> architektura 'zaladuj raz + API' jest mozliwa.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import requests as creq

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_replay_api.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"

CAPTURED_BUILD = {}  # zostanie wypelniony przez on_request


def on_request(req):
    global CAPTURED_BUILD
    if "checkout/build" in req.url:
        CAPTURED_BUILD = {
            "method": req.method,
            "url": req.url,
            "headers": dict(req.headers),
            "post_data": req.post_data,
        }
        print("PRZECHWYCONO checkout/build")


def main() -> None:
    results = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # ---- FAZA 1: przechwycenie realnego requestu ----
    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
    ) as ctx:
        page = ctx.new_page()
        page.on("request", on_request)

        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)

        # OneTrust accept
        try:
            page.evaluate(
                """() => {
                    const btns = document.querySelectorAll('#onetrust-accept-btn-handler, .ot-sdk-container button');
                    for (const b of btns) {
                        if (/accept|akceptuj|zaakceptuj|zgadzam/i.test(b.textContent | '')) { b.click(); return; }
                    }
                }"""
            )
            time.sleep(2)
        except Exception:  # noqa: BLE001
            pass

        # kliknij Kup teraz
        page.evaluate(
            """() => {
                const el = document.querySelector('button[data-testid="item-buy-button"]');
                if (el) { el.click(); return true; }
                return false;
            }"""
        )
        time.sleep(8)

        # pobierz cookies z kontekstu (czyste, dla curl_cffi)
        cookies = ctx.cookies()
        cookie_jar = {c["name"]: c["value"] for c in cookies}
        results["cookies_count"] = len(cookie_jar)

    results["captured"] = CAPTURED_BUILD
    if not CAPTURED_BUILD:
        print("NIE przechwycono checkout/build - nie mozna wykonac fazy 2")
        OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    print("Przechwycone naglowki:", list(CAPTURED_BUILD["headers"].keys()))

    # ---- FAZA 2: replay przez curl_cffi ----
    h = CAPTURED_BUILD["headers"]
    # Zbuduj naglowki dla curl_cffi (pomin cookie z h, uzyjemy cookie_jar)
    replay_headers = {
        "user-agent": h.get("user-agent", ""),
        "accept": h.get("accept", ""),
        "accept-language": h.get("accept-language", ""),
        "content-type": h.get("content-type", "application/json"),
        "x-incognia-request-token": h.get("x-incognia-request-token", ""),
        "x-anon-id": h.get("x-anon-id", ""),
        "locale": h.get("locale", ""),
        "x-csrf-token": h.get("x-csrf-token", ""),
        "priority": h.get("priority", ""),
        "origin": h.get("origin", ""),
        "referer": h.get("referer", ""),
    }
    payload = CAPTURED_BUILD.get("post_data")

    try:
        r = creq.post(
            BUILD_URL,
            headers=replay_headers,
            cookies=cookie_jar,
            data=payload,
            impersonate="chrome",
            timeout=30,
        )
        results["replay"] = {
            "status": r.status_code,
            "body_head": r.text[:800],
            "has_x_datadome": "x-datadome" in r.headers,
        }
        print("\nREPLAY STATUS:", r.status_code)
        print("REPLAY BODY:", r.text[:800])
        print("REPLAY x-datadome:", "x-datadome" in r.headers)
    except Exception as e:  # noqa: BLE001
        results["replay_error"] = repr(e)
        print("REPLAY ERROR:", repr(e))

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")


if __name__ == "__main__":
    main()