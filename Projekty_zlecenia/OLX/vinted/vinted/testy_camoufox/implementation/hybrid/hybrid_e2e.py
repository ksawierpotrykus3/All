# coding: utf-8
"""
hybrid_e2e.py — kompletny flow end-to-end: Camoufox (build) + curl_cffi (PUT + payment).

Architektura (wynik Priorytetu 0, sekcja 30):
- `checkout/build` przez czysty curl_cffi = 403 DataDome (UDOWODNIONE).
- Jedyne, co wymaga przegladarki, to trusted click "Kup teraz" -> build.
- Reszta (PUT payment_method, PUT pickup_details, POST payment) dziala przez curl_cffi,
  pod warunkiem uzycia swiezych cookies z kontekstu Camoufox i checksum z OSTATNIEGO PUT
  (checksum rotuje przy kazdej aktualizacji checkoutu — sekcja 20.8.6).

Sekwencja:
1. Camoufox: strona itemu -> klik "Kup teraz" (trusted) -> przechwycenie builda
   (checkout_id + components + pierwotny checksum) + eksport swiezych cookies.
2. curl_cffi (swieze cookies z Camoufox):
   a. PUT payment_method (pay_in_method_id=12 = Przelewy24) -> checksum rotuje
   b. GET nearby pickup points -> wybor punktu (suggested lub pierwszy)
   c. PUT pickup_details -> FINAL checksum
   d. POST payment z FINAL checksum + browser_info (pre-computed fingerprint) + token Incognia
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMPERSONATE = "firefox133"
OUT = BASE_DIR / "wynik_hybrid_e2e.json"

results = {"steps": []}


def _log(name, **extra):
    e = {"step": name, "ts": time.time()}
    e.update(extra)
    results["steps"].append(e)
    print(f"[{name}] {extra}" if extra else f"[{name}]", flush=True)


def _find_checksum(obj):
    """Rekurencyjnie szuka pierwszego klucza 'checksum'."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                return v
            r = _find_checksum(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_checksum(v)
            if r:
                return r
    return None


def _load_fingerprint() -> dict:
    fp = json.loads((BASE_DIR / "fingerprint_datadome.json").read_text(encoding="utf-8"))
    return fp


def _merge_cookies(base_file_cookies: list, ctx_cookies: list) -> list:
    """Laczy statyczne cookies z cookies_profil.json (pokrywaja api.vinted.pl)
    ze swiezymi cookies z kontekstu Camoufox (datadome po kliknieciu)."""
    merged: dict[tuple, dict] = {}
    for c in list(base_file_cookies) + list(ctx_cookies):
        key = (c.get("domain", ""), c.get("name", ""), c.get("path", "/"))
        merged[key] = c
    return list(merged.values())


def _gen_token(sdk_instance_id: str) -> str:
    """Generuje x-incognia-request-token przez Node.js (HKDF + AES-GCM)."""
    import subprocess
    r = subprocess.run(
        ["node", str(BASE_DIR / "generate_incognia_token.js"), sdk_instance_id],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Node error: {r.stderr}")
    return r.stdout.strip()


def _session_from(cookies: list) -> cr.Session:
    # UWAGA: BEZ naglowka "authorization" — autoryzacja idzie przez cookie
    # access_token_web (domena .vinted.pl pokrywa api.vinted.pl). Dodanie
    # Bearer powodowalo 403 "Access denied" (code 106) na api.vinted.pl/shipping-estimation.
    s = cr.Session()
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "priority": "u=3",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    })
    return s


def _btn_state(page):
    """Zwraca stan przycisku 'Kup teraz' po hydratacji (sekcja 31.4)."""
    return page.evaluate(
        """() => {
            const b = document.querySelector('button[data-testid="item-buy-button"]');
            if (!b) return {found: false};
            const r = b.getBoundingClientRect();
            const cs = getComputedStyle(b);
            return {
                found: true,
                disabled: b.disabled,
                visible: r.width > 0 && r.height > 0,
                rect: {w: Math.round(r.width), h: Math.round(r.height)},
                display: cs.display,
                visibility: cs.visibility,
                opacity: cs.opacity,
                text: (b.textContent ?? '').trim().slice(0, 30),
            };
        }"""
    )


