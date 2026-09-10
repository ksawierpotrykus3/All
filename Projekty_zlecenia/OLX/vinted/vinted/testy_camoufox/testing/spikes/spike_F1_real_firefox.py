"""SPIKE F1 - real Firefox (nie Camoufox): weryfikacja Incognia + trackerów + checkout flow.

Odpowiada na pytania:
1. Czy SDK Incognia ładuje się w prawdziwym Firefox (window.Incognia po 15s)?
2. Czy jest request do incognia.com?
3. Czy 6 zew. CDN trackerów ładuje się bez błędu "Loading failed"
   (pbstck, facebook, d34r8q7sht0t9k, openai, mgln.ai, gtm.js)?
4. Czy jest captcha na stronie przedmiotu?
5. Czy klik "Kup teraz" (page.click trusted) + POST /api/v2/purchases/checkout/build
   przechodzi bez 403?

Środowisko:
- Prawdziwy Firefox 150.0.2 (Playwright build firefox-1522), BEZ Camoufox
- Nowy, świeży profil w F:\TEMP\playwright_ff_real
- Cookies sesyjne Vinted zaimportowane z profilu Camoufox
  (Firefox 150 nie potrafi otworzyc profilu stworzonego przez Firefox 152 Camoufox -
   wersje roznia sie; Playwright launch_persistent_context zwrocil TimeoutError)

UWAGA: VINTED_EMAIL/VINTED_PASSWORD nie sa ustawione w tym srodowisku,
wiec zamiast logowania importujemy wazne cookies sesyjne z profilu Camoufox
(datadome + cf_clearance + access_token_web + refresh_token_web + _vinted_fr_session).

Wynik: C:\Temp\wynik_spike_F1_real_firefox.json
"""
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# ===== KONFIG =====
ITEM_ID = 9807925466
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"
PROFILE_SRC = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135")  # kanoniczny profil
PROFILE_NEW = Path(r"F:\TEMP\playwright_ff_real")
OUTPUT = Path(r"C:\Temp\wynik_spike_F1_real_firefox.json")

# Trackery ktorych sprawdzamy status ladowania (anty-camoufox artifact)
TRACKER_PATTERNS = {
    "pbstck":          ["pbstck.com", "pubstck"],
    "facebook":        ["facebook.com", "connect.facebook.net", "facebook.net"],
    "d34r8q7sht0t9k":  ["d34r8q7sht0t9k"],
    "openai":          ["openai.com", "chatgpt", "openai"],
    "mgln.ai":         ["mgln.ai"],
    "gtm.js":          ["/gtm.js", "googletagmanager.com/gtm"],
}


def load_cookies_from_camoufox_profile() -> list[dict]:
    """Czyta cookies Vinted z profilu Camoufox i konwertuje do formatu Playwright."""
    db_path = PROFILE_SRC / "cookies.sqlite"
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite "
        "FROM moz_cookies "
        "WHERE host LIKE '%vinted%' OR host LIKE '%datadome%' OR host LIKE '%incognia%'"
    ).fetchall()
    conn.close()

    # Mapowanie sameSite: 0=None, 1=SameSite, 2=Strict
    same_site_map = {0: "None", 1: "Lax", 2: "Strict", 3: "None", 4: "Lax", 5: "Strict"}

    cookies = []
    for name, value, host, path, expiry, is_secure, is_http, same_site in rows:
        # Firefox przechowuje expiry w SEKUNDACH
        expires_s = float(expiry) if expiry and expiry > 0 else -1
        if expires_s > 10**12:  # na wypadek ms
            expires_s = expires_s / 1000.0
        # Konwersja hosta: ".vinted.pl" -> ".vinted.pl" (z kropka) Playwright akceptuje
        cookies.append({
            "name": name,
            "value": value,
            "domain": host,
            "path": path or "/",
            "expires": expires_s,
            "httpOnly": bool(is_http),
            "secure": bool(is_secure),
            "sameSite": same_site_map.get(same_site, "None"),
        })
    return cookies


