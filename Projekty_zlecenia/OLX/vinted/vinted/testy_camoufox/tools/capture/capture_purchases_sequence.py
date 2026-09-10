# coding: utf-8
"""Przechwycenie PEŁNEJ sekwencji requestow /purchases przy kliknieciu 'Kup teraz'.

Naprawia blokade OneTrust: klika przez JS (click()) z pominieciem nakładki zgód.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
OUTPUT = BASE_DIR / "wynik_purchases_sekwencja.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"
CAPTURED = []


def on_request(req):
    u = req.url
    if "/purchases" in u or "checkout" in u or "/transactions" in u:
        CAPTURED.append({
            "method": req.method,
            "url": u,
            "post_data": req.post_data,
        })
        print(f"[{req.method}] {u}" + (f"  DATA={req.post_data}" if req.post_data else ""))


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

        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)
        print("ITEM PAGE LOADED")

        # zamknij/zatwierdz OneTrust nakładkę, jesli jest
        try:
            page.evaluate(
                """() => {
                    const btns = document.querySelectorAll('#onetrust-accept-btn-handler, .ot-sdk-container button');
                    for (const b of btns) {
                        if (/accept|akceptuj|zaakceptuj|zgadzam/i.test(b.textContent || '')) {
                            b.click();
                            return 'accepted';
                        }
                    }
                    return 'no-accept-btn';
                }"""
            )
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            print("ONETRUST ERROR:", repr(e))

        # kliknij "Kup teraz" przez JS click() (omija nakładke)
        clicked = page.evaluate(
            """() => {
                const el = document.querySelector('button[data-testid="item-buy-button"]');
                if (el) { el.click(); return true; }
                return false;
            }"""
        )
        print("KLIKNIETO przez JS:", clicked)

        time.sleep(12)  # czas na pelna sekwencje requestow

    results["captured"] = CAPTURED
    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")
    print(f"Liczba requestow purchases: {len(CAPTURED)}")


if __name__ == "__main__":
    main()