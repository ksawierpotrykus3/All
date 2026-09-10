"""Test: co przeglądarka wysyła w build_body (czy zawiera transaction_id?).

Rozstrzyga czy utworz_transakcje (inquiries) jest potrzebna przed buildem,
czy Vinted tworzy transaction automatycznie przy kliknięciu Kup teraz.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from camoufox import Camoufox

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vintedbot.refresh import WEBGL_CONFIG

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"build_body_{int(time.time())}.json"


def main() -> int:
    wynik = {"build_body": None, "build_resp": None, "inquiries": [], "item": None, "err": None}
    try:
        with Camoufox(persistent_context=True, headless=False, user_data_dir=PROFIL,
                      os="windows", fingerprint_preset=True, humanize=True,
                      webgl_config=WEBGL_CONFIG) as ctx:
            page = ctx.new_page()

            def on_request(req):
                if "checkout/build" in req.url:
                    try:
                        wynik["build_body"] = req.post_data
                    except Exception:
                        pass
                if "inquiries" in req.url:
                    try:
                        wynik["inquiries"].append(req.post_data)
                    except Exception:
                        pass

            def on_response(resp):
                if "checkout/build" in resp.url:
                    try:
                        wynik["build_resp"] = {"status": resp.status, "body": resp.text()[:2000]}
                    except Exception:
                        pass

            page.on("request", on_request)
            page.on("response", on_response)

            page.goto("https://www.vinted.pl/catalog?search_text=nike&order=newest_first",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            item_id = page.evaluate(
                """async () => {
                    const r = await fetch('/api/v2/catalog/items?search_text=nike&per_page=5&order=newest_first',
                                          {headers: {'Accept': 'application/json'}});
                    const j = await r.json();
                    return (j.items && j.items[0]) ? j.items[0].id : null;
                }"""
            )
            wynik["item"] = item_id
            if not item_id:
                wynik["err"] = "brak itemu"
                return 1

            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            try:
                page.evaluate(
                    "() => { const b=document.querySelector('#onetrust-accept-btn-handler'); if(b) b.click();"
                    " const f=document.querySelector('.onetrust-pc-dark-filter'); if(f) f.remove();"
                    " const c=document.querySelector('#onetrust-consent-sdk'); if(c) c.remove(); }"
                )
            except Exception:
                pass
            try:
                page.get_by_test_id("item-buy-button").click(timeout=20000)
            except Exception:
                try:
                    page.click("button:has-text('Kup teraz')", timeout=20000)
                except Exception as e:
                    wynik["err"] = f"klik: {e}"
            page.wait_for_timeout(8000)
    except Exception as e:
        wynik["err"] = f"outer: {e}"
    finally:
        OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(wynik, indent=2, ensure_ascii=False)[:3000], flush=True)
    print(f"[test] zapisano -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