def classify_tracker(url: str) -> str | None:
    u = url.lower()
    for name, patterns in TRACKER_PATTERNS.items():
        if any(p.lower() in u for p in patterns):
            return name
    return None


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # === 0. Przygotowanie nowego profilu ===
    if PROFILE_NEW.exists():
        shutil.rmtree(PROFILE_NEW, ignore_errors=True)
    PROFILE_NEW.parent.mkdir(parents=True, exist_ok=True)
    # Tworzymy pusty katalog - Playwright sam zainicjalizuje profil Firefox
    PROFILE_NEW.mkdir(exist_ok=True)

    # Wczytaj cookies z profilu Camoufox
    imported_cookies = load_cookies_from_camoufox_profile()
    print(f"[INIT] Zaimportowano {len(imported_cookies)} cookies z profilu Camoufox")
    key_cookies = [c for c in imported_cookies if c["name"] in (
        "access_token_web", "refresh_token_web", "_vinted_fr_session",
        "datadome", "cf_clearance", "__cf_bm", "anon_id", "v_sid", "v_uid"
    )]
    print(f"[INIT] Kluczowe cookies sesyjne: {len(key_cookies)}")
    for c in key_cookies:
        exp_iso = "session" if c["expires"] <= 0 else datetime.fromtimestamp(
            c["expires"], tz=timezone.utc
        ).isoformat()
        print(f"  - {c['name']:25s} @ {c['domain']:30s} exp={exp_iso}")

    result = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": ITEM_URL,
        "browser": "Playwright Firefox 150.0.2 (REAL Firefox, nie Camoufox)",
        "profile": str(PROFILE_NEW),
        "imported_cookies_count": len(imported_cookies),
        "all_requests": [],
        "responses": [],
        "console_errors": [],
        "page_errors": [],
        "incognia_check": {},
        "tracker_load_results": {n: {"hit": [], "failed": [], "loading_failed_console": []}
                                  for n in TRACKER_PATTERNS},
        "performance_incognia_resources": [],
        "checkout_attempt": {},
        "captcha_check": {},
        "incognia_globals_keys": [],
        "steps": [],
        "errors": [],
    }

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser_info = p.firefox
        print(f"\n[BROWSER] executable_path: {browser_info.executable_path}")
        result["firefox_executable"] = browser_info.executable_path

        # === 1. Uruchom real Firefox z nowym profilem ===
        t0 = time.monotonic()
        ctx = p.firefox.launch_persistent_context(
            user_data_dir=str(PROFILE_NEW),
            headless=True,
            viewport={"width": 1280, "height": 720},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) "
                        "Gecko/20100101 Firefox/150.0"),
            locale="pl-PL",
            timezone_id="Europe/Warsaw",
            extra_http_headers={
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
            },
            ignore_https_errors=False,
        )
        result["steps"].append({
            "step": "launch_persistent_context",
            "ms": round((time.monotonic() - t0) * 1000, 1),
        })
        page = ctx.new_page()
        result["firefox_version"] = browser_info.executable_path  # placeholder

        # === 2. Import cookies PRZED nawigacja na Vinted ===
        try:
            ctx.add_cookies(imported_cookies)
            print(f"[COOKIES] Dodano {len(imported_cookies)} cookies do kontekstu")
            result["cookies_added"] = len(imported_cookies)
        except Exception as e:
            result["errors"].append(f"add_cookies: {e!r}")
            print(f"[ERROR] add_cookies: {e!r}")

        # === 3. Event listenery ===
        def on_request(req):
            try:
                entry = {
                    "method": req.method,
                    "url": req.url,
                    "rtype": req.resource_type,
                    "post": req.post_data if req.post_data else None,
                }
                result["all_requests"].append(entry)
                tracker = classify_tracker(req.url)
                if tracker:
                    result["tracker_load_results"][tracker]["hit"].append(req.url[:200])
            except Exception as e:
                result["errors"].append(f"on_request: {e!r}")

        def on_response(resp):
            try:
                entry = {
                    "url": resp.url,
                    "status": resp.status,
                    "headers": dict(resp.headers),
                }
                result["responses"].append(entry)
                tracker = classify_tracker(resp.url)
                if tracker and resp.status >= 400:
                    result["tracker_load_results"][tracker]["failed"].append({
                        "url": resp.url[:200],
                        "status": resp.status,
                    })
            except Exception as e:
                result["errors"].append(f"on_response: {e!r}")

        def on_console(msg):
            try:
                text = msg.text
                if msg.type in ("error", "warning"):
                    result["console_errors"].append({"type": msg.type, "text": text[:300]})
                    # Wykryj specyficzny blad "Loading failed" dla trackerow
                    for tracker in TRACKER_PATTERNS:
                        if tracker.lower() in text.lower() and "loading failed" in text.lower():
                            result["tracker_load_results"][tracker]["loading_failed_console"].append(text[:300])
                        # czesc bledow nie zawiera nazwy trackera - loguj wszystkie "Loading failed"
                        if "loading failed" in text.lower():
                            result.setdefault("all_loading_failed", []).append(text[:300])
            except Exception as e:
                result["errors"].append(f"on_console: {e!r}")

        def on_pageerror(exc):
            result["page_errors"].append(str(exc)[:400])

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

        # === 4. Goto item ===
        print(f"\n[NAV] goto {ITEM_URL}")
        t0 = time.monotonic()
        try:
            page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            result["errors"].append(f"goto: {e!r}")
            print(f"[ERROR] goto: {e!r}")
        result["steps"].append({"step": "goto", "ms": round((time.monotonic() - t0) * 1000, 1)})
        print(f"[NAV] document.title = {page.title()}")

        # === 5. Sprawdz status zalogowania ===
        t0 = time.monotonic()
        user_info = page.evaluate("""async () => {
            try {
                const r = await fetch('/api/v2/users/current', {
                    credentials: 'include',
                    headers: {'Accept': 'application/json'}
                });
                const t = await r.text();
                let body = null; try { body = JSON.parse(t); } catch(e) {}
                return {
                    status: r.status,
                    login: body?.user?.login ?? body?.login ?? null,
                    id: body?.user?.id ?? body?.id ?? null,
                    body_excerpt: t.slice(0, 200),
                };
            } catch(e) { return {error: String(e)}; }
        }""")
        result["login_check"] = user_info
        result["steps"].append({"step": "login_check", "ms": round((time.monotonic() - t0) * 1000, 1)})
        print(f"[AUTH] users/current: {user_info}")

        # === 6. Czekaj 15s na Incognia (moze ladowac sie asynchronicznie) ===
        print(f"\n[WAIT] 15s na potencjalne zaladowanie SDK Incognia...")
        time.sleep(15)

        # === 7. Sprawdz Incognia w window ===
        incognia_check = page.evaluate("""() => {
            const out = {
                has_Incognia: typeof window.Incognia !== 'undefined',
                Incognia_keys: window.Incognia ? Object.keys(window.Incognia).slice(0, 30) : null,
                globals_with_incognia: [],
                dataLayer_keys: [],
                consentOneTrust: typeof window.OneTrust !== 'undefined',
                gtag_present: typeof window.gtag === 'function',
            };
            for (const k in window) {
                if (/incognia/i.test(k)) out.globals_with_incognia.push(k);
            }
            if (window.dataLayer && Array.isArray(window.dataLayer)) {
                window.dataLayer.slice(-20).forEach(e => {
                    if (e && typeof e === 'object') out.dataLayer_keys.push(Object.keys(e).slice(0, 10));
                });
            }
            return out;
        }""")
        result["incognia_check"] = incognia_check
        print(f"[INCOGNIA] {incognia_check}")

        # === 8. Resource Timing - czy byly requesty do incognia.com ===
        perf_incognia = page.evaluate("""() => {
            return performance.getEntriesByType('resource')
                .map(e => ({name: e.name, duration: Math.round(e.duration),
                            transferSize: e.transferSize,
                            responseStatus: e.responseStatus}))
                .filter(e => /incognia/i.test(e.name));
        }""")
        result["performance_incognia_resources"] = perf_incognia
        print(f"[PERF] Incognia resources: {len(perf_incognia)}")

        # === 9. Sprawdz captche ===
        captcha_check = page.evaluate("""() => {
            const txt = document.body.innerText.toLowerCase();
            const hasText = (s) => txt.includes(s);
            const cfFrame = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
            const cfScript = document.querySelector('script[src*="challenges.cloudflare.com"]');
            const cfDiv = document.querySelector('div[id*="cf-"]');
            const hCaptcha = document.querySelector('iframe[src*="hcaptcha.com"]');
            const recaptcha = document.querySelector('iframe[src*="recaptcha"]');
            return {
                has_cloudflare_text: hasText('verify you are human') || hasText('sprawdź czy jesteś człowiekiem'),
                cloudflare_frame: !!cfFrame,
                cloudflare_script: !!cfScript,
                cloudflare_div: !!cfDiv,
                has_hcaptcha: !!hCaptcha,
                has_recaptcha: !!recaptcha,
                datadome_blocked: hasText('access denied') || hasText('blocked'),
                page_text_excerpt: document.body.innerText.slice(0, 600),
            };
        }""")
        result["captcha_check"] = captcha_check
        print(f"[CAPTCHA] cloudflare: {captcha_check['cloudflare_frame']}, hCaptcha: {captcha_check['has_hcaptcha']}, reCAPTCHA: {captcha_check['has_recaptcha']}")

        # === 10. Czekaj na przycisk Kup teraz ===
        print("\n[BUTTON] Czekam na przycisk 'Kup teraz'...")
        t0 = time.monotonic()
        btn_found = False
        try:
            page.wait_for_selector('button[data-testid="item-buy-button"]', timeout=30000)
            btn_found = True
        except Exception as e:
            result["errors"].append(f"button_wait: {e!r}")
            print(f"[ERROR] Nie znaleziono przycisku: {e!r}")
        result["steps"].append({
            "step": "button_ready",
            "ms": round((time.monotonic() - t0) * 1000, 1),
            "found": btn_found,
        })

        if btn_found:
            # === 11. Sprawdz stan konta: czy jesteś zalogowany ===
            page_info = page.evaluate("""() => {
                const btn = document.querySelector('button[data-testid="item-buy-button"]');
                return {
                    btn_text: btn ? btn.innerText : null,
                    btn_disabled: btn ? btn.disabled : null,
                    btn_data_visual: btn ? btn.getAttribute('data-testid') : null,
                };
            }""")
            result["buy_button_state"] = page_info
            print(f"[BUTTON] {page_info}")

            # === 12. Ponowne sprawdzenie Incognia tuz przed klikiem ===
            pre_click_incognia = page.evaluate("""() => ({
                has_Incognia: typeof window.Incognia !== 'undefined',
                keys: typeof window.Incognia !== 'undefined' ? Object.keys(window.Incognia) : []
            })""")
            result["incognia_pre_click"] = pre_click_incognia

            # === 13. Przechwyc POST /purchases/checkout/build (bez klikania) ===
            captured_posts = []
            def on_post_capture(req):
                if "/api/v2/purchases" in req.url and req.method == "POST":
                    captured_posts.append({"url": req.url, "post": req.post_data})
            page.on("request", on_post_capture)

            # === 14. TRUSTED CLICK page.click() ===
            print("\n[CLICK] TRUSTED page.click('button[data-testid=item-buy-button]')...")
            t_click = time.monotonic()
            try:
                page.click('button[data-testid="item-buy-button"]', timeout=15000)
                result["steps"].append({
                    "step": "click_trusted",
                    "ms": round((time.monotonic() - t_click) * 1000, 1),
                })
                print("[CLICK] OK")
            except Exception as e:
                result["steps"].append({
                    "step": "click_trusted", "error": repr(e),
                })
                print(f"[ERROR] click: {e!r}")

            # === 15. Czekaj na POST checkout/build (do 20s) ===
            print("\n[WAIT] Czekam do 20s na POST /api/v2/purchases/checkout/build...")
            deadline = time.monotonic() + 20
            checkout_resp = None
            while time.monotonic() < deadline:
                for resp in result["responses"]:
                    if "checkout/build" in resp["url"] or "purchases/checkout" in resp["url"]:
                        checkout_resp = resp
                        break
                if checkout_resp:
                    break
                time.sleep(0.5)

            # Buduj zestawienie checkout
            checkout_attempt = {
                "captured_posts": captured_posts[:5],
                "checkout_build_responses": [r for r in result["responses"]
                                              if "/purchases/checkout" in r["url"]],
            }
            result["checkout_attempt"] = checkout_attempt

            if checkout_resp:
                print(f"[CHECKOUT] Response status: {checkout_resp['status']}")
                print(f"[CHECKOUT] URL: {checkout_resp['url']}")
                # Sprawdz czy nie 403
                result["checkout_no_403"] = checkout_resp["status"] != 403
                if checkout_resp["status"] == 403:
                    print("[CHECKOUT] !!! 403 - forbidden !!!")
                elif checkout_resp["status"] == 200:
                    print("[CHECKOUT] OK - 200")
            else:
                print("[CHECKOUT] Brak odpowiedzi /api/v2/purchases/checkout/build w 20s")
                result["checkout_no_403"] = None  # unknown

            # === 16. Sprawdz Incognia po kliku ===
            time.sleep(3)
            post_click_incognia = page.evaluate("""() => ({
                has_Incognia: typeof window.Incognia !== 'undefined',
                keys: typeof window.Incognia !== 'undefined' ? Object.keys(window.Incognia) : []
            })""")
            result["incognia_post_click"] = post_click_incognia
            print(f"[INCOGNIA POST-CLICK] {post_click_incognia}")

        # === 17. Finalne podsumowanie trackerów ===
        print("\n=== PODSUMOWANIE TRACKERÓW ===")
        for name, data in result["tracker_load_results"].items():
            hits = len(data["hit"])
            fails = len(data["failed"])
            console_fails = len(data["loading_failed_console"])
            status = "OK" if hits > 0 and fails == 0 and console_fails == 0 else "FAIL"
            print(f"  {name:15s} hits={hits:3d}  http_fail={fails:2d}  console_load_failed={console_fails:2d}  -> {status}")

        # === 18. Statystyki bledow Loading failed ===
        all_lf = result.get("all_loading_failed", [])
        if all_lf:
            print(f"\n[LOADING-FAILED] {len(all_lf)} 'Loading failed' console errors:")
            for e in all_lf[:10]:
                print(f"  - {e}")
        else:
            print("\n[LOADING-FAILED] 0 'Loading failed' console errors w Firefox real")

        result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        result["summary"] = {
            "firefox_version": "150.0.2 (Playwright)",
            "profile": str(PROFILE_NEW),
            "profile_was_fresh": True,
            "cookies_imported_from_camoufox_profile": len(imported_cookies),
            "login_status": user_info.get("login"),
            "user_id": user_info.get("id"),
            "incognia_loaded": incognia_check.get("has_Incognia", False),
            "incognia_requests": len(perf_incognia),
            "captcha_detected": (
                captcha_check.get("cloudflare_frame", False)
                or captcha_check.get("has_hcaptcha", False)
                or captcha_check.get("has_recaptcha", False)
                or captcha_check.get("has_cloudflare_text", False)
            ),
            "buy_button_visible": btn_found,
            "checkout_no_403": result.get("checkout_no_403"),
            "total_requests": len(result["all_requests"]),
            "total_responses": len(result["responses"]),
            "console_errors_total": len(result["console_errors"]),
            "page_errors_total": len(result["page_errors"]),
            "loading_failed_console_total": len(all_lf),
            "tracker_summary": {
                name: {
                    "hits": len(data["hit"]),
                    "http_failed": len(data["failed"]),
                    "console_loading_failed": len(data["loading_failed_console"]),
                    "urls_hit_sample": data["hit"][:3],
                    "http_failed_sample": data["failed"][:3],
                }
                for name, data in result["tracker_load_results"].items()
            },
        }

        OUTPUT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[DONE] Raport zapisany do {OUTPUT}")
        print(f"[DONE] Rozmiar: {OUTPUT.stat().st_size:,} bytes")

        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
