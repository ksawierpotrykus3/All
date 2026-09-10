# coding: utf-8
"""Rozstrzyga przyczynę 403 na checkout/build: body odpowiedzi + plaintext Incognii w JEDNEJ żywej sesji."""
import time, json, traceback
from pathlib import Path

OUT_LOG = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\_checkout_403_diag.txt")
OUT_JSON = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_checkout_403_diag.json")

def log(msg):
    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"

INIT_SCRIPT = r"""
(function () {
  if (window.__chInstalled) return;
  window.__chInstalled = true;
  window.__captured = { encrypt_calls: [], import_key_calls: [] };
  const toB64 = (buf) => { const b = new Uint8Array(buf); let s=''; for(let i=0;i<b.length;i++) s+=String.fromCharCode(b[i]); return btoa(s); };
  const arr = (x) => x instanceof ArrayBuffer ? new Uint8Array(x.slice(0)) : (ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) : null);
  const origEnc = crypto.subtle.encrypt.bind(crypto.subtle);
  crypto.subtle.encrypt = async function (algo, key, data) {
    const a = arr(data);
    window.__captured.encrypt_calls.push({ algo: JSON.stringify(algo), len: a?a.length:-1, plaintext_b64: a?toB64(a):null, key_alg: key&&key.algorithm&&key.algorithm.name });
    return origEnc(algo, key, data);
  };
})();
"""

result = {
    "checkout_build_status": None,
    "checkout_build_body": None,
    "checkout_build_headers": None,
    "token_captured": False,
    "canvas_from_token": None,
    "final_url": None,
    "error": None,
}

log("t0 import")
from camoufox import Camoufox

try:
    log("t1 open context (headless=True)")
    with Camoufox(persistent_context=True, headless=True,
                  user_data_dir=PROFILE, os="windows") as ctx:
        page = ctx.new_page()
        page.add_init_script(INIT_SCRIPT)

        def on_request(req):
            try:
                if "checkout/build" in req.url:
                    result["token_captured"] = bool(req.headers.get("x-incognia-request-token"))
                    log("REQ checkout/build token=%s" % result["token_captured"])
            except Exception:
                pass

        def handle_route(route):
            req = route.request
            if "checkout/build" in req.url:
                try:
                    resp = route.fetch()
                    result["checkout_build_status"] = resp.status
                    result["checkout_build_headers"] = dict(resp.headers)
                    try:
                        result["checkout_build_body"] = resp.text()[:3000]
                    except Exception as e:
                        result["checkout_build_body"] = "BODY_ERR: %r" % e
                    log("ROUTE checkout/build status=%s" % resp.status)
                    route.fulfill(response=resp)
                except Exception as e:
                    log("ROUTE FAIL: %r" % e)
                    route.continue_()
            else:
                route.continue_()

        page.on("request", on_request)
        page.route("**/checkout/build", handle_route)

        log("t2 goto item")
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        log("t3 goto done: " + page.url)
        time.sleep(4)

        buy = None
        for sel in ['button[data-testid="item-buy-button"]',
                    'button:has-text("Kup teraz")',
                    'button:has-text("Kup i zapłać")']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    buy = el
                    log("t4 buy button: " + sel)
                    break
            except Exception:
                continue

        if not buy:
            result["error"] = "no buy button"
            log("NO BUY BUTTON")
        else:
            log("t5 click buy")
            try:
                buy.click(timeout=10000)
            except Exception as e:
                log("click FAIL: %r" % e)
            time.sleep(8)

        result["final_url"] = page.url
        log("t6 final_url=" + page.url)

        # odczytaj plaintext z hooka i wyciagnij canvas_paint
        try:
            data = page.evaluate("() => window.__captured || { encrypt_calls: [] }")
            encs = data.get("encrypt_calls", [])
            import base64 as _b64
            for c in encs:
                b64 = c.get("plaintext_b64")
                if not b64:
                    continue
                raw = _b64.b64decode(b64)
                if b'"app_id"' in raw[:200]:
                    obj = json.loads(raw.decode("utf-8", "replace"))
                    result["canvas_from_token"] = {
                        "canvas_paint_cpu_1": obj.get("canvas_paint_cpu_1"),
                        "canvas_paint_cpu_2": obj.get("canvas_paint_cpu_2"),
                        "canvas_paint_gpu_1": obj.get("canvas_paint_gpu_1"),
                        "canvas_paint_gpu_2": obj.get("canvas_paint_gpu_2"),
                        "token_sequence_number": obj.get("token_sequence_number"),
                        "session_id": obj.get("session_id"),
                    }
                    log("canvas_from_token: seq=%s session=%s" % (
                        obj.get("token_sequence_number"), obj.get("session_id")))
                    break
        except Exception as e:
            log("plaintext extract FAIL: %r" % e)

        log("status=%s token=%s" % (result["checkout_build_status"], result["token_captured"]))
except Exception as e:
    result["error"] = repr(e)
    log("FAIL: " + repr(e))
    log(traceback.format_exc())

OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
log("SAVED -> " + str(OUT_JSON))
log("DONE")