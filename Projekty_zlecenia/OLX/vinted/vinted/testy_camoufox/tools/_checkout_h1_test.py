# coding: utf-8
"""_checkout_h1_test.py — test hipotezy H1: czy build z X-Incognia-Request-Token przechodzi 200?

Strategia: w jednej zywej sesji Camoufox przechwytujemy realny token Incognia
generowany przez strone przy kliknieciu 'Kup teraz', a potem wysylamy wlasny
reczny POST checkout/build z tym tokenem w naglowku i mierzymy status.

Porownanie do benchmarku (wynik 403): benchmark NIE wysylal tokenu Incognia.
Jesli H1 prawdziwa -> nasz build z tokenem zwroci 200.
"""
import json
import time
import traceback
from pathlib import Path

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"
OUT_JSON = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_checkout_h1_test.json")
OUT_LOG = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_checkout_h1_test.log")

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

result = {
    "token_captured_from_click": False,
    "token_len": None,
    "build_with_token_status": None,
    "build_with_token_ms": None,
    "build_with_token_body": None,
    "build_without_token_status": None,
    "build_without_token_ms": None,
    "conversations_status": None,
    "txn_id": None,
    "error": None,
}

captured = {"token": None}
result["_captured_token"] = None  # wynik do JSON


def log(msg):
    line = "[H1] " + msg
    print(line, flush=True)
    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_txn(obj):
    """Szuka transaction id w odpowiedzi conversations."""
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

    # wyczysc stary log
    OUT_LOG.write_text("", encoding="utf-8")
    log("start H1 test")

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

            # --- przechwytuj token Incognia z requestow strony ---
            def on_request(req):
                try:
                    if "checkout/build" in req.url or "checkout/payment" in req.url:
                        tok = req.headers.get("x-incognia-request-token")
                        if tok:
                            captured["token"] = tok
                            result["_captured_token"] = tok  # duplikat do result
                            result["token_captured_from_click"] = True
                            result["token_len"] = len(tok)
                            log("captured token len=%d url=%s" % (len(tok), req.url[:80]))
                except Exception:
                    pass

            page.on("request", on_request)

            # --- 1) otworz strone itemu i kliknij 'Kup teraz' zeby wygenerowac token ---
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

            if buy:
                try:
                    # czekamy az strona przejdzie na /checkout (to znak ze build wyslany)
                    with page.expect_navigation(url="**/checkout**", timeout=20000):
                        buy.click(timeout=10000)
                    log("nawigacja na /checkout - build wyslany, czekam 4s na callback on_request...")
                    time.sleep(4)
                except Exception as e:
                    log("click/nav fail: %r" % e)
                    time.sleep(4)
            else:
                log("brak buy button - token moze nie zostac wygenerowany")

            token = captured["token"] or result["_captured_token"]
            log("token captured=%s (captured=%s result=%s)" % (bool(token), bool(captured["token"]), bool(result["_captured_token"])))

            API_H = {"accept": "application/json", "locale": "pl-PL",
                     "content-type": "application/json",
                     "x-csrf-token": CSRF, "x-anon-id": ANON}

            # --- 2) szybki catalog do pobrania itemu ---
            r = ctx.request.get(
                "https://www.vinted.pl/api/v2/catalog/items"
                "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=2&currency=PLN",
                headers={"accept": "application/json", "locale": "pl-PL",
                         "x-csrf-token": CSRF, "x-anon-id": ANON})
            items = r.json().get("items", [])
            item = next((it for it in items if it.get("status") != "sold" and it.get("is_visible") is not False), None)
            if not item:
                result["error"] = "brak itemu w katalogu"
                log("BRAK itemu")
                return
            item_id, seller_id = item["id"], item["user"]["id"]
            log("item %d seller=%d" % (item_id, seller_id))

            # --- 3) conversations (inicjacja transakcji) ---
            t0 = time.monotonic()
            r = ctx.request.post("https://www.vinted.pl/api/v2/conversations",
                                 data=json.dumps({"initiator": "buy", "item_id": str(item_id),
                                                  "opposite_user_id": seller_id}),
                                 headers=API_H)
            result["conversations_status"] = r.status
            log("conversations: %d ms status=%d" % (round((time.monotonic() - t0) * 1000), r.status))
            if r.status != 200:
                result["error"] = "conversations != 200"
                return
            txn_id = find_txn(r.json())
            result["txn_id"] = txn_id
            log("txn_id=%s" % txn_id)
            if not txn_id:
                result["error"] = "brak txn_id"
                return

            body = {"purchase_items": [{"id": txn_id, "type": "transaction"}]}

            # --- 4a) build BEZ tokenu (kontrola - powinno dac 403 jak w benchmarku) ---
            t0 = time.monotonic()
            r = ctx.request.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
                                 data=json.dumps(body), headers=API_H)
            result["build_without_token_status"] = r.status
            result["build_without_token_ms"] = round((time.monotonic() - t0) * 1000)
            log("build BEZ tokenu: %d ms status=%d" % (result["build_without_token_ms"], r.status))

            # --- 4b) build Z tokenem Incognia (H1) ---
            if token:
                h_tok = dict(API_H)
                h_tok["x-incognia-request-token"] = token
                t0 = time.monotonic()
                r = ctx.request.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
                                     data=json.dumps(body), headers=h_tok)
                result["build_with_token_status"] = r.status
                result["build_with_token_ms"] = round((time.monotonic() - t0) * 1000)
                try:
                    result["build_with_token_body"] = r.body()[:400].decode("utf-8", "ignore")
                except Exception:
                    pass
                log("build Z tokenem: %d ms status=%d" % (result["build_with_token_ms"], r.status))
            else:
                log("BRAK tokenu - pominieto test Z tokenem")

            log("final_url=" + page.url)

    except Exception as e:
        result["error"] = repr(e)
        log("FAIL: " + repr(e))
        log(traceback.format_exc())

    # do JSON zapisz tylko prefix tokenu (pełny jest za dlugi)
    if result.get("_captured_token"):
        result["_captured_token_prefix"] = result["_captured_token"][:60] + "..."
        result["_captured_token"] = None
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log("SAVED -> " + str(OUT_JSON))


if __name__ == "__main__":
    main()
