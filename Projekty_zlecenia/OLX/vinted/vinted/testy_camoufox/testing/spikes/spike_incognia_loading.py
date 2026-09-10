# coding: utf-8
"""Spike diagnostyczny: dlaczego SDK Incognia sie nie laduje na stronie Vinted.

Przechwytuje:
1. wszystkie <script src> (z DOM oraz z zyczenia sieciowego),
2. wszystkie requesty XHR/fetch,
3. headery CSP (content-security-policy) z odpowiedzi dokumentu i innych,
4. czy gdziekolwiek w requestach wystepuje 'incognia',
5. czy script incognia.js jest w DOM (querySelectorAll('script')).

Uruchomienie: python spike_incognia_loading.py  (headless, persistent profile)
Wynik: wynik_spike_incognia_loading.json
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_spike_incognia_loading.json"

ITEM_URL = "https://www.vinted.pl/items/9807925466"


def main() -> None:
    results = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": ITEM_URL,
        "script_requests": [],      # requesty na zasoby typu script
        "xhr_fetch_requests": [],   # requesty typu xhr/fetch
        "csp_headers": [],          # headery CSP znalezione w odpowiedziach
        "incognia_requests": [],    # requesty zawierajace 'incognia' w URL
        "all_requests_count": 0,
        "errors": [],
    }

    def on_request(request):
        results["all_requests_count"] += 1
        try:
            rtype = request.resource_type
            url = request.url
            if rtype == "script":
                results["script_requests"].append(url)
            elif rtype in ("xhr", "fetch"):
                results["xhr_fetch_requests"].append(url)
            if "incognia" in url.lower():
                results["incognia_requests"].append(url)
        except Exception as e:
            results["errors"].append(f"on_request: {e!r}")

    def on_response(response):
        try:
            headers = {k.lower(): v for k, v in response.headers.items()}
            for name in ("content-security-policy",
                         "content-security-policy-report-only",
                         "x-content-security-policy"):
                if name in headers:
                    results["csp_headers"].append(
                        {"url": response.url, "header": name, "value": headers[name]}
                    )
        except Exception as e:
            results["errors"].append(f"on_response: {e!r}")

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
        page.on("response", on_response)

        try:
            page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
        except Exception as e:
            results["errors"].append(f"goto: {e!r}")
        time.sleep(10)  # czas na doladowanie skryptow asynchronicznych

        # wszystkie <script> w DOM
        try:
            results["dom_scripts"] = page.evaluate(
                """() => Array.from(document.querySelectorAll('script')).map(s => ({
                    src: s.src || null,
                    id: s.id || null,
                    type: s.type || null,
                    has_inline: !s.src && (s.textContent || '').length > 0,
                }))"""
            )
        except Exception as e:
            results["dom_scripts"] = None
            results["errors"].append(f"dom_scripts: {e!r}")

        # czy w DOM jest skrypt incognia
        try:
            results["dom_incognia"] = page.evaluate(
                """() => {
                    const all = Array.from(document.querySelectorAll('script'));
                    const matches = all.filter(s =>
                        /incognia/i.test(s.src || '') || /incognia/i.test(s.textContent || '').toString() === 'true' && /incognia/i.test(s.textContent || '')
                    );
                    return {
                        total_scripts: all.length,
                        incognia_scripts: matches.map(s => s.src || (s.textContent || '').slice(0, 200)),
                        globals: (() => {
                            const out = [];
                            for (const k in window) if (/incognia/i.test(k)) out.push(k);
                            return out;
                        })(),
                    };
                }"""
            )
        except Exception as e:
            results["dom_incognia"] = None
            results["errors"].append(f"dom_incognia: {e!r}")

        # resource timing entries zawierajace 'incognia'
        try:
            results["perf_incognia"] = page.evaluate(
                """() => performance.getEntriesByType('resource')
                    .map(e => e.name).filter(u => /incognia/i.test(u))"""
            )
        except Exception as e:
            results["perf_incognia"] = None
            results["errors"].append(f"perf_incognia: {e!r}")

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # podsumowanie do konsoli
    print("=== SPIKE INCOGNIA LOADING ===")
    print("Wszystkie requesty:", results["all_requests_count"])
    print("Script requests:", len(results["script_requests"]))
    print("XHR/fetch requests:", len(results["xhr_fetch_requests"]))
    print("CSP headers:", len(results["csp_headers"]))
    for c in results["csp_headers"][:5]:
        print(" CSP:", c["header"], "@", c["url"][:80])
        print("   ", c["value"][:400])
    print("Incognia requests (network):", results["incognia_requests"])
    dom = results.get("dom_incognia") or {}
    print("DOM scripts total:", dom.get("total_scripts"))
    print("DOM incognia scripts:", dom.get("incognia_scripts"))
    print("Window globals z 'incognia':", dom.get("globals"))
    print("Perf entries incognia:", results.get("perf_incognia"))
    if results["errors"]:
        print("Errors:", results["errors"])

    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano do: {OUTPUT}")


if __name__ == "__main__":
    main()
