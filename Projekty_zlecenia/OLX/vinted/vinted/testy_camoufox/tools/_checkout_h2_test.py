# coding: utf-8
"""_checkout_h2_test.py — test hipotezy H2: prefetch strony /checkout przed build.

H2: po kliknieciu 'Kup teraz' strona przechodzi na /checkout i DataDome wykonuje
challenge JS w tle. Dopiero PO pelnym zaladowaniu strony checkoutu reczny build
moze przejsc 200 (DataDome "nauczylo sie" sesji na tej stronie).

Roznica vs H1: czekamy az strona /checkout w pelni sie zaladuje (networkidle)
i dopiero potem wysylamy nasz build.
"""
import json
import time
import traceback
from pathlib import Path

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"
OUT_JSON = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_checkout_h2_test.json")
OUT_LOG = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_checkout_h2_test.log")

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

result = {
    "build_after_full_load_status": None,
    "build_after_full_load_ms": None,
    "build_after_full_load_body": None,
    "conversations_status": None,
    "txn_id": None,
    "checkout_url": None,
    "error": None,
}


def log(m):
    line = "[H2] " + m
    print(line, flush=True)
    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_txn(obj):
    if isinstance(obj, dict):
        if obj.get("transaction") and isinstance(obj["transaction"], dict) and obj["transaction"].get("id"):
            return obj["transaction"]["id"]
        for v in obj.values():
            r = find_txn(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_txn(v)
            if r:
                return r
    return None


def main():
    from camoufox import Camoufox

    OUT_LOG.write_text("", encoding="utf-8")
    log("start H2 test (prefetch strony checkout)")

    for lock in ("parent.lock", "lock", "lockfile"):
        p = Path(PROFILE) / lock
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

    try:
        with Camoufox(
            persistent_context=True,
            headless=True,
            user_data_dir=PROFILE,
            os="windows",
            fingerprint_preset=True,
            humanize=False,
            block_webgl=True,
            firefox_user_prefs=prefs,
            i_know_what_im_doing=True,
        ) as ctx:
            page = ctx.new_page()

            API_H = {"accept": "application/json", "locale": "pl-PL",
                     "content-type": "application/json",
                     "x-csrf-token": CSRF, "x-anon-id": ANON}

            # 1) catalog -> item
            r = ctx.request.get(
                "https://www.vinted.pl/api/v2/catalog/items"
                "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=2&currency=PLN",
                headers={"accept": "application/json", "locale": "pl-PL",
                         "x-csrf-token": CSRF, "x-anon-id": ANON})
            items = r.json().get("items", [])
            item = next((it for it in items if it.get("status") != "sold" and it.get("is_visible") is not False), None)
            if not item:
                result["error"] = "brak itemu"
                log("BRAK itemu")
                return
            item_id, seller_id = item["id"], item["user"]["id"]
            log("item %d seller=%d" % (item_id, seller_id))

            # 2) conversations -> txn_id
            r = ctx.request.post("https://www.vinted.pl/api/v2/conversations",
                                 data=json.dumps({"initiator": "buy", "item_id": str(item_id),
                                                  "opposite_user_id": seller_id}),
                                 headers=API_H)
            result["conversations_status"] = r.status
            log("conversations status=%d" % r.status)
            if r.status != 200:
                result["error"] = "conversations != 200"
                return
            txn_id = find_txn(r.json())
            result["txn_id"] = txn_id
            log("txn_id=%s" % txn_id)

            # 3) klik 'Kup teraz' -> nawigacja na /checkout, czekamy az sie w pelni zaladuje
            log("goto item page")
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            buy = None
            for sel in ['button[data-testid="item-buy-button"]',
                        'button:has-text("Kup teraz")',
                        'button:has-text("Kup i zapłać")']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        buy = el
                        break
                except Exception:
                    continue

            if buy:
                try:
                    with page.expect_navigation(url="**/checkout**", timeout=20000):
                        buy.click(timeout=10000)
                    log("na stronie /checkout, czekam na networkidle (DataDome challenge)...")
                    try:
                        page.wait_for_load_state("networkidle", timeout=20000)
                    except Exception:
                        log("networkidle timeout - kontynuuje")
                    time.sleep(5)  # dodatkowy czas na challenge DataDome
                    result["checkout_url"] = page.url
                    log("checkout_url=" + page.url)
                except Exception as e:
                    log("nav fail: %r" % e)
                    time.sleep(5)
            else:
                log("brak buy button")

            # 4) TERAZ wysylamy reczny build (po pelnym zaladowaniu strony checkout)
            t0 = time.monotonic()
            r = ctx.request.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
                                 data=json.dumps({"purchase_items": [{"id": txn_id, "type": "transaction"}]}),
                                 headers=API_H)
            result["build_after_full_load_ms"] = round((time.monotonic() - t0) * 1000)
            result["build_after_full_load_status"] = r.status
            try:
                result["build_after_full_load_body"] = r.body()[:400].decode("utf-8", "ignore")
            except Exception:
                pass
            log("build po full load: %d ms status=%d" % (result["build_after_full_load_ms"], r.status))

    except Exception as e:
        result["error"] = repr(e)
        log("FAIL: " + repr(e))
        log(traceback.format_exc())

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log("SAVED -> " + str(OUT_JSON))


if __name__ == "__main__":
    main()