def camoufox_build(item_ids: list[int]) -> tuple[dict, list]:
    """Camoufox: iteruje po itemach, na pierwszym z WIDOCZNYM przyciskiem
    'Kup teraz' (visible=True po hydratacji — sekcja 31.4) klika i przechwytuje build.
    Zwraca (build_json, cookies)."""
    captured = {}
    cookies = []
    all_reqs = []

    # Profil po hard-stopie (kill/StopCommand) zostawia parent.lock -> Firefox nie startuje.
    # Profil nalezy wylacznie do tego projektu (procesy ALLEGRO uzywaja wlasnych profili).
    for lock in ("parent.lock", "lock", "lockfile"):
        p = PROFILE_DIR / lock
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    def on_response(resp):
        if resp.url.endswith("/api/v2/purchases/checkout/build"):
            # lap budowa bez wzgledu na status (diagnostyka: 403 tez jest informacja)
            captured["build_status"] = resp.status
            captured["build_url"] = resp.url
            if resp.status == 200:
                try:
                    captured["build"] = resp.json()
                except Exception:
                    pass

    def on_request(req):
        u = req.url
        if any(x in u for x in ("checkout", "conversations", "purchases")):
            all_reqs.append({"method": req.method, "url": u})

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
        i_know_what_im_doing=True,
    ) as ctx:
        page = ctx.new_page()
        page.on("response", on_response)
        page.on("request", on_request)

        for item_id in item_ids:
            url = f"https://www.vinted.pl/items/{item_id}"
            _log("goto_item", url=url, item_id=item_id)
            try:
                page.goto(url, wait_until="commit", timeout=45000)
            except Exception as e:
                _log("goto_error", item_id=item_id, err=str(e)[:100])
                continue
            time.sleep(2.5)

            # Sprawdzenie logowania (diagnostyka: zalogowany profil?)
            try:
                login_check = page.evaluate(
                    """async () => {
                        try {
                            const r = await fetch('/api/v2/users/current', {headers: {'Accept': 'application/json'}});
                            const d = await r.json();
                            return {status: r.status, login: d.user?.login || d.login || null};
                        } catch (e) { return {status: 'err', login: null}; }
                    }"""
                )
                _log("login_check", item_id=item_id, **login_check)
            except Exception as e:
                _log("login_check_err", item_id=item_id, err=str(e)[:80])

            # OneTrust dismiss
            try:
                page.evaluate(
                    """() => {
                        const btns = document.querySelectorAll('#onetrust-accept-btn-handler, .ot-sdk-container button');
                        for (const b of btns) {
                            const t = (b.textContent ?? '').toLowerCase();
                            if (/akcept|zgadzam|accept/.test(t)) { b.click(); return true; }
                        }
                        return false;
                    }"""
                )
                time.sleep(0.5)
            except Exception:
                pass

            btn_state = _btn_state(page)
            _log("button_state", item_id=item_id, **btn_state)
            if not btn_state.get("found") or not btn_state.get("visible") or btn_state.get("disabled"):
                _log("item_skip", item_id=item_id, reason="przycisk nieaktywny")
                continue

            # trusted click (sekcja 3.15: evaluate click = natywny klik wyzwala handler
            # Reacta z interceptorem Incognia; page.click moze nie trafiac przez overlay)
            for attempt in range(1, 3):
                _log("click_kup_teraz", item_id=item_id, attempt=attempt)
                if "build" in captured:
                    break
                try:
                    clicked = page.evaluate(
                        """() => {
                            const b = document.querySelector('button[data-testid="item-buy-button"]');
                            if (!b) return false;
                            b.click();
                            return true;
                        }"""
                    )
                    _log("evaluate_click", item_id=item_id, clicked=clicked)
                except Exception as e:
                    _log("click_error", item_id=item_id, attempt=attempt, err=str(e)[:120])
                for _ in range(80):
                    if "build" in captured:
                        break
                    time.sleep(0.1)
                if "build" not in captured:
                    time.sleep(1.5)
            if "build" in captured:
                break
            _log("item_build_fail", item_id=item_id)
            time.sleep(1.0)

        cookies = ctx.cookies()

    _log("build_captured", status=captured.get("build_status"),
         has_build="build" in captured, url=captured.get("build_url"))
    if all_reqs:
        _log("requesty_checkout", n=len(all_reqs),
             reqs=[f"{r['method']} {r['url'][:90]}" for r in all_reqs[-8:]])
    if captured.get("build"):
        (BASE_DIR / "wynik_hybrid_e2e_build_raw.json").write_text(
            json.dumps(captured["build"], ensure_ascii=False, indent=2), encoding="utf-8")
    return captured.get("build"), cookies


