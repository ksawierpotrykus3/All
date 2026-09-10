"""Badanie struktury DataDome slider challenge (iframe captcha-delivery.com).

Otwiera item, klika Kup teraz, czeka na iframe slidera i zrzuca:
- listę ramek (frames) i ich URL
- strukturę DOM iframe captcha (elementy suwaka)
- pozycje/rozmiary kluczowych elementów
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
OUT = ROOT / "output" / f"slider_struktura_{int(time.time())}.json"


def main() -> int:
    wynik = {"frames": [], "captcha_dom": None, "err": None}
    with Camoufox(persistent_context=True, headless=False, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()

        # Pobierz item z katalogu.
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
            OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
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

        # Kliknij aby wywołać challenge.
        try:
            page.get_by_test_id("item-buy-button").click(timeout=20000)
        except Exception:
            try:
                page.click("button:has-text('Kup teraz')", timeout=20000)
            except Exception as e:
                wynik["err"] = f"klik: {e}"

        # Czekaj aż iframe captcha się pojawi (max 20s).
        captcha_frame = None
        for _ in range(40):
            for fr in page.frames:
                if "captcha-delivery.com" in (fr.url or ""):
                    captcha_frame = fr
                    break
            if captcha_frame:
                break
            page.wait_for_timeout(500)

        wynik["frames"] = [{"url": fr.url, "name": fr.name} for fr in page.frames]

        if not captcha_frame:
            wynik["err"] = "iframe captcha NIE pojawił się (build mógł przejść 200 albo inny błąd)"
            OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(wynik, indent=2, ensure_ascii=False)[:2000], flush=True)
            return 0

        # Zrzut DOM iframe captcha.
        try:
            dom = captcha_frame.evaluate(
                """() => {
                    const els = [];
                    document.querySelectorAll('*').forEach(el => {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            els.push({
                                tag: el.tagName, id: el.id || null,
                                cls: el.className && el.className.baseVal !== undefined ? el.className.baseVal : (el.className || null),
                                x: Math.round(r.x), y: Math.round(r.y),
                                w: Math.round(r.width), h: Math.round(r.height),
                            });
                        }
                    });
                    return {url: location.href, title: document.title, els: els.slice(0, 120)};
                }"""
            )
            wynik["captcha_dom"] = dom
        except Exception as e:
            wynik["err"] = f"dom iframe: {e}"

    OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(wynik, indent=2, ensure_ascii=False)[:3500], flush=True)
    print(f"[slider] zapisano -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
