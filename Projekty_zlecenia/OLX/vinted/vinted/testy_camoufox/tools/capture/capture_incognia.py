# coding: utf-8
"""Przechwycenie pelnych naglowkow Incognia z realnego checkout/build (headless, bez platnosci).

Metoda: wejscie na strone wlasnego przedmiotu testowego, nasluchiwanie na requesty,
klikniecie "Kup teraz" (uruchamia checkout/build z naglowkami Incognia z SDK),
przechwycenie pelnego naglowka requestu. BEZ finalizacji platnosci.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
OUTPUT = BASE_DIR / "wynik_incognia_capture.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"
CAPTURED = []


def on_request(req):
    u = req.url
    if "checkout/build" in u or "purchases/checkout" in u:
        CAPTURED.append({
            "url": u,
            "method": req.method,
            "headers": dict(req.headers),
            "post_data": req.post_data,
        })
        print("PRZECHWYCONO checkout/build!")


def main() -> None:
    results = {"steps": [], "captured": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

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

        # KROK 1: wejscie na strone przedmiotu
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)
        results["steps"].append({"step": "item_page", "title": page.title(), "url": page.url})
        print("ITEM PAGE:", page.title())

        # KROK 2: wypisz wszystkie przyciski i linki z tekstem (do debugu)
        try:
            buttons = page.evaluate(
                """() => {
                    const out = [];
                    const els = document.querySelectorAll('button, a');
                    for (const el of els) {
                        const txt = (el.textContent || '').trim();
                        if (txt && txt.length < 40 && /kup|buy/.test(txt.toLowerCase())) {
                            out.push({tag: el.tagName, text: txt, testid: el.getAttribute('data-testid')});
                        }
                    }
                    return out.slice(0, 20);
                }"""
            )
            results["steps"].append({"step": "buy_buttons", "data": buttons})
            print("BUTTONS:", json.dumps(buttons, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "buy_buttons", "error": repr(e)})
            print("BUTTONS ERROR:", repr(e))

        # KROK 3: proba klikniecia "Kup teraz" przez selectory
        clicked = False
        for sel in [
            "button[data-testid*='buy']",
            "button:has-text('Kup teraz')",
            "text=Kup teraz",
            "button:has-text('Kup')",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=5000)
                    clicked = True
                    print("KLIKNIETO:", sel)
                    break
            except Exception:
                continue

        if not clicked:
            print("Selectory nie trafily. Proboje przez evaluate...")
            try:
                clicked = page.evaluate(
                    """() => {
                        const els = document.querySelectorAll('button, a');
                        for (const el of els) {
                            const txt = (el.textContent || '').trim().toLowerCase();
                            if (txt.indexOf('kup teraz') !== -1 || txt.indexOf('buy now') !== -1) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }"""
                )
            except Exception as e:  # noqa: BLE001
                print("EVALUATE CLICK ERROR:", repr(e))

        time.sleep(7)  # czas na wyslanie checkout/build
        results["steps"].append({"step": "click_done", "clicked": clicked})

    results["captured"] = CAPTURED
    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")
    print(f"Przechwycono requestow checkout/build: {len(CAPTURED)}")


if __name__ == "__main__":
    main()