# coding: utf-8
"""Faza 1+3: Headed Camoufox, weryfikacja Inccognia i pomiar realnego czasu rezerwacji.

Test na własnym przedmiocie 9807925466. Mierzy:
1. Czy SDK Incognia sie inicjalizuje w headed mode
2. Realny czas rezerwacji end-to-end (goto -> click -> purchase_id)

Bezpieczenstwo:
- wlasny przedmiot testowy
- BEZ platnosci (tylko rezerwacja)
- headed mode (headless=False) — wymaga GUI
"""

import json
import time
from pathlib import Path
from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_headed_incognia_speed.json"

ITEM_ID = 9807925466  # genesis krypton 700 (wlasny przedmiot)
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"


def measure_incognia_and_reserve():
    results = {"steps": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    t0_global = time.monotonic()

    with Camoufox(
        persistent_context=True,
        headless=False,  # HEADED - wymaga GUI
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
    ) as ctx:
        page = ctx.new_page()

        # KROK 1: goto strona przedmiotu + pomiar czasu
        t_nav_start = time.monotonic()

        captured = {}
        def on_response(resp):
            if "/checkout?" in resp.url and "purchase_id=" in resp.url:
                captured["url"] = resp.url
                captured["time_from_click"] = time.monotonic()

        page.on("response", on_response)

        page.goto(ITEM_URL, wait_until="commit", timeout=90000)
        t_nav_end = time.monotonic()

        results["steps"].append({
            "step": "goto_item",
            "duration_ms": round((t_nav_end - t_nav_start) * 1000, 1)
        })

        # KROK 2: czekaj na przycisk "Kup teraz"
        try:
            page.wait_for_selector('button[data-testid="item-buy-button"]', timeout=15000)
            t_button_ready = time.monotonic()
            results["steps"].append({
                "step": "button_ready",
                "duration_ms": round((t_button_ready - t_nav_end) * 1000, 1)
            })
        except Exception as e:
            results["steps"].append({"step": "button_ready", "error": repr(e)})

        # KROK 3: sprawdź Incognia
        incognia_check = page.evaluate("""() => {
            const keys = [];
            for (const k in window) if (/incognia/i.test(k)) keys.push(k);
            return {
                incognia_keys: keys,
                has_Incognia: typeof window.Incognia !== 'undefined',
                webgl_available: !!window.WebGLRenderingContext,
                userAgent: navigator.userAgent
            };
        }""")
        results["incognia_check"] = incognia_check
        print(f"INCOGNIA CHECK: {json.dumps(incognia_check, indent=2)}")

        # KROK 4: zamknij OneTrust
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

        # KROK 5: klik i pomiar
        t_click_start = time.monotonic()

        page.evaluate("""() => {
            const el = document.querySelector('button[data-testid="item-buy-button"]');
            if (el) { el.click(); return true; }
            return false;
        }""")

        # czekaj na redirect z purchase_id
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and "url" not in captured:
            time.sleep(0.1)

        t_click_end = time.monotonic()

        if "url" in captured:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(captured["url"]).query)
            results["steps"].append({
                "step": "reservation_success",
                "purchase_id": q.get("purchase_id", [""])[0],
                "order_id": q.get("order_id", [""])[0],
                "click_to_purchase_ms": round((captured["time_from_click"] - t_click_start) * 1000, 1),
                "total_time_ms": round((t_click_end - t0_global) * 1000, 1),
                "url": captured["url"]
            })
            print(f"SUCCESS: purchase_id={q.get('purchase_id', [''])[0]} in {captured['time_from_click']-t_click_start:.2f}s")
        else:
            results["steps"].append({
                "step": "reservation_timeout",
                "duration_ms": round((t_click_end - t_click_start) * 1000, 1)
            })
            print("TIMEOUT — no purchase_id in 30s")

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano: {OUTPUT}")
    return results


if __name__ == "__main__":
    measure_incognia_and_reserve()
