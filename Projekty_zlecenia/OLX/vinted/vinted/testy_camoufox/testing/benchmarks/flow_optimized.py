# coding: utf-8
"""flow_optimized.py — zoptymalizowany flow zakupowy BEZ przeglądarki (curl_cffi + Node.js).

Jeden spójny fingerprint TLS: Firefox 135 = wbudowany profil `firefox135` curl_cffi.
Zweryfikowany 1:1 z Camoufox 135 (profil_firefox_135) na tls.peet.ws:
  - ja3_hash    6f7889b9fb1a62a9577e685c1fcfa919
  - ja4         t13d1717h2_5b57614c22b0_3cbfd9057e0d
  - peet_hash   89d89662b21018947a9a46658c4f5ede
  - cert_comp   [zlib, brotli, zstd] (3 algorytmy — komplet)
Cookie datadome wyharvestowane przez Camoufox 135 jest spójne z tym stackiem.
Żaden krok nie wymaga selektora CSS ani Camoufox w runtime.

Wektory efektywności (UDOWODNIONE w bench_curl_gateway_opt.py):
  - /messaging/main/inquiries (nowy backend) zamiast /api/v2/conversations (unika 429 code 106)
  - równoległość PUT payment_method | GET nearby_pickup_points (ThreadPoolExecutor)
  - pojedynczy PUT pickup_details (nie wiele osobnych PUT-ów)

Mierzy payment_reached_ms (przejście do płatności) od startu.
"""
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # testy_camoufox
COOKIES_PATH = BASE_DIR / "analysis" / "cookies_profil.json"
NODE_SCRIPT_PATH = BASE_DIR / ".bin" / "archive" / "generate_incognia_token.js"
OUT = BASE_DIR / "wynik_flow_optimized.json"
PROFILE_DIR = BASE_DIR / "profil_firefox_135"

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# Wbudowany profil Firefox 135 w curl_cffi — pełny match 1:1 z Camoufox 135
# (ja3_hash / ja4 / peet_hash / cert_compression [zlib,brotli,zstd]).
IMPERSONATE = "firefox135"

# Metoda płatności (źródło: odpowiedź checkout/build -> components.payment_method.pay_in_methods):
#   1 = CREDIT_CARD (Karta płatnicza), 12 = P24 (Przelewy24), 17 = GOOGLE_PAY, 18 = BLIK_DIRECT.
PAY_IN_METHOD = "1"  # karta zamiast Przelewy24 (12 -> 400 code 114)

SCREEN_W, SCREEN_H = 1920, 1080  # zgodne z udanym runem do bramki


def wall():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


def _load_cookies() -> list:
    return json.loads(COOKIES_PATH.read_text(encoding="utf-8"))


def _create_session() -> cr.Session:
    s = cr.Session(impersonate=IMPERSONATE)
    for c in _load_cookies():
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
    return s


def _headers(extra=None):
    h = {"x-csrf-token": CSRF, "x-anon-id": ANON}
    if extra:
        h.update(extra)
    return h


