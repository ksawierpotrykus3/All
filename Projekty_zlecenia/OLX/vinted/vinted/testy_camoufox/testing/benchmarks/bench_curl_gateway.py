# coding: utf-8
"""Benchmark curl_cffi: pelny flow do BRAMKI PLATNOSCI (payment 200 pending + redirect).

Mierzy czas per-etap (ms od T0) i robi SCREENSHOT bramki przez Camoufox
z wypalonym znacznikiem czasu (T0, czas dotarcia do bramki, zegar UTC ms) - dowod
wizualny ze flow curl_cffi dociera do bramki platnosci.

Uzycie: python bench_curl_gateway.py
Wymaga swiezych cookies (cookies_profil.json) i profilu Camoufox.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
OUT_PREFIX = "bench_gateway"

results = {"ts_start": None, "steps": [], "elapsed": {}}
T0 = time.monotonic()  # start zegara - "od kiedy powinien zaczac liczyc"


def now_ms() -> float:
    return round((time.monotonic() - T0) * 1000, 1)


def wall_ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


results["ts_start"] = wall_ts()


def step(name, **extra):
    e = {"step": name, "elapsed_ms": now_ms(), "wall_utc": wall_ts()}
    e.update(extra)
    results["steps"].append(e)
    print(f"[{e['elapsed_ms']:>9.1f} ms] {name}", flush=True)


# --- Sesja curl_cffi ---
s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:  # noqa: BLE001
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


def find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(find_checksum(v))
    return hits


def get_txn_status(txn_id):
    r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn_id}", headers=H,
              impersonate=BrowserType.firefox133, timeout=30)
    return r.json().get("transaction", {})


# --- 0) Wybor swiezego itemu ---
step("wybor_itemu")
url = ("https://www.vinted.pl/api/v2/catalog/items"
       "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=40&currency=PLN")
r = s.get(url, headers=H, impersonate=BrowserType.firefox133, timeout=30)
item = None
for it in r.json().get("items", []):
    u = it.get("user", {})
    if it.get("status") == "sold" or it.get("is_visible") is False:
        continue
    item = it
    break
if item is None:
    print("BRAK itemu w katalogu - abort")
    raise SystemExit(1)
item_id, seller_id = item["id"], item["user"]["id"]
results["item"] = {"id": item_id, "seller": seller_id,
                   "title": item.get("title", "")[:60], "price": item.get("price", {})}
step(f"item {item_id} seller={seller_id} '{item.get('title','')[:40]}'")

# --- 1) Conversations ---
r = s.post("https://www.vinted.pl/api/v2/conversations",
           json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
           headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
j = r.json()
conv_id = j["conversation"]["id"]
txn_id = j["conversation"]["transaction"]["id"]
step(f"conversations conv={conv_id} txn={txn_id}", http=r.status_code)

# --- 2) Build ---
r = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
           json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
           headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
build = r.json()
checkout_id = build.get("checkout", {}).get("id")
ch = find_checksum(build)
comps = build.get("checkout", {}).get("components", {})
pd_inner = comps.get("shipping_pickup_details", {}).get("pickup_details", {})
rate_uuid = pd_inner.get("selected_rate_uuid")
so_id = comps.get("shipping_address", {}).get("shipping_order_id")
addr = comps.get("shipping_address", {}).get("address", {})
coords = addr.get("coordinates") or {}
lat, lon = coords.get("latitude"), coords.get("longitude")
step(f"build checkout={checkout_id}", http=r.status_code)

# --- 3) PUT payment_method ---
put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {"card_id": None, "pay_in_method_id": "12"},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": {},
}}, headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
try:
    ch2 = find_checksum(r.json())
except Exception:  # noqa: BLE001
    ch2 = []
step("put payment_method", http=r.status_code, checksum=bool(ch2))

# --- 4) Pickup points ---
point = None
if so_id:
    pts_url = (f"https://api.vinted.pl/shipping-estimation/external/shipping_orders/{so_id}"
               f"/nearby_pickup_points?country_code=PL&latitude={lat}&longitude={lon}")
    r = s.get(pts_url, headers=H, impersonate=BrowserType.firefox133, timeout=30)
    pp = r.json()
    spoints = (pp or {}).get("shipping_points") or []
    sug = (pp or {}).get("suggested_shipping_point_code")
    for cand in spoints:
        sp = cand.get("point", {})
        if sug and sp.get("code") == sug:
            point = sp
            break
    if point is None and spoints:
        point = spoints[0].get("point", {})
    step(f"pickup_points n={len(spoints)}", http=r.status_code)

# --- 5) PUT pickup_details ---
details = {}
if rate_uuid:
    details["rate_uuid"] = rate_uuid
if point:
    if point.get("code"):
        details["point_code"] = point["code"]
    if point.get("uuid"):
        details["point_uuid"] = point["uuid"]
    if point.get("rate_uuid"):
        details["rate_uuid"] = point["rate_uuid"]
r = s.put(put_url, json={"components": {
    "additional_service": {},
    "payment_method": {},
    "shipping_address": {},
    "shipping_pickup_options": {},
    "shipping_pickup_details": details,
}}, headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
try:
    ch3 = find_checksum(r.json())
except Exception:  # noqa: BLE001
    ch3 = []
step("put pickup_details", http=r.status_code, checksum=bool(ch3))

# --- 6) Payment -> BRAMKA ---
checksum = (ch3 or ch2 or ch)[0] if (ch3 or ch2 or ch) else ""
r = s.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
           json={"checksum": checksum, "payment_options": {"browser_info": {
               "language": "pl", "color_depth": 24, "java_enabled": False,
               "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}},
           headers=H, impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
try:
    pj = r.json()
except Exception:  # noqa: BLE001
    pj = {}
pay_status = (pj.get("payment") or {}).get("status")
nav = (pj.get("action") or {}).get("parameters") or {}
redirect_url = nav.get("url", "")
T_GATEWAY = now_ms()
# sukces = realny pending + URL bramki (nie pusty 403/404)
success = (r.status_code == 200 and pay_status == "pending" and bool(redirect_url))
results["success"] = success
step("PAYMENT -> BRAMKA" if success else "PAYMENT (BLAD)",
     http=r.status_code, payment_status=pay_status,
     redirect=redirect_url[:100], success=success)
results["elapsed"]["to_gateway_ms"] = T_GATEWAY if success else None

# --- 7) Status transakcji ---
t = get_txn_status(txn_id)
step("txn status", txn_status=t.get("status"), status_title=t.get("status_title"))
results["elapsed"]["txn_status_ms"] = now_ms()
results["txn"] = {"id": txn_id, "status": t.get("status"),
                  "status_title": t.get("status_title"),
                  "purchase_id": t.get("purchase_id")}

# --- 8) Screenshot bramki przez Camoufox (dowod wizualny) ---
step("start Camoufox do screena bramki")
from camoufox import Camoufox  # noqa: E402

shot_path = BASE_DIR / f"{OUT_PREFIX}_bramka.png"
try:
    with Camoufox(persistent_context=True, headless=True,
                  user_data_dir=str(PROFILE_DIR), os="windows",
                  fingerprint_preset=True, humanize=True) as ctx:
        page = ctx.new_page()
        page.goto(redirect_url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_timeout(4000)  # czas na przekierowania (api.vinted -> adyen)
        except Exception:  # noqa: BLE001
            pass
        page.screenshot(path=str(shot_path), full_page=False)
    step("screenshot bramki zapisany", file=str(shot_path))
except Exception as e:  # noqa: BLE001
    results["screenshot_error"] = str(e)
    print(f"BLAD screenshotu: {e}", flush=True)

# --- 9) Wypal znacznik czasu na screenshotcie (dowod wizualny) ---
try:
    if shot_path.exists():
        img = Image.open(shot_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except Exception:  # noqa: BLE001
            font = ImageFont.load_default()
        gw_ms = results["elapsed"].get("to_gateway_ms")
        gw_txt = f"+{gw_ms:.0f} ms" if gw_ms is not None else "BRAK (403/404)"
        lines = [
            f"curl_cffi -> BRAMKA | T0={results['ts_start']} | "
            f"dotarcie={gw_txt} | shot={wall_ts()} | payment={pay_status} txn={t.get('status')}",
        ]
        # czarny pasek NA DOLE (bramka zostaje widoczna na gorze)
        bar_h = 48
        draw.rectangle([0, img.height - bar_h, img.width, img.height], fill=(0, 0, 0))
        draw.text((12, img.height - bar_h + 8), lines[0], fill=(255, 255, 0), font=font)
        marked = BASE_DIR / f"{OUT_PREFIX}_bramka_dowod.png"
        img.save(marked)
        results["screenshot_marked"] = str(marked)
        print(f"Zapisano dowod: {marked}", flush=True)
except Exception as e:  # noqa: BLE001
    results["mark_error"] = str(e)
    print(f"BLAD znakowania: {e}", flush=True)

# --- zapis wyniku ---
out = BASE_DIR / f"{OUT_PREFIX}_wynik.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nZapisano: {out}", flush=True)
print(f"SUMA do bramki: {results['elapsed']['to_gateway_ms']} ms", flush=True)
