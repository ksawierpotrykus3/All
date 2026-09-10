# coding: utf-8
"""Hybryda: Camoufox TYLKO do checkout/build (trusted click), curl_cffi do reszty.

Flow:
1. Camoufox: otworz strone itemu, kliknij 'Kup teraz' (trusted click) -> wyzwala checkout/build
2. Przechwyc response build (purchase_id, checkout_id, components)
3. curl_cffi: PUT payment_method -> PUT pickup_details -> POST payment
4. Camoufox: (opcjonalnie) screenshot bramki

Cel: minimalna ilosc Camoufox (tylko tam, gdzie konieczna), maksymalna predkosc curl_cffi.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

results = {"steps": [], "elapsed": {}}
T0 = time.monotonic()


def now_ms() -> float:
    return round((time.monotonic() - T0) * 1000, 1)


def step(name, **extra):
    e = {"step": name, "elapsed_ms": now_ms(), "wall_utc": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"}
    e.update(extra)
    results["steps"].append(e)
    print(f"[{e['elapsed_ms']:>9.1f} ms] {name}", flush=True)


def find_checksum(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                return v
            r = find_checksum(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_checksum(v)
            if r:
                return r
    return None


def main():
    # --- 1) Camoufox: strona itemu + trusted click ---
    step("camoufox_start")
    captured = {}

    def on_response(response):
        if "/purchases/checkout/build" in response.url:
            try:
                captured["build"] = response.json()
                captured["build_status"] = response.status
                captured["build_url"] = response.url
            except Exception:
                captured["build_text"] = response.text()[:500]

    with Camoufox(persistent_context=True, headless=True,
                  user_data_dir=str(PROFILE_DIR), os="windows",
                  fingerprint_preset=True, humanize=True,
                  block_webgl=True,
                  i_know_what_im_doing=True) as ctx:
        page = ctx.new_page()
        page.on("response", on_response)

        # Profil persistent_context sam utrzymuje sesję — NIE importować cookies z pliku
        # (stare cookies z pliku nadpisałyby świeże z profilu)

        # Sprawdź czy zalogowany (przez API)
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        login_check = page.evaluate("""async () => {
            const r = await fetch('/api/v2/users/current', {
                headers: {'Accept': 'application/json'}
            });
            const data = await r.json();
            return {status: r.status, login: data.user?.login || data.login, id: data.user?.id || data.id};
        }""")
        step("sprawdzenie_logowania", status=login_check.get("status"), login=login_check.get("login"))
        if not login_check.get("login"):
            print("❌ Użytkownik nie jest zalogowany nawet po imporcie cookies.")
            print("Wymagane ręczne zalogowanie przez harvest_cookies_firefox.py")
            return

        # swiezy item (przez curl_cffi - szybciej)
        s_temp = cr.Session()
        cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
        for c in cookies:
            try:
                s_temp.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
            except Exception:
                pass
        s_temp.headers.update({
            "accept": "application/json,text/plain,*/*,image/webp",
            "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
            "content-type": "application/json",
            "locale": "pl-PL",
            "origin": "https://www.vinted.pl",
            "referer": "https://www.vinted.pl/",
        })
        H_temp = {"x-csrf-token": CSRF, "x-anon-id": ANON}
        r = s_temp.get("https://www.vinted.pl/api/v2/catalog/items"
                       "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=3&currency=PLN",
                       headers=H_temp, impersonate=BrowserType.chrome146, timeout=30)
        it = r.json().get("items", [])[0]
        item_id, seller_id = it["id"], it["user"]["id"]
        step("item", id=item_id, seller=seller_id, title=it.get("title", "")[:40])

        # strona itemu
        page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="domcontentloaded", timeout=30000)
        step("strona_zaladowana", url=page.url)
        try:
            page.wait_for_selector('button[data-testid="item-buy-button"]', timeout=15000)
            step("strona_itemu")
        except Exception as e:
            step("strona_itemu_timeout", error=str(e)[:100], url=page.url)
            print(f"Nie znaleziono przycisku 'Kup teraz': {e}")
            print(f"URL: {page.url}")
            # sprawdz czy item ma przycisk
            btn = page.query_selector('button[data-testid="item-buy-button"]')
            if btn:
                print("Przycisk istnieje, ale nie jest widoczny")
            else:
                print("Przycisk NIE istnieje - item moze byc juz sprzedany lub niedostepny")
            return

        # trusted click - sprawdz wszystkie requesty po kliknieciu
        btn = page.query_selector('button[data-testid="item-buy-button"]')
        if btn:
            is_disabled = btn.get_attribute("disabled")
            is_visible = btn.is_visible()
            step("przycisk_stan", disabled=is_disabled, visible=is_visible)
            print(f"Przycisk: disabled={is_disabled}, visible={is_visible}")

        all_requests = []
        def on_request(request):
            all_requests.append({"url": request.url, "method": request.method})
        page.on("request", on_request)

        page.click('button[data-testid="item-buy-button"]')
        step("klik_kup_teraz")

        # czekaj na build response (bardzo dlugo - moze byc opozniony)
        for i in range(600):
            if "build" in captured:
                break
            time.sleep(0.1)
        else:
            step("build_timeout")
            print(f"Wszystkie requesty po kliknieciu: {len(all_requests)}")
            build_reqs = [r for r in all_requests if "checkout" in r["url"] or "purchases" in r["url"]]
            print(f"Requesty checkout/purchases: {len(build_reqs)}")
            for req in build_reqs:
                print(f"  {req['method']} {req['url'][:100]}")
            return

        build_status = captured.get("build_status")
        checkout_id = captured.get("build", {}).get("checkout", {}).get("id")
        step("build_przechwycony", http=build_status, checkout_id=checkout_id)

        if build_status != 200:
            print(f"BUILD FAIL: {build_status}")
            return

        # cookies z przegladarki
        cookies = ctx.cookies()
        step("cookies_z_przegladarki", n=len(cookies))

    # --- 2) curl_cffi: reszta flow ---
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
        "referer": "https://www.vinted.pl/",
        "priority": "u=3",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    })
    H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

    build = captured["build"]
    checkout_id = build.get("checkout", {}).get("id")
    ch = find_checksum(build)
    comps = build.get("checkout", {}).get("components", {})
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    address = comps.get("shipping_address", {}).get("address", {})
    coords = address.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")

    # PUT payment_method
    r = s.put(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout",
              json={"components": {
                  "additional_service": {},
                  "payment_method": {"card_id": None, "pay_in_method_id": "12"},
                  "shipping_address": {},
                  "shipping_pickup_options": {},
                  "shipping_pickup_details": {},
              }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    step("put_payment_method", http=r.status_code)
    if r.status_code != 200:
        print(f"PUT payment_method FAIL: {r.status_code}")
        return

    # GET pickup points
    r = s.get(f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
              f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}",
              headers=H, impersonate=BrowserType.chrome146, timeout=30)
    pp = r.json()
    spoints = (pp or {}).get("shipping_points") or []
    sug = (pp or {}).get("suggested_shipping_point_code")
    point = None
    for cand in spoints:
        sp = cand.get("point", {})
        if sug and sp.get("code") == sug:
            point = sp
            break
    if point is None and spoints:
        point = spoints[0].get("point", {})
    step("pickup_points", n=len(spoints), point=point.get("code") if point else None)

    # PUT pickup_details
    details = {"rate_uuid": rate_uuid}
    if point:
        if point.get("code"):
            details["point_code"] = point["code"]
        if point.get("uuid"):
            details["point_uuid"] = point["uuid"]
        if point.get("rate_uuid"):
            details["rate_uuid"] = point["rate_uuid"]

    r = s.put(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout",
              json={"components": {
                  "additional_service": {},
                  "payment_method": {},
                  "shipping_address": {},
                  "shipping_pickup_options": {},
                  "shipping_pickup_details": details,
              }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    step("put_pickup_details", http=r.status_code)
    if r.status_code != 200:
        print(f"PUT pickup_details FAIL: {r.status_code}")
        return

    # POST payment
    r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
               json={"checksum": ch, "payment_options": {"browser_info": {
                   "language": "pl", "color_depth": 24, "java_enabled": False,
                   "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
               headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    pay_status = (r.json().get("payment") or {}).get("status")
    step("payment", http=r.status_code, status=pay_status)

    # zapisz wynik
    (BASE_DIR / "wynik_hybryda.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    total = now_ms()
    print(f"\n=== WYNIK ===")
    print(f"Czas calkowity: {total} ms")
    print(f"Camoufox: {results['steps'][3]['elapsed_ms'] - results['steps'][0]['elapsed_ms']} ms")
    print(f"curl_cffi: {total - results['steps'][3]['elapsed_ms']} ms")
    print(f"Payment: {pay_status}")


if __name__ == "__main__":
    main()