def _find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(_find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(_find_checksum(v))
    return hits


def _get_sdk_instance_id():
    r = cr.get("https://api.vinted.pl/j3r4zw/v1/config", timeout=30)
    return (r.json() or {}).get("sdk_instance_id")


def _generate_incognia_token(sdk_instance_id: str) -> str:
    res = subprocess.run(
        ["node", str(NODE_SCRIPT_PATH), sdk_instance_id],
        capture_output=True, text=True, timeout=30,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Node.js error: {res.stderr}")
    return res.stdout.strip()


def _render_card_screen(checkout_id: str, results: dict):
    """Renderuje stronę checkout z wybraną kartą, wypełnia losowe dane testowe
    i robi screen z wypalonym timestampem ms (dowód wizualny)."""
    import random

    from PIL import Image, ImageDraw, ImageFont
    from camoufox import Camoufox

    card = {
        "encryptedCardNumber": "4111111111111111",
        "encryptedExpiryDate": f"{random.randint(1, 12):02d}/{random.randint(25, 30)}",
        "encryptedSecurityCode": f"{random.randint(100, 999)}",
        "encryptedCardHolderName": "JAN KOWALSKI",
    }
    checkout_url = f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"
    shot_ts = wall()
    shot_path = BASE_DIR / f"flow_optimized_card_{int(time.time() * 1000)}.png"

    try:
        with Camoufox(
            persistent_context=True, headless=True,
            user_data_dir=str(PROFILE_DIR), os="windows",
            fingerprint_preset=True, humanize=True, block_webgl=True,
        ) as ctx:
            page = ctx.new_page()
            page.goto(checkout_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # pola karty Adyen żyją w iframe'ach (securedFields); holder name w głównym DOM
            for frame in page.frames:
                for ft, val in card.items():
                    try:
                        loc = frame.locator(f"[data-fieldtype='{ft}']")
                        if loc.count():
                            loc.first.fill(val)
                    except Exception:
                        pass
            for sel in ("input[name='cardholderName']", "input[autocomplete='cc-name']"):
                try:
                    page.fill(sel, card["encryptedCardHolderName"])
                    break
                except Exception:
                    continue

            page.screenshot(path=str(shot_path), full_page=False)
        print(f"screenshot karty zapisany: {shot_path}", flush=True)
    except Exception as e:
        results["card_screenshot_error"] = str(e)
        print(f"BLAD screena karty: {e}", flush=True)
        return

    try:
        img = Image.open(shot_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        timings = results.get("timings", {})
        lines = [
            f"flow_optimized -> KARTA (id=1) | T0={results.get('ts', '')} | shot={shot_ts}",
            f"karta nr={card['encryptedCardNumber']} exp={card['encryptedExpiryDate']} "
            f"cvc={card['encryptedSecurityCode']}",
        ]
        pairs = [(k, v) for k, v in timings.items() if isinstance(v, int)]
        pairs.sort(key=lambda kv: kv[1])
        for i in range(0, len(pairs), 4):
            chunk = " | ".join(f"{k}={v} ms" for k, v in pairs[i:i + 4])
            lines.append(chunk)

        # Zawijaj linie do szerokosci obrazu; zmniejsz czcionke az sie zmieszcza.
        max_w = img.width - 24
        wrapped = []
        for line in lines:
            while draw.textlength(line, font=font) > max_w and len(line) > 1:
                # zawin na ostatnim separatorze przed przekroczeniem
                cut = len(line)
                while cut > 0 and draw.textlength(line[:cut], font=font) > max_w:
                    cut -= 1
                sep = line.rfind(" | ", 0, cut)
                if sep <= 0:
                    sep = cut
                wrapped.append(line[:sep])
                line = line[sep:].lstrip(" |")
            wrapped.append(line)

        line_h = font.size + 6 if hasattr(font, "size") else 26
        bar_h = 16 + len(wrapped) * line_h
        draw.rectangle([0, img.height - bar_h, img.width, img.height], fill=(0, 0, 0))
        for i, line in enumerate(wrapped):
            draw.text((12, img.height - bar_h + 8 + i * line_h), line, fill=(255, 255, 0), font=font)

        marked = BASE_DIR / f"flow_optimized_card_dowod_{int(time.time() * 1000)}.png"
        img.save(marked)
        results["card_screenshot"] = str(marked)
        print(f"dowod karty: {marked}", flush=True)
    except Exception as e:
        results["card_mark_error"] = str(e)
        print(f"BLAD znakowania: {e}", flush=True)


def main():
    T0 = time.monotonic()
    results = {"ts": wall(), "timings": {}, "tls": "firefox135"}

    s = _create_session()
    token = _generate_incognia_token(_get_sdk_instance_id())
    results["incognia_token_length"] = len(token)

    # --- 0) health ---
    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=_headers(), timeout=30)
    if r.status_code != 200:
        results["error"] = f"health {r.status_code}"
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    print("health: 200 (firefox135)", flush=True)

    # --- 1) catalog ---
    t0 = time.monotonic()
    r = s.get(
        "https://www.vinted.pl/api/v2/catalog/items"
        "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=10&currency=PLN",
        headers=_headers(), timeout=30)
    results["timings"]["catalog"] = round((time.monotonic() - t0) * 1000)
    items = r.json().get("items") if r.status_code == 200 else []
    items = [it for it in items if it.get("is_visible") is not False and it.get("user")]
    results["catalog_status"] = r.status_code
    print(f"catalog: {results['timings']['catalog']} ms status={r.status_code} ({len(items)} kupowalnych)", flush=True)
    if not items:
        results["error"] = "brak itemu"
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    item = items[0]
    item_id, seller_id = item["id"], item["user"]["id"]
    results["item_id"] = item_id
    print(f"[OK] item {item_id} seller={seller_id}", flush=True)

    # --- 2) inquiries (nowy backend, unika 429 na /conversations) ---
    t0 = time.monotonic()
    r = s.post("https://api.vinted.pl/messaging/main/inquiries",
               json={"item_ids": [str(item_id)], "receiver_id": str(seller_id)},
               headers=_headers(), timeout=30, allow_redirects=False)
    results["timings"]["inquiries"] = round((time.monotonic() - t0) * 1000)
    if r.status_code == 200:
        txn_id = r.json().get("transaction_id")
        results["txn_id"] = txn_id
        print(f"inquiries: {results['timings']['inquiries']} ms txn={txn_id}", flush=True)
    else:
        results["inquiries_error"] = {"status": r.status_code, "body": r.text[:120]}
        print(f"inquiries: {results['timings']['inquiries']} ms status={r.status_code} -> {r.text[:80]}", flush=True)
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    # --- 3) build ---
    t0 = time.monotonic()
    r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
               json={"purchase_items": [{"id": int(txn_id), "type": "transaction"}]},
               headers=_headers({
                   "referer": f"https://www.vinted.pl/items/{item_id}",
                   "x-incognia-request-token": token}),
               timeout=30, allow_redirects=False)
    results["timings"]["build"] = round((time.monotonic() - t0) * 1000)
    results["build"] = {"status": r.status_code}
    print(f"build: {results['timings']['build']} ms status={r.status_code}", flush=True)
    if r.status_code != 200:
        results["build"]["body"] = r.text[:200]
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    bj = r.json()
    checkout_id = (bj.get("checkout") or {}).get("id")
    ch = _find_checksum(bj)
    comps = (bj.get("checkout") or {}).get("components", {})
    pd_inner = (comps.get("shipping_pickup_details") or {}).get("pickup_details", {})
    rate_uuid = pd_inner.get("selected_rate_uuid")
    so_id = (comps.get("shipping_address") or {}).get("shipping_order_id")
    addr = (comps.get("shipping_address") or {}).get("address", {})
    coords = addr.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    results["checkout_id"] = checkout_id
    print(f"  checkout={checkout_id}", flush=True)

    put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
    pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
               f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}") if so_id else None

    # --- 4) RÓWNOLEGLE: PUT payment_method | GET pickup_points ---
    def put_payment_method():
        r = s.put(put_url, json={"components": {
            "additional_service": {},
            "payment_method": {"card_id": None, "pay_in_method_id": PAY_IN_METHOD},
            "shipping_address": {},
            "shipping_pickup_options": {"pickup_type": 1},
            "shipping_pickup_details": {},
        }}, headers=_headers({"referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"}),
            timeout=30, allow_redirects=False)
        try:
            return r.status_code, _find_checksum(r.json())
        except Exception:
            return r.status_code, []

    def get_pickup():
        if not pts_url:
            return "skip", None
        r = s.get(pts_url, headers=_headers(), timeout=30)
        try:
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
            return r.status_code, point
        except Exception:
            return r.status_code, None

    t0 = time.monotonic()
    if pts_url:
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_put = ex.submit(put_payment_method)
            f_pts = ex.submit(get_pickup)
            put_status, ch2 = f_put.result()
            pts_status, point = f_pts.result()
    else:
        put_status, ch2 = put_payment_method()
        pts_status, point = "skip", None
    results["timings"]["put_payment_method_parallel"] = round((time.monotonic() - t0) * 1000)
    print(f"parallel [put payment_method | pickup_points]: "
          f"{results['timings']['put_payment_method_parallel']} ms put={put_status} pickup={pts_status} point={point and point.get('code')}", flush=True)

    # --- 5) PUT pickup_details ---
    details = {}
    if rate_uuid:
        details["rate_uuid"] = rate_uuid
    if point:
        if point.get("code"):
            details["point_code"] = point["code"]
        if point.get("uuid"):
            details["point_uuid"] = point["uuid"]
    ch3 = []
    if details:
        t0 = time.monotonic()
        r = s.put(put_url, json={"components": {
            "additional_service": {},
            "payment_method": {},
            "shipping_address": {},
            "shipping_pickup_options": {},
            "shipping_pickup_details": details,
        }}, headers=_headers({"referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"}),
            timeout=30, allow_redirects=False)
        results["timings"]["put_pickup_details"] = round((time.monotonic() - t0) * 1000)
        ch3 = _find_checksum(r.json()) if r.status_code == 200 else []
        print(f"put pickup_details: {results['timings']['put_pickup_details']} ms status={r.status_code} ch3={bool(ch3)}", flush=True)

    # --- 6) payment ---
    checksum = (ch3 or ch2 or ch)[0] if (ch3 or ch2 or ch) else ""
    payment_reached_ms = int((time.monotonic() - T0) * 1000)
    t0 = time.monotonic()
    r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
               json={"checksum": checksum, "payment_options": {"browser_info": {
                   "language": "pl", "color_depth": 24, "java_enabled": False,
                   "screen_height": SCREEN_H, "screen_width": SCREEN_W, "timezone_offset": -120}}},
               headers=_headers({
                   "referer": f"https://www.vinted.pl/checkout?purchase_id={checkout_id}",
                   "x-incognia-request-token": token}),
               timeout=30, allow_redirects=False)
    results["timings"]["payment"] = round((time.monotonic() - t0) * 1000)
    results["payment"] = {"status": r.status_code}
    results["payment_reached_ms"] = payment_reached_ms
    # Czas dotarcia do bramki BEZ screenshotu (screenshot dodawany pozniej nie wchodzi
    # do czasu zakupu). To jest miarodajna metryka "czas do bramki".
    results["czas_do_bramki_ms"] = payment_reached_ms + results["timings"]["payment"]
    print(f"payment: {results['timings']['payment']} ms status={r.status_code} "
          f"(dotarcie {payment_reached_ms} ms od startu)", flush=True)

    if r.status_code == 200:
        pj = r.json()
        ps = ((pj.get("payment") or {}).get("status"))
        rd = (((pj.get("action") or {}).get("parameters") or {}).get("url") or "")
        results["payment"]["payment_status"] = ps
        results["payment"]["redirect"] = rd[:100]
        results["success"] = ps == "pending" and bool(rd)
        print(f"  -> {ps} {rd[:80]}", flush=True)
    else:
        # payment != 200 = NIEPOWODZENIE — nie liczyc do rankingu czasowego.
        results["success"] = False
        results["payment"]["body"] = r.text[:200]
        try:
            results["payment"]["error_code"] = r.json().get("code")
        except Exception:
            pass

    # --- 7) screen formularza karty (losowe dane + timestamp ms) ---
    if checkout_id:
        t0 = time.monotonic()
        _render_card_screen(checkout_id, results)
        results["timings"]["card_screenshot"] = round((time.monotonic() - t0) * 1000)

    # SUMA = czas zakupu BEZ screenshotu (screenshot to narzut dowodu, nie zakupu).
    results["timings"]["SUMA"] = sum(
        v for k, v in results["timings"].items()
        if isinstance(v, int) and k not in ("SUMA", "screenshot", "card_screenshot"))

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT}", flush=True)
    print(f"TIMINGI: {json.dumps(results['timings'], ensure_ascii=False)}", flush=True)


if __name__ == "__main__":
    main()