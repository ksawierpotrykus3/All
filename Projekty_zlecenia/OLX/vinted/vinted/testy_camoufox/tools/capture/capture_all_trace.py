# coding: utf-8
"""Rozszerzone badania: przechwycenie WSZYSTKICH requestow + odpowiedzi przy kliknieciu 'Kup teraz'.

Cel: znalezc zrodlo transaction_id 21867789545 (skad go bierze frontend).

Metoda:
- nasluch na request i response (pelne URL, post_data, status)
- szuka liczby 21867789545 w body odpowiedzi i w HTML strony
"""
import json
import re
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
OUTPUT = BASE_DIR / "wynik_all_trace.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"
TARGET_ID = "21867789545"

REQUESTS = []
RESPONSES = []


def on_request(req):
    REQUESTS.append({
        "method": req.method,
        "url": req.url,
        "post_data": req.post_data,
    })


def on_response(resp):
    try:
        body = resp.text()
    except Exception:  # noqa: BLE001
        body = ""
    entry = {
        "status": resp.status,
        "url": resp.url,
        "body_head": body[:300],
    }
    if TARGET_ID in body:
        entry["contains_target"] = True
    RESPONSES.append(entry)
    if TARGET_ID in body:
        print(f"[RESPONSE z target id] {resp.status} {resp.url}")


def main() -> None:
    results = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

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
        page.on("response", on_response)

        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)

        # przeszukaj SSR HTML pod katem target id
        html = page.content()
        results["html_contains_target"] = TARGET_ID in html
        results["html_len"] = len(html)
        if TARGET_ID in html:
            i = html.find(TARGET_ID)
            results["html_context"] = html[max(0, i - 200):i + 300]

        # zamknij OneTrust
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

        # kliknij "Kup teraz"
        clicked = page.evaluate(
            """() => {
                const el = document.querySelector('button[data-testid="item-buy-button"]');
                if (el) { el.click(); return true; }
                return false;
            }"""
        )
        results["clicked"] = clicked
        print("KLIKNIETO:", clicked)

        time.sleep(12)

    results["requests"] = REQUESTS
    results["responses"] = RESPONSES
    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")
    print(f"Requests: {len(REQUESTS)}, Responses: {len(RESPONSES)}")

    # podsumowanie: gdzie pojawilo sie target id
    hits = [r for r in RESPONSES if r.get("contains_target")]
    print(f"Odpowiedzi zawierajace {TARGET_ID}: {len(hits)}")


if __name__ == "__main__":
    main()