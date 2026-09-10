# coding: utf-8
"""Rozstrzyga czy czysty Camoufox (headless=False, jedna stabilna sesja) przechodzi checkout/build."""
import time, json, sys, traceback
from pathlib import Path

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"
OUT = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_camoufox_checkout_probe.json")

result = {
    "checkout_build_status": None,
    "checkout_build_body": None,
    "checkout_build_headers": {},
    "x_incognia_request_token_captured": False,
    "final_url": None,
    "error": None,
}

def log(msg):
    print(msg, flush=True)

from camoufox import Camoufox

try:
    with Camoufox(persistent_context=True, headless=False,
                  user_data_dir=PROFILE, os="windows") as ctx:
        page = ctx.new_page()

        def on_request(req):
            try:
                if "checkout/build" in req.url:
                    h = req.headers
                    if h.get("x-incognia-request-token"):
                        result["x_incognia_request_token_captured"] = True
                    log("REQ checkout/build incognia=%s" % bool(h.get("x-incognia-request-token")))
            except Exception:
                pass

        page.on("request", on_request)

        # route interception zeby przeczytac body odpowiedzi checkout/build
        def handle_route(route):
            req = route.request
            if "checkout/build" in req.url:
                resp = route.fetch()
                result["checkout_build_status"] = resp.status
                result["checkout_build_headers"] = dict(resp.headers)
                try:
                    result["checkout_build_body"] = resp.text()[:2000]
                except Exception as e:
                    result["checkout_build_body"] = "BODY_ERR: %r" % e
                log("ROUTE checkout/build status=%s" % resp.status)
                route.fulfill(response=resp)
            else:
                route.continue_()

        page.route("**/checkout/build", handle_route)

        log("goto item")
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)

        buy = None
        for sel in ['button[data-testid="item-buy-button"]',
                    'button:has-text("Kup teraz")',
                    'button:has-text("Kup i zapłać")']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    buy = el
                    log("buy button: " + sel)
                    break
            except Exception:
                continue

        if not buy:
            result["error"] = "no buy button"
            log("NO BUY BUTTON")
        else:
            log("click buy")
            buy.click(timeout=10000)
            time.sleep(8)

        result["final_url"] = page.url
        log("final_url=" + page.url)
        log("status=%s token=%s" % (result["checkout_build_status"], result["x_incognia_request_token_captured"]))
except Exception as e:
    result["error"] = repr(e)
    log("FAIL: " + repr(e))
    log(traceback.format_exc())

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
log("SAVED -> " + str(OUT))