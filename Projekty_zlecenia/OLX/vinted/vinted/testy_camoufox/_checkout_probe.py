# coding: utf-8
import sys, time, json, traceback
from pathlib import Path

OUT = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\_checkout_probe_out.txt")

def log(msg):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"
HEADLESS = False  # False = widoczne okno

result = {"checkout_build_status": None, "checkout_build_body": None,
          "checkout_build_headers": {}, "token_captured": False,
          "final_url": None, "error": None}

log("t0 import")
from camoufox import Camoufox
log("t1 import ok")

try:
    log("t2 open context headless=%s" % HEADLESS)
    with Camoufox(persistent_context=True, headless=HEADLESS,
                  user_data_dir=PROFILE, os="windows") as ctx:
        log("t3 context open")
        page = ctx.new_page()
        log("t4 new page")

        def on_request(req):
            try:
                if "checkout/build" in req.url:
                    result["token_captured"] = bool(req.headers.get("x-incognia-request-token"))
                    log("REQ checkout/build token=%s" % result["token_captured"])
            except Exception:
                pass
        page.on("request", on_request)

        def handle_route(route):
            req = route.request
            if "checkout/build" in req.url:
                try:
                    resp = route.fetch()
                    result["checkout_build_status"] = resp.status
                    result["checkout_build_headers"] = dict(resp.headers)
                    try:
                        result["checkout_build_body"] = resp.text()[:2000]
                    except Exception as e:
                        result["checkout_build_body"] = "BODY_ERR: %r" % e
                    log("ROUTE checkout/build status=%s" % resp.status)
                    route.fulfill(response=resp)
                except Exception as e:
                    log("ROUTE FAIL: %r" % e)
                    route.continue_()
            else:
                route.continue_()

        page.route("**/checkout/build", handle_route)

        log("t5 goto item")
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        log("t6 goto done: " + page.url)
        time.sleep(4)

        buy = None
        for sel in ['button[data-testid="item-buy-button"]',
                    'button:has-text("Kup teraz")',
                    'button:has-text("Kup i zapłać")']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    buy = el
                    log("t7 buy button: " + sel)
                    break
            except Exception:
                continue

        if not buy:
            result["error"] = "no buy button"
            log("NO BUY BUTTON on " + page.url)
        else:
            log("t8 click buy")
            buy.click(timeout=10000)
            time.sleep(8)

        result["final_url"] = page.url
        log("t9 final_url=" + page.url)
        log("status=%s token=%s" % (result["checkout_build_status"], result["token_captured"]))
except Exception as e:
    result["error"] = repr(e)
    log("FAIL: " + repr(e))
    log(traceback.format_exc())

log("SAVING JSON")
Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_camoufox_checkout_probe.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
log("DONE")