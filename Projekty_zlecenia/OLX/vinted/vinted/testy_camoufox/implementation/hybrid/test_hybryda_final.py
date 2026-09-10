# coding: utf-8
"""Hybryda: Camoufox robi strone itemu + klik 'Kup teraz' (rozwiazuje DataDome),
potem curl_cffi przejmuje od checkout/build dalej.

Klucz: po kliknieciu 'Kup teraz' w przegladarce, Vinted sam wysyla requesty
checkout/build + PUT payment_method + PUT pickup_details + POST payment.
Przechwytujemy je i replikujemy w curl_cffi (ze swiezymi cookies z przegladarki).
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

results = {"steps": [], "captured": {}}


def _headers(cookies, extra=None):
    h = {
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
        "x-csrf-token": CSRF,
        "x-anon-id": ANON,
    }
    if extra:
        h.update(extra)
    return h


def _session(cookies):
    s = cr.Session()
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update(_headers(cookies))
    return s


# --- 1) Camoufox: strona itemu + klik 'Kup teraz' ---
with Camoufox(persistent_context=True, headless=True,
              user_data_dir=str(PROFILE_DIR), os="windows",
              fingerprint_preset=True, humanize=True) as ctx:
    page = ctx.new_page()
    captured = {}

    def on_response(resp):
        if "/api/v2/purchases/checkout/build" in resp.url and resp.status == 200:
            try:
                captured["build"] = resp.json()
            except Exception:
                pass
        if "/api/v2/purchases/" in resp.url and "/checkout/payment" in resp.url:
            captured["payment_status"] = resp.status
            try:
                captured["payment"] = resp.json()
            except Exception:
                pass

    page.on("response", on_response)

    # wybierz swiezy item
    page.goto("https://www.vinted.pl/catalog/44-kobiety?order=newest_first&price_to=50",
              wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # znajdz pierwszy dostepny item
    item_url = page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href^="/items/"]');
            for (const a of links) {
                const href = a.getAttribute('href');
                if (href && !href.includes('sold')) return 'https://www.vinted.pl' + href;
            }
            return null;
        }
    """)
    if not item_url:
        print("BRAK itemu - abort")
        raise SystemExit(1)
    print(f"item_url={item_url}")

    page.goto(item_url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # klik 'Kup teraz' (rozwiazuje DataDome)
    try:
        page.click('button[data-testid="item-buy-button"]', timeout=15000)
        print("Klik 'Kup teraz' OK")
    except Exception as e:
        print(f"Klik 'Kup teraz' BLAD: {e}")

    # czekaj na przechwycenie build (max 10s)
    for _ in range(100):
        if "build" in captured:
            break
        time.sleep(0.1)

    cookies = ctx.cookies()
    results["camoufox_cookies"] = len(cookies)
    results["captured"] = {k: (v if isinstance(v, int) else str(v)[:200])
                           for k, v in captured.items()}
    print(f"Przechwycono: {list(captured.keys())}")

# --- 2) curl_cffi przejmuje ---
s = _session(cookies)
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

if "build" in captured:
    build = captured["build"]
    checkout_id = build.get("checkout", {}).get("id")
    txn_id = build.get("checkout", {}).get("transaction_id")
    print(f"build z przegladarki: checkout_id={checkout_id} txn={txn_id}")

    # PUT payment_method
    r = s.put(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout",
              json={"components": {
                  "additional_service": {},
                  "payment_method": {"card_id": None, "pay_in_method_id": "12"},
                  "shipping_address": {},
                  "shipping_pickup_options": {},
                  "shipping_pickup_details": {},
              }}, headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    print(f"PUT payment_method: {r.status_code}")
    results["put_pm"] = r.status_code

    # PUT pickup_details (z danych z build)
    comps = build.get("checkout", {}).get("components", {})
    pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = comps.get("shipping_address", {}).get("shipping_order_id")
    addr = comps.get("shipping_address", {}).get("address", {})
    coords = addr.get("coordinates") or {}

    if so_id and coords:
        pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
                   f"/nearby_pickup_points?country_code=PL&latitude={coords.get('latitude')}&longitude={coords.get('longitude')}")
        r = s.get(pts_url, headers=H, impersonate=BrowserType.chrome146, timeout=30)
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
        print(f"PUT pickup_details: {r.status_code}")
        results["put_pickup"] = r.status_code

        # POST payment
        ch = None
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
        ch = find_checksum(build)

        r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
                   json={"checksum": ch, "payment_options": {"browser_info": {
                       "language": "pl", "color_depth": 24, "java_enabled": False,
                       "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
                   headers=H, impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
        print(f"POST payment: {r.status_code}")
        results["payment"] = {"http": r.status_code, "body": r.text[:300]}
else:
    print("NIE przechwycono build - DataDome nie zostal rozwiazany")
    results["error"] = "no_build_captured"

(BASE_DIR / "wynik_hybryda_final.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("Zapisano: wynik_hybryda_final.json")
