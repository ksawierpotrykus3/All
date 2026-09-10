# coding: utf-8
"""Probe: czy z evaluate da sie siegnac do wewnetrznych modulow (webpack require) i SDK Incognia.

Jesli webpack rejestr jest dostepny, mozemy wywolac initiateSingleCheckout bezposrednio,
pomijajac DOM i OneTrust. Jesli nie - klik w DOM jest jedyna droga.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_internal_modules.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"


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

        probe = page.evaluate(
            """() => {
                const out = {};

                // 1. webpack require (Next.js/turbopack)
                out.has_webpack_require = typeof window.__webpack_require__ !== 'undefined';
                out.has_webpack_chunk = typeof window.webpackChunk !== 'undefined';
                out.has_next_f = typeof window.__next_f !== 'undefined';

                // 2. szukaj globali z 'require', 'module', 'chunk' w nazwie
                const globals = Object.keys(window);
                out.require_like = globals.filter(k => /require|webpack|chunk|module/i.test(k)).slice(0, 30);

                // 3. szukaj obiektu incognia w calym window (glebiej: sprawdz czy jest w jakims globalnym store)
                out.incognia_globals = globals.filter(k => /incognia/i.test(k));

                // 4. React fiber root (czy jest dostepny __reactContainer$ / __reactFiber$)
                out.react_container_globals = globals.filter(k => /react/i.test(k)).slice(0, 30);

                return out;
            }"""
        )
        results["probe"] = probe
        print("PROBE:", json.dumps(probe, ensure_ascii=False, indent=2))

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")


if __name__ == "__main__":
    main()