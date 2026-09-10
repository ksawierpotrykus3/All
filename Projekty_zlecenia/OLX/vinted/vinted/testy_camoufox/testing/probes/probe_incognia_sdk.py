# coding: utf-8
"""Probe: czy SDK Incognia w ogole laduje sie na stronie Vinted w headless Camoufox.

Sprawdza:
1. czy w DOM jest <script> z 'incognia' w src
2. czy window.Incognia / inne globalne istnieja
3. czy feature flag web_incognia_script jest wlaczona (z __NEXT_DATA__ / env)
4. jaka jest wartosc INCOGNIA_WEB_CLIENT_SIDE_KEY (z env)
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_probe_incognia_sdk.json"

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"


def main() -> None:
    results = {"steps": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

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
        time.sleep(6)  # czas na zaladowanie skryptow

        # 1. skrypty incognia w DOM
        try:
            scripts = page.evaluate(
                """() => {
                    return Array.from(document.querySelectorAll('script')).map(s => s.src | s.id | '').filter(x => /incognia/i.test(x));
                }"""
            )
            results["steps"].append({"step": "incognia_scripts", "data": scripts})
            print("INCOGNIA SCRIPTS:", scripts)
        except Exception as e:
            results["steps"].append({"step": "incognia_scripts", "error": repr(e)})

        # 2. globalne obiekty incognia
        try:
            globals_info = page.evaluate(
                """() => {
                    const out = {keys: []};
                    for (const k in window) if (/incognia/i.test(k)) out.keys.push(k);
                    out.Incognia = typeof window.Incognia;
                    out.incognia = typeof window.incognia;
                    return out;
                }"""
            )
            results["steps"].append({"step": "incognia_globals", "data": globals_info})
            print("INCOGNIA GLOBALS:", globals_info)
        except Exception as e:
            results["steps"].append({"step": "incognia_globals", "error": repr(e)})

        # 3. feature flag z __NEXT_DATA__ / window.__env
        try:
            flags = page.evaluate(
                """() => {
                    const out = {};
                    // feature flags czesto w __NEXT_DATA__ lub window.__ENV
                    const nd = window.__NEXT_DATA__;
                    if (nd && nd.props && nd.props.pageProps) {
                        const pp = nd.props.pageProps;
                        for (const k in pp) if (/incognia|feature/i.test(k)) out[k] = pp[k];
                    }
                    // sprawdz runtime config
                    try {
                        if (window.__ENV) out.__ENV_keys = Object.keys(window.__ENV).filter(k => /incognia/i.test(k));
                    } catch(e) {}
                    return out;
                }"""
            )
            results["steps"].append({"step": "feature_flags", "data": flags})
            print("FEATURE FLAGS:", flags)
        except Exception as e:
            results["steps"].append({"step": "feature_flags", "error": repr(e)})

        # 4. czy jest request o incognia w network (nasluch retrospektywnie nie dziala, wiec sprawdzmy performance entries)
        try:
            entries = page.evaluate(
                """() => {
                    return performance.getEntriesByType('resource')
                        .map(e => e.name)
                        .filter(u => /incognia|metrics\.vinted/i.test(u));
                }"""
            )
            results["steps"].append({"step": "network_incognia", "data": entries})
            print("NETWORK INCOGNIA:", entries)
        except Exception as e:
            results["steps"].append({"step": "network_incognia", "error": repr(e)})

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")


if __name__ == "__main__":
    main()