# coding: utf-8
"""REALNA rezerwacja checkout/build na wlasnym przedmiocie testowym 9806080522.

Konta:
- kupujacy: maksks0 (zalogowany w profilu Camoufox)
- sprzedajacy: inne konto testowe (wlasciciel przedmiotu test123)

Bezpieczenstwo:
- przedmiot jest wlasny (testowy), nie cudzy
- BEZ platnosci - tylko POST /purchases/checkout/build (rezerwacja)
- naglowek X-CSRF-Token (hardcoded z kodu), bez Incognia (celowo - do sprawdzenia czy jest wymagany)
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_rezerwacja_realna.json"

ITEM_ID = 9806080522


def main() -> None:
    results = {"steps": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
    ) as ctx:
        page = ctx.new_page()

        # KROK 1: wejscie na strone (ustalenie sesji DataDome)
        try:
            page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            results["steps"].append({"step": "home", "title": page.title()})
            print("HOME OK:", page.title())
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "home", "error": repr(e)})
            print("HOME ERROR:", repr(e))

        # KROK 2: realna rezerwacja checkout/build
        try:
            data = page.evaluate(
                """async (itemId) => {
                    const r = await fetch('/api/v2/purchases/checkout/build', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'X-CSRF-Token': '75f6c9fa-dc8e-4e52-a000-e09dd4084b3e',
                        },
                        body: JSON.stringify({purchase_items: [{id: itemId, type: 'item'}]})
                    });
                    return {
                        status: r.status,
                        final_url: r.url,
                        body: await r.text(),
                        headers: Object.fromEntries(r.headers.entries())
                    };
                }""",
                ITEM_ID,
            )
            body = data.get("body", "") or ""
            step = {
                "step": "checkout_build_real",
                "item_id": ITEM_ID,
                "status": data.get("status"),
                "final_url": (data.get("final_url") or "")[:200],
                "body": body,
                "has_datadome_header": "x-datadome" in (data.get("headers") or {}),
                "content_type": (data.get("headers") or {}).get("content-type", ""),
            }
            print("STATUS:", data.get("status"))
            print("BODY:", body[:1500])
            results["steps"].append(step)
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "checkout_build_real", "error": repr(e)})
            print("ERROR:", repr(e))

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano wynik do: {OUTPUT}")


if __name__ == "__main__":
    main()