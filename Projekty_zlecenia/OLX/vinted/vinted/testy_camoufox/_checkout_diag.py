# coding: utf-8
import time, json, traceback
from pathlib import Path

OUT = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\_checkout_diag_out.txt")

def log(msg):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"

reqs = []
resps = []
pops = []

log("t0 import")
from camoufox import Camoufox

try:
    with Camoufox(persistent_context=True, headless=False,
                  user_data_dir=PROFILE, os="windows") as ctx:
        # lapanie popupow
        ctx.on("page", lambda p: (pops.append(p.url), log("POPUP: " + p.url)))

        page = ctx.new_page()

        def on_request(r):
            if "checkout" in r.url:
                reqs.append(r.url)
                log("REQ " + r.url)

        def on_response(r):
            if "checkout" in r.url:
                resps.append((r.url, r.status))
                log("RES %s %s" % (r.status, r.url))

        page.on("request", on_request)
        page.on("response", on_response)

        log("t1 goto item")
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        log("t2 goto done: " + page.url)
        time.sleep(4)

        # zamknij ew. banner "Koszt wysyłki ... Zamknij"
        try:
            for sel in ['button:has-text("Zamknij")']:
                el = page.locator(sel).first
                if el.is_visible(timeout=1500):
                    el.click(timeout=2000)
                    log("zamknieto banner: " + sel)
                    time.sleep(1)
        except Exception as e:
            log("banner zamkniecie skip: %r" % e)

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
            log("NO BUY BUTTON; page html head: " + page.content()[:500])
        else:
            log("click buy")
            try:
                buy.click(timeout=10000)
            except Exception as e:
                log("click FAIL: %r" % e)
            # czekaj na nawigacje/request
            for _ in range(20):
                time.sleep(0.5)
                if any("checkout" in u for u in reqs) or page.url.startswith("https://www.vinted.pl/checkout"):
                    break

        log("FINAL URL: " + page.url)
        log("POPUPS: %s" % pops)
        log("checkout REQS: %s" % [u for u in reqs if "checkout" in u])
        log("checkout RESPS: %s" % [(u, s) for u, s in resps if "checkout" in u])
        # screenshot
        try:
            page.screenshot(path=r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\screenshots\_checkout_diag.png", full_page=False)
            log("screenshot saved")
        except Exception as e:
            log("screenshot err: %r" % e)
except Exception as e:
    log("FAIL: " + repr(e))
    log(traceback.format_exc())

log("DONE")