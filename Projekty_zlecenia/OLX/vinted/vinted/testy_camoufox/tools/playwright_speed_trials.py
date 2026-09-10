# coding: utf-8
"""playwright_speed_trials.py — flow do bramki W CAŁOŚCI w Playwright (Camoufox).

Dlaczego: curl_cffi z cookie z przegladarki jest wywalywany przez DataDome
(cookie jest zwiazane z fingerprintem TLS Firefoksa). W przegladarce cookie
i fingerprint sa spojne -> 403 nie powinno wracac.

Cel:
  - zmierzyc czasy krokow w przegladarce (ctx.request = ten sam stack sieciowy)
  - zebrac trace sieci z loadu strony itemu (wektory/potencjaly: co frontend prefetchuje)
  - test wariantu MINIMAL (build -> payment od razu)
  - zapis rozmiarow odpowiedzi (mniejsza ilosc danych)
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
PROFILE_DIR = ROOT / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_playwright_speed_trials.json"


def wall():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


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


def main():
    from camoufox import Camoufox

    results = {"ts": wall(), "trace": []}

    # locki profilu
    for lock in ("parent.lock", "lock", "lockfile"):
        p = PROFILE_DIR / lock
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    prefs = {
        "layers.acceleration.disabled": True,
        "gfx.webrender.software": True,
        "gfx.webrender.all": False,
        "gfx.canvas.accelerated": False,
        "dom.ipc.processPrelaunch.enabled": False,
    }

    with Camoufox(
        persistent_context=True,
        headless=False,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=False,
        block_webgl=True,
        firefox_user_prefs=prefs,
        i_know_what_im_doing=True,
    ) as ctx:
        page = ctx.new_page()

        # --- trace sieci: co frontend sciaga przy ladowaniu itemu ---
        def on_request(req):
            if req.resource_type in ("xhr", "fetch"):
                results["trace"].append({
                    "t": round((time.monotonic() - T0) * 1000),
                    "m": req.method,
                    "u": req.url[:160],
                    "size": None,
                })

        T0 = time.monotonic()
        page.on("request", on_request)

        def on_response(resp):
            if resp.request.resource_type in ("xhr", "fetch"):
                body = b""
                try:
                    body = resp.body()
                except Exception:
                    pass
                # dopasuj do wpisu po url
                for e in results["trace"]:
                    if e["size"] is None and e["u"] in resp.url:
                        e["size"] = len(body)
                        e["status"] = resp.status
                        break

        page.on("response", on_response)

        # 1) wybierz item lekko: per_page=2 (mniejsza ilosc danych)
        t0 = time.monotonic()
        r = ctx.request.get(
            "https://www.vinted.pl/api/v2/catalog/items"
            "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=2&currency=PLN",
            headers={"accept": "application/json", "locale": "pl-PL", "x-csrf-token": CSRF, "x-anon-id": ANON},
        )
        cat_ms = round((time.monotonic() - t0) * 1000)
        items = r.json().get("items", [])
        item = next((it for it in items if it.get("status") != "sold" and it.get("is_visible") is not False), None)
        results["catalog_ms"] = cat_ms
        results["catalog_size"] = len(r.body())
        results["catalog_items"] = len(items)
        print(f"catalog per_page=2: {cat_ms} ms, {len(r.body())} B, {len(items)} items", flush=True)
        if not item:
            results["error"] = "brak itemu"
            print("BRAK itemu", flush=True)
            return
        item_id, seller_id = item["id"], item["user"]["id"]
        print(f"item {item_id} seller={seller_id} '{item.get('title','')[:40]}'", flush=True)

        # 2) wejdz na strone itemu (fresh datadome cookie od DataDome)
        page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        time.sleep(8)

        def dd():
            try:
                ck = ctx.cookies("https://www.vinted.pl/")
                d = next((c for c in ck if c.get("name") == "datadome"), None)
                return d["value"][:50] if d else "BRAK"
            except Exception:
                return "?"

        dd0 = dd()
        results["datadome_po_load"] = dd0
        print(f"datadome po loadzie: {dd0}", flush=True)

        API_H = {"accept": "application/json", "locale": "pl-PL", "content-type": "application/json",
                 "x-csrf-token": CSRF, "x-anon-id": ANON}

        # 3) conversations
        t0 = time.monotonic()
        r = ctx.request.post("https://www.vinted.pl/api/v2/conversations",
                             data=json.dumps({"initiator": "buy", "item_id": str(item_id),
                                              "opposite_user_id": seller_id}),
                             headers=API_H)
        conv_ms = round((time.monotonic() - t0) * 1000)
        results["conversations"] = {"ms": conv_ms, "status": r.status, "size": len(r.body())}
        print(f"conversations: {conv_ms} ms status={r.status}", flush=True)
        if r.status != 200:
            results["conversations_body"] = r.body()[:120].decode("utf-8", "ignore")
            results["error"] = "conversations nie 200"
            OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            return
        conv = r.json()
        txn_id = conv["conversation"]["transaction"]["id"]

        # 4) build
        t0 = time.monotonic()
        r = ctx.request.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
                             data=json.dumps({"purchase_items": [{"id": txn_id, "type": "transaction"}]}),
                             headers=API_H)
        build_ms = round((time.monotonic() - t0) * 1000)
        results["build"] = {"ms": build_ms, "status": r.status, "size": len(r.body())}
        print(f"build: {build_ms} ms status={r.status}", flush=True)
        if r.status != 200:
            results["build_body"] = r.body()[:120].decode("utf-8", "ignore")
            results["error"] = "build nie 200"
            OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            return
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
        results["checkout_id"] = checkout_id
        print(f"checkout={checkout_id} so_id={so_id} rate_uuid={rate_uuid}", flush=True)

        # 5) wariant MINIMAL: od razu payment na checksumie z builda
        t0 = time.monotonic()
        r = ctx.request.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
                             data=json.dumps({"checksum": ch[0] if ch else "", "payment_options": {"browser_info": {
                                 "language": "pl", "color_depth": 24, "java_enabled": False,
                                 "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}}),
                             headers=API_H)
        pay_ms = round((time.monotonic() - t0) * 1000)
        results["payment_MINIMAL"] = {"ms": pay_ms, "status": r.status, "size": len(r.body())}
        print(f"payment MINIMAL: {pay_ms} ms status={r.status}", flush=True)
        if r.status == 200:
            pj = r.json()
            ps = (pj.get("payment") or {}).get("status")
            rd = ((pj.get("action") or {}).get("parameters") or {}).get("url", "")
            results["payment_MINIMAL"]["payment_status"] = ps
            results["payment_MINIMAL"]["redirect"] = rd[:100]
            print(f"  -> status={ps} redirect={rd[:60]}", flush=True)
        else:
            results["payment_MINIMAL"]["body"] = r.body()[:150].decode("utf-8", "ignore")
            # fallback: payment_method -> payment
            put_url = f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
            t0 = time.monotonic()
            r = ctx.request.put(put_url, data=json.dumps({"components": {
                "additional_service": {}, "payment_method": {"card_id": None, "pay_in_method_id": "12"},
                "shipping_address": {}, "shipping_pickup_options": {}, "shipping_pickup_details": {}},
            }), headers=API_H)
            pm_ms = round((time.monotonic() - t0) * 1000)
            results["payment_method"] = {"ms": pm_ms, "status": r.status}
            print(f"payment_method: {pm_ms} ms status={r.status}", flush=True)
            if r.status == 200:
                try:
                    ch = find_checksum(r.json())
                except Exception:
                    ch = []
            t0 = time.monotonic()
            r = ctx.request.post(f"https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment",
                                 data=json.dumps({"checksum": ch[0] if ch else "", "payment_options": {"browser_info": {
                                     "language": "pl", "color_depth": 24, "java_enabled": False,
                                     "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}}),
                                 headers=API_H)
            pay2_ms = round((time.monotonic() - t0) * 1000)
            results["payment_po_method"] = {"ms": pay2_ms, "status": r.status}
            print(f"payment po method: {pay2_ms} ms status={r.status}", flush=True)
            if r.status == 200:
                pj = r.json()
                results["payment_po_method"]["payment_status"] = (pj.get("payment") or {}).get("status")
                results["payment_po_method"]["redirect"] = \
                    (((pj.get("action") or {}).get("parameters") or {}).get("url") or "")[:100]

        results["datadome_koniec"] = dd()
        results["trace"] = [e for e in results["trace"] if e.get("status") is not None]

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT}", flush=True)


if __name__ == "__main__":
    main()