def curl_checkout_and_payment(build: dict, cookies: list, token: str) -> dict:
    """curl_cffi: PUT payment_method -> PUT pickup_details -> POST payment."""
    s = _session_from(cookies)
    H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

    checkout = build.get("checkout", {})
    checkout_id = checkout.get("id")
    if not checkout_id:
        return {"error": "brak checkout_id w buildzie"}

    comps = checkout.get("components", {})
    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    referer = f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"

    # a. PUT payment_method
    r = s.put(put_url, json={"components": {
        "additional_service": {},
        "payment_method": {"card_id": None, "pay_in_method_id": "12"},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": {},
    }}, headers=H, impersonate=IMPERSONATE, timeout=30, allow_redirects=False)
    ch_pm = _find_checksum(r.json()) if r.status_code == 200 else None
    _log("put_payment_method", http=r.status_code, checksum=bool(ch_pm))
    if r.status_code != 200:
        return {"error": "PUT payment_method", "http": r.status_code, "body": r.text[:300]}

    # b. GET pickup points
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    addr = comps.get("shipping_address", {}).get("address", {})
    coords = addr.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    # rate_uuid z builda (fallback, gdy pickup points nie zawiera pasujacego punktu)
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    build_rate_uuid = pd_inner.get("selected_rate_uuid")

    details = {}
    if so_id and lat and lon:
        pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
                   f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
        rp = s.get(pts_url, headers=H, impersonate=IMPERSONATE, timeout=30)
        pp = rp.json() if rp.status_code == 200 else {}
        spoints = (pp or {}).get("shipping_points") or []
        sug = (pp or {}).get("suggested_shipping_point_code")
        point = None
        for cand in spoints:
            sp = cand.get("point", {})
            if sug and sp.get("code") == sug:
                point = sp
                break
        if point is None and build_rate_uuid:
            for cand in spoints:
                sp = cand.get("point", {})
                if sp.get("rate_uuid") == build_rate_uuid:
                    point = sp
                    break
        if point is None and spoints:
            point = spoints[0].get("point", {})
        # rate_uuid NIE jest w poincie — jest w selected_rate_uuid builda.
        if build_rate_uuid:
            details["rate_uuid"] = build_rate_uuid
        if point:
            if point.get("code"):
                details["point_code"] = point["code"]
            if point.get("uuid"):
                details["point_uuid"] = point["uuid"]
        _log("pickup_points", http=rp.status_code, n=len(spoints), sug=sug,
             so_id=so_id, lat=lat, lon=lon, build_rate_uuid=build_rate_uuid,
             body=rp.text[:300] if rp.status_code != 200 else None)
    else:
        _log("pickup_points", skipped="brak so_id/coords", so_id=so_id, lat=lat, lon=lon)

    # c. PUT pickup_details
    r2 = s.put(put_url, json={"components": {
        "additional_service": {},
        "payment_method": {},
        "shipping_address": {},
        "shipping_pickup_options": {},
        "shipping_pickup_details": details,
    }}, headers=H, impersonate=IMPERSONATE, timeout=30, allow_redirects=False)
    ch_pickup = _find_checksum(r2.json()) if r2.status_code == 200 else None
    _log("put_pickup_details", http=r2.status_code, checksum=bool(ch_pickup), details=bool(details))

    # FINAL checksum: z pickup_details, potem payment_method, potem build
    final_checksum = ch_pickup or ch_pm or _find_checksum(build)
    if not final_checksum:
        return {"error": "brak checksum", "http": r2.status_code}

    # d. POST payment
    fp = _load_fingerprint()
    r3 = s.post(
        f"{put_url}/payment",
        json={
            "checksum": final_checksum,
            "payment_options": {"browser_info": {
                "language": "pl",
                "color_depth": 24,
                "java_enabled": False,
                "screen_height": fp.get("screen_height", 1080),
                "screen_width": fp.get("screen_width", 1920),
                "timezone_offset": -120,
            }},
        },
        headers={**H, "referer": referer, "x-incognia-request-token": token},
        impersonate=IMPERSONATE, timeout=30, allow_redirects=False,
    )
    pj = r3.json() if r3.status_code == 200 else {}
    payment = pj.get("payment", {}) if isinstance(pj, dict) else {}
    nav = (pj.get("action", {}) or {}).get("parameters", {}) if isinstance(pj, dict) else {}
    redirect_url = nav.get("url", "")
    _log("payment", http=r3.status_code, status=payment.get("status"), redirect=bool(redirect_url))

    return {
        "checkout_id": checkout_id,
        "http": r3.status_code,
        "payment_status": payment.get("status"),
        "redirect_url": redirect_url[:200],
        "success": r3.status_code == 200 and payment.get("status") == "pending" and bool(redirect_url),
        "raw": r3.text[:400] if r3.status_code != 200 else None,
    }


