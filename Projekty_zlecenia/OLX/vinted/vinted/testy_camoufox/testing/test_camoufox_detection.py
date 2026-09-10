# coding: utf-8
"""Smoke test detekcji: czy headless Camoufox (Firefox) przechodzi DataDome anonimowo.

Bezpieczenstwo:
- zero logowania, zero cookies, zero rezerwacji, zero endpointow transakcyjnych.
- tylko anonimowe wejscie na Vinted + anonimowy odczyt katalogu.

Cel: sprawdzic, czy silnik Camoufox (realny fingerprint Firefoksa) przechodzi
DataDome tam, gdzie headless Chromium/Playwright dostawal 403/captche.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "wynik_camoufox_detekcja.json"


def _has_datadome(parts) -> bool:
    """Szuka sygnalow DataDome/blokady w laczonym tekscie (case-insensitive)."""
    haystack = " ".join(str(p).lower() for p in parts if p)
    return any(k in haystack for k in ("datadome", "captcha-delivery", "challenge"))


def main() -> None:
    results = {"steps": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    with Camoufox(
        headless=True,
        os="windows",
        fingerprint_preset=True,
        humanize=True,
    ) as browser:
        page = browser.new_page()

        # KROK 1: strona glowna
        try:
            resp = page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
            title = page.title()
            body = page.content()
            headers = dict(resp.headers) if resp else {}
            step1 = {
                "step": "home",
                "status": resp.status if resp else None,
                "final_url": page.url,
                "title": title,
                "body_len": len(body),
                "x_datadome": headers.get("x-datadome"),
                "datadome_signal": _has_datadome([title, body, headers.get("x-datadome")]),
            }
            print("HOME:", json.dumps(step1, ensure_ascii=False))
            results["steps"].append(step1)
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "home", "error": repr(e)})
            print("HOME ERROR:", repr(e))

        time.sleep(2)

        # KROK 2: anonimowy odczyt katalogu z wnetrza strony (fetch)
        try:
            resp2 = page.evaluate(
                """async () => {
                    const r = await fetch('/api/v2/catalog/items', {
                        headers: {'Accept': 'application/json'}
                    });
                    return {status: r.status, body: await r.text()};
                }"""
            )
            body2 = resp2.get("body", "") or ""
            step2 = {
                "step": "catalog_items_fetch",
                "status": resp2.get("status"),
                "body_len": len(body2),
                "datadome_signal": _has_datadome([body2]),
                "body_head": body2[:200],
            }
            print("CATALOG FETCH:", json.dumps(step2, ensure_ascii=False))
            results["steps"].append(step2)
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "catalog_items_fetch", "error": repr(e)})
            print("CATALOG FETCH ERROR:", repr(e))

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano wynik do: {OUTPUT}")


if __name__ == "__main__":
    main()