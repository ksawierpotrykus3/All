# coding: utf-8
"""Szuka zrodla transaction_id (21867789545) w stronie przedmiotu.

Metoda:
1. pobranie pelnego HTML (SSR + flight data)
2. szukanie doslownego id i slowa 'transaction' w HTML
3. szukanie w window.__NEXT_DATA__ / globalnym stanie JS
4. dump kontekstow wokol item id 9806080522
"""
import json
import re
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_transaction_source.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"
ITEM_ID = "9806080522"
TARGET_ID = "21867789545"


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
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)

        html = page.content()
        results["html_len"] = len(html)

        # 1. literalne wystapienie target id
        results["target_in_html"] = TARGET_ID in html
        results["item_id_in_html"] = ITEM_ID in html

        # 2. kontekst wokol item id
        hits_item = [m.start() for m in re.finditer(ITEM_ID, html)]
        results["item_id_occurrences"] = len(hits_item)
        contexts = []
        for i in hits_item[:10]:
            contexts.append(html[max(0, i - 150):i + 200])
        results["item_id_contexts"] = contexts

        # 3. szukaj slowa 'transaction' w HTML
        tx_hits = [m.start() for m in re.finditer(r"transaction", html, re.IGNORECASE)]
        results["transaction_occurrences"] = len(tx_hits)
        tx_contexts = []
        for i in tx_hits[:15]:
            tx_contexts.append(html[max(0, i - 120):i + 200])
        results["transaction_contexts"] = tx_contexts

        # 4. szukaj w window.__NEXT_DATA__ i globalnym stanie
        try:
            js_state = page.evaluate(
                """() => {
                    const out = {};
                    const nd = window.__NEXT_DATA__;
                    if (nd) {
                        out.next_data_keys = Object.keys(nd.props?.pageProps | {});
                        // szukaj transaction/purchase w pageProps
                        const s = JSON.stringify(nd.props?.pageProps | {});
                        out.pageProps_has_transaction = s.toLowerCase().includes('transaction');
                        out.pageProps_has_target = s.includes('21867789545');
                    }
                    // globalne klucze zawierajace 'item' lub 'product'
                    out.global_keys = Object.keys(window).filter(k => /item|product|purchase|transaction/i.test(k)).slice(0, 30);
                    return out;
                }"""
            )
            results["js_state"] = js_state
            print("JS STATE:", json.dumps(js_state, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            results["js_state_error"] = repr(e)

        # 5. flight data - szukaj w __next_f
        try:
            flight = page.evaluate(
                """() => {
                    const out = [];
                    if (window.__next_f) {
                        for (const ch of window.__next_f) out.push(JSON.stringify(ch).slice(0, 500));
                    }
                    return out;
                }"""
            )
            joined = " ".join(flight)
            results["flight_has_target"] = TARGET_ID in joined
            results["flight_len"] = len(joined)
            if TARGET_ID in joined:
                i = joined.find(TARGET_ID)
                results["flight_context"] = joined[max(0, i - 200):i + 300]
        except Exception as e:  # noqa: BLE001
            results["flight_error"] = repr(e)

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")


if __name__ == "__main__":
    main()