def _candidate_items(limit: int = 10) -> list[int]:
    """curl_cffi: pobiera świeże itemy z katalogu (nie sprzedane, nie zablokowane)."""
    from curl_cffi import requests as req
    s = cr.Session()
    for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({"accept": "application/json,text/plain,*/*,image/webp",
                      "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
                      "content-type": "application/json", "locale": "pl-PL",
                      "origin": "https://www.vinted.pl", "referer": "https://www.vinted.pl/"})
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?catalog_ids%5B%5D=44&price_to=100&order=newest_first&page=1&per_page=40&currency=PLN",
              headers={"x-csrf-token": CSRF, "x-anon-id": ANON},
              impersonate=IMPERSONATE, timeout=30)
    ids = []
    for it in r.json().get("items", []):
        if it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        ids.append(it["id"])
        if len(ids) >= limit:
            break
    return ids


def main():
    import sys
    if len(sys.argv) > 1:
        item_ids = [int(sys.argv[1])]
    else:
        item_ids = _candidate_items(limit=10)
    _log("candidate_items", n=len(item_ids), ids=item_ids[:5])

    # token Incognia (AES-GCM z sdkInstanceId) — generowalny w Node bez przegladarki
    _log("get_sdk_instance_id")
    from curl_cffi import requests as req
    rc = req.get("https://api.vinted.pl/j3r4zw/v1/config", impersonate=IMPERSONATE, timeout=30)
    sdk_id = (rc.json() or {}).get("sdk_instance_id")
    token = _gen_token(sdk_id) if sdk_id else ""
    _log("token_generated", sdk=bool(sdk_id), token_len=len(token))

    # 1. Camoufox build (iteracja po itemach z weryfikacja visible — sekcja 31.4)
    build, ctx_cookies = camoufox_build(item_ids)
    if not build:
        results["result"] = {"error": "build nie przechwycony (brak itemu z widocznym przyciskiem)"}
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\nNIE przechwycono builda — zapisano wynik.", flush=True)
        return

    # merge: swiezy datadome z klikniecia + cookies pokrywajace api.vinted.pl
    base_cookies = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    cookies = _merge_cookies(base_cookies, ctx_cookies)

    # 2. curl_cffi PUT + payment
    result = curl_checkout_and_payment(build, cookies, token)
    results["result"] = result

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT}", flush=True)
    print(f"SUKCES: {result.get('success')} (http={result.get('http')}, "
          f"payment={result.get('payment_status')})", flush=True)


if __name__ == "__main__":
    main()