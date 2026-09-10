# coding: utf-8
"""Bezpieczny probe warstwy transakcyjnej: POST /purchases/checkout/build z BZDURNYM ID.

Cel: rozstrzygnac, czy headless Camoufox z zalogowana sesja przechodzi DataDome
rowniez na endpointzie zakupu, czy tam nadal dostaje blokade.

Bezpieczenstwo:
- ID 999999999999 NIE istnieje -> zero realnej rezerwacji, zero ryzyka bana.
- Zero platnosci.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_probe_checkout_build.json"

BOGUS_ITEM_ID = 999999999999


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

        # KROK 2: POST checkout/build z bzdurnym ID (bezpieczny probe)
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
                        body: await r.text()
                    };
                }""",
                BOGUS_ITEM_ID,
            )
            body = data.get("body", "") or ""
            step = {
                "step": "checkout_build_bogus",
                "item_id": BOGUS_ITEM_ID,
                "status": data.get("status"),
                "final_url": (data.get("final_url") or "")[:200],
                "body_head": body[:500],
                "datadome_signal": any(
                    k in (body or "").lower() for k in ("datadome", "captcha-delivery", "challenge")
                ),
            }
            print("CHECKOUT BUILD (BOGUS):", json.dumps(step, ensure_ascii=False))
            results["steps"].append(step)
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "checkout_build_bogus", "error": repr(e)})
            print("CHECKOUT BUILD ERROR:", repr(e))

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano wynik do: {OUTPUT}")


if __name__ == "__main__":
    main()