# coding: utf-8
"""DECYDUJĄCY test pełnego replayu: curl_cffi + cookie jar z profilu Camoufox.

Empirycznie zweryfikowane w tej sesji:
- cookie `datadome` z prawdziwego beacona przeglądarki wstrzyknięte do curl_cffi
  PRZECHODZI warstwę transportową DataDome (POST /checkout/build przestaje zwracać
  challenge JSON {"url": "geo.captcha-delivery.com/..."} i zaczyna zwracać aplikacyjne
  403 access_denied -> czyli transport OK, brakuje tylko logowania).
- Prawdziwa (zalogowana) sesja Vinted jest trzymana w profilu Camoufox `profil_firefox_135`
  (skrypt refresh_cookies_headless.py już jej używa).

Ten test: warmup przeglądarki (beacon DataDome + auto-refresh tokenu) -> eksport cookie
jar -> replay przez curl_cffi (impersonate chrome146) -> POST /purchases/checkout/build.

Zakaz mockowania wewnętrznych klas: test używa prawdziwego curl_cffi i prawdziwej
przeglądarki Camoufox, aż do requestu API.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr
from curl_cffi import BrowserType
from camoufox.sync_api import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUTPUT = BASE_DIR / "wynik_replay_pelny.json"

ITEM_ID = 9807925466
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}-genesis-krypton-700"
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CURRENT_USER_URL = "https://www.vinted.pl/api/v2/users/current"


def _check_login(page):
    """Sprawdza czy sesja przeglądarki jest zalogowana."""
    try:
        data = page.evaluate(
            """async () => {
                const r = await fetch('/api/v2/users/current', {
                    headers: {'Accept': 'application/json'}
                });
                if (r.status !== 200) return null;
                const j = await r.json();
                const u = j.user || {};
                return (u.login || u.id) ? {login: u.login, id: u.id} : null;
            }"""
        )
        return data
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


def _extract_csrf(page):
    """Szuka tokenu CSRF w DOM/cookie/window."""
    try:
        m = page.evaluate(
            """() => {
                const el = document.querySelector('meta[name="csrf-token"]');
                if (el && el.content) return el.content;
                const c = document.cookie.match(/(?:^|; )_vinted_csrftoken=([^;]*)/);
                if (c) return decodeURIComponent(c[1]);
                if (window.__V) {
                    if (window.__V.csrfToken) return window.__V.csrfToken;
                    if (window.__V.csrf) return window.__V.csrf;
                }
                return null;
            }"""
        )
        return m
    except Exception:  # noqa: BLE001
        return None


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

        # Przechwyć x-csrf-token / x-anon-id z prawdziwych API requestów frontendu
        captured_headers = {}

        def on_request(request):
            try:
                url = request.url
                if "vinted" not in url or "api" not in url:
                    return
                h = request.headers
                if "x-csrf-token" in h and "x_csrf" not in captured_headers:
                    captured_headers["x_csrf"] = h["x-csrf-token"]
                if "x-anon-id" in h and "x_anon" not in captured_headers:
                    captured_headers["x_anon"] = h["x-anon-id"]
            except Exception:  # noqa: BLE001
                pass

        page.on("request", on_request)

        # KROK 1: warmup - wejście na item page (DataDome beacon + auto-refresh tokenu)
        try:
            page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(8)  # daj czas na beacon jspl + refresh tokenu + API calls frontendu
            results["steps"].append({"step": "warmup", "title": page.title()})
            print("WARMUP OK:", page.title())
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "warmup", "error": repr(e)})
            print("WARMUP ERROR:", repr(e))

        # KROK 2: logowanie + csrf (z DOM lub z przechwyconych requestów)
        login = _check_login(page)
        csrf = _extract_csrf(page) or captured_headers.get("x_csrf")
        anon_hdr = captured_headers.get("x_anon")
        results["login"] = login
        results["csrf_found"] = bool(csrf)
        results["csrf_source"] = "dom" if _extract_csrf(page) else ("network" if csrf else None)
        results["captured_headers"] = captured_headers
        print("LOGIN:", login)
        print("CSRF:", (csrf or "BRAK")[:40])
        print("CAPTURED:", captured_headers)

        # KROK 3: eksport cookie jar
        cookies = ctx.cookies()
        results["cookies_count"] = len(cookies)
        results["cookie_names"] = [c["name"] for c in cookies]
        results["has_datadome"] = "datadome" in results["cookie_names"]
        print(f"COOKIES: {len(cookies)}, datadome={'datadome' in results['cookie_names']}")

        anon = next((c["value"] for c in cookies if c["name"] == "anon_id"), None)
        anon = anon or anon_hdr

        # KROK 4: replay przez curl_cffi
        s = cr.Session()
        for c in cookies:
            try:
                s.cookies.set(
                    c["name"], c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )
            except Exception:  # noqa: BLE001
                pass

        s.headers.update({
            "accept": "*/*",
            "accept-language": "pl,en-US;q=0.9,en;q=0.8",
            "origin": "https://www.vinted.pl",
            "referer": ITEM_URL,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })

        # 4a. GET item page
        try:
            r1 = s.get(ITEM_URL, impersonate=BrowserType.chrome146, timeout=30)
            results["steps"].append({"step": "replay_get_item", "status": r1.status_code})
            print("REPLAY GET item:", r1.status_code)
        except Exception as e:  # noqa: BLE001
            results["steps"].append({"step": "replay_get_item", "error": repr(e)})
            print("REPLAY GET ERROR:", repr(e))

        # 4b. POST checkout/build (type=item) - z CSRF; potem wariant kontrolny bez CSRF
        build_headers = {"content-type": "application/json"}
        if csrf:
            build_headers["x-csrf-token"] = csrf
        if anon:
            build_headers["x-anon-id"] = anon
        body = {"purchase_items": [{"id": ITEM_ID, "type": "item"}]}

        r2 = s.post(
            BUILD_URL, json=body, headers=build_headers,
            impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False,
        )
        step = {
            "step": "replay_post_build",
            "with_csrf": bool(csrf),
            "status": r2.status_code,
            "is_transport_challenge": r2.text.startswith('{"url"'),
            "body": r2.text[:600],
        }
        results["steps"].append(step)
        print("REPLAY POST build (csrf=", bool(csrf), "):", r2.status_code)
        print("BODY:", r2.text[:300])
        if "x-datadome" in r2.headers:
            step["x_datadome"] = r2.headers.get("x-datadome")

        # Wariant kontrolny: BEZ x-csrf-token (dowód, że to on jest brakującym elementem)
        if csrf:
            headers_no_csrf = {"content-type": "application/json"}
            if anon:
                headers_no_csrf["x-anon-id"] = anon
            r3 = s.post(
                BUILD_URL, json=body, headers=headers_no_csrf,
                impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False,
            )
            results["steps"].append({
                "step": "replay_post_build_no_csrf",
                "status": r3.status_code,
                "is_transport_challenge": r3.text.startswith('{"url"'),
                "body": r3.text[:300],
            })
            print("REPLAY POST build (bez csrf):", r3.status_code, r3.text[:150])

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano wynik do: {OUTPUT}")


if __name__ == "__main__":
    main()
