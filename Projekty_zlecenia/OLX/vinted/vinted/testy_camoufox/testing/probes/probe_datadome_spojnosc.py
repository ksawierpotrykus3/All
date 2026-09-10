# coding: utf-8
"""probe_datadome_spojnosc.py — rozstrzyga, czy 403 na build to BRAK cookie `datadome`
w eksporcie cookies_profil.json (niespojnosc), czy zablokowany stan datadome / blokada per-IP.

Ustalenie: profil_firefox_135/cookies.sqlite ZAWIERA datadome (exp ~2027), a cookies_profil.json
NIE. Wszystkie testy curl_cffi/NewContext szly bez tokenu datadome -> 403.

T1 (curl_cffi):  cookies_profil.json + datadome z cookies.sqlite -> conversations + build.
T2 (Camoufox persistent): ladujemy strone itemu, czekamy 20s na skrypt DataDome,
   rejestrujemy wartosc datadome przed/po, wykrywamy captcha, klikamy "Kup teraz".

Uzycie: python probe_datadome_spojnosc.py [item_id_t2]
"""
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
COOKIES_PATH = BASE_DIR / "cookies_profil.json"
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_probe_datadome_spojnosc.json"

results = {"ts": datetime.now(timezone.utc).isoformat()}


def datadome_from_sqlite():
    db = sqlite3.connect(str(PROFILE_DIR / "cookies.sqlite"))
    rows = db.execute(
        "SELECT value, host, expiry FROM moz_cookies WHERE name='datadome' ORDER BY expiry DESC"
    ).fetchall()
    db.close()
    if not rows:
        return None
    value, host, expiry = rows[0]
    return {"name": "datadome", "value": value, "domain": host, "path": "/",
            "expires": expiry, "httpOnly": True, "secure": True, "sameSite": "Lax"}


def _curl_session(cookies, with_auth=True):
    s = cr.Session()
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
        "x-csrf-token": CSRF,
        "x-anon-id": ANON,
    })
    if with_auth:
        at = next((c["value"] for c in cookies if c["name"] == "access_token_web"), "")
        if at:
            s.headers["authorization"] = f"Bearer {at}"
    return s


def _pick_item(s):
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?price_to=100&order=newest_first&page=1&per_page=40&currency=PLN",
              impersonate=BrowserType.firefox133, timeout=30)
    for it in r.json().get("items", []):
        if it.get("status") != "sold" and it.get("is_visible") is not False:
            return it
    return None


def t1():
    print("=== T1: curl_cffi + datadome z profilu (cookies.sqlite) ===", flush=True)
    cookies = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    dd = datadome_from_sqlite()
    if not dd:
        results["t1"] = {"error": "brak datadome w cookies.sqlite"}
        print("  BRAK datadome w cookies.sqlite", flush=True)
        return
    cookies = [c for c in cookies if c.get("name") != "datadome"]
    cookies.append(dd)
    print(f"  datadome z profilu: {dd['value'][:50]}... (host={dd['domain']})", flush=True)

    s = _curl_session(cookies)
    r = s.get("https://www.vinted.pl/api/v2/users/current", impersonate=BrowserType.firefox133, timeout=30)
    login = None
    try:
        login = r.json().get("user", {}).get("login") if r.status_code == 200 else None
    except Exception:
        pass
    print(f"  login: {r.status_code} {login}", flush=True)

    item = _pick_item(s)
    if not item:
        results["t1"] = {"error": "brak itemu"}
        print("  brak itemu", flush=True)
        return
    item_id = item["id"]
    seller_id = item["user"]["id"]
    print(f"  item {item_id} ({item.get('title', '')[:45]})", flush=True)

    rc = s.post("https://www.vinted.pl/api/v2/conversations",
                json={"initiator": "buy", "item_id": str(item_id), "opposite_user_id": seller_id},
                impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
    print(f"  conversations: {rc.status_code}", flush=True)
    txn_id = None
    try:
        txn_id = rc.json().get("conversation", {}).get("transaction", {}).get("id")
    except Exception:
        pass
    if not txn_id:
        results["t1"] = {"conversations_status": rc.status_code, "raw": rc.text[:150],
                         "item_id": item_id}
        print(f"  brak transaction_id: {rc.text[:150]}", flush=True)
        return

    rb = s.post("https://www.vinted.pl/api/v2/purchases/checkout/build",
                json={"purchase_items": [{"id": txn_id, "type": "transaction"}]},
                headers={"referer": f"https://www.vinted.pl/items/{item_id}"},
                impersonate=BrowserType.firefox133, timeout=30, allow_redirects=False)
    checkout_id = None
    if rb.status_code == 200:
        try:
            checkout_id = rb.json().get("checkout", {}).get("id")
        except Exception:
            pass
    res = {"status": rb.status_code, "x_datadome": rb.headers.get("x-datadome", ""),
           "checkout_id": checkout_id, "transaction_id": txn_id, "item_id": item_id,
           "body_head": rb.text[:150]}
    results["t1"] = res
    print(f"  BUILD: status={res['status']} checkout_id={checkout_id}", flush=True)


def t2():
    print("\n=== T2: Camoufox persistent + czekanie 20s na skrypt DataDome ===", flush=True)
    from camoufox import Camoufox

    for lock in ("parent.lock", "lock", "lockfile"):
        p = PROFILE_DIR / lock
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    # wybor swiezego itemu przez curl (cookies_profil.json wystarcza na katalog)
    s0 = _curl_session(json.loads(COOKIES_PATH.read_text(encoding="utf-8")), with_auth=False)
    item = _pick_item(s0)
    if not item:
        results["t2"] = {"error": "brak itemu"}
        print("  brak itemu", flush=True)
        return
    item_id = item["id"]
    print(f"  item {item_id} ({item.get('title', '')[:45]})", flush=True)

    captured = {"requests": []}

    def on_response(resp):
        if resp.url.endswith("/api/v2/purchases/checkout/build"):
            captured["status"] = resp.status
            if resp.status == 200:
                try:
                    j = resp.json()
                    captured["checkout_id"] = (j.get("checkout") or {}).get("id")
                except Exception:
                    pass

    def on_request(req):
        if "checkout/build" in req.url or "conversations" in req.url:
            captured["requests"].append(f"{req.method} {req.url[:100]}")

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
        i_know_what_im_doing=True,
    ) as ctx:
        page = ctx.new_page()
        page.on("response", on_response)
        page.on("request", on_request)
        try:
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"  goto err: {e}", flush=True)

        # czekanie na wykonanie skryptu DataDome (ustawienie/odnowienie cookie)
        for i in range(5):
            time.sleep(4)
            ck = ctx.cookies("https://www.vinted.pl/")
            dd = next((c for c in ck if c.get("name") == "datadome"), None)
            state = f"datadome={dd['value'][:25]}..." if dd else "datadome=BRAK"
            print(f"  +{4 * (i + 1)}s {state}", flush=True)

        # diagnostyka: captcha / buy button / stan datadome
        try:
            diag = page.evaluate("""() => {
                const ifr = Array.from(document.querySelectorAll('iframe')).map(f => (f.src || '').slice(0, 60));
                return {
                    title: document.title,
                    url: location.href,
                    buyBtn: !!document.querySelector('button[data-testid="item-buy-button"]'),
                    ddCaptcha: !!document.querySelector('.datadome-captcha'),
                    iframes: ifr,
                };
            }""")
            print(f"  DIAG: {json.dumps(diag, ensure_ascii=False)[:700]}", flush=True)
        except Exception as e:
            print(f"  diag err: {e}", flush=True)

        dd_before = None
        ck = ctx.cookies("https://www.vinted.pl/")
        dd = next((c for c in ck if c.get("name") == "datadome"), None)
        if dd:
            dd_before = dd["value"][:50]
        print(f"  datadome przed klikiem: {dd_before}", flush=True)

        try:
            page.evaluate("""() => {
                const b = document.querySelector('#onetrust-accept-btn-handler');
                if (b) b.click();
            }""")
        except Exception:
            pass
        time.sleep(1)

        for attempt in range(1, 3):
            if "status" in captured:
                break
            try:
                clicked = page.evaluate("""() => {
                    const b = document.querySelector('button[data-testid="item-buy-button"]');
                    if (!b) return false;
                    b.click();
                    return true;
                }""")
                print(f"  click attempt={attempt} clicked={clicked}", flush=True)
            except Exception as e:
                print(f"  click err: {e}", flush=True)
            for _ in range(100):
                if "status" in captured:
                    break
                time.sleep(0.2)
            if "status" not in captured:
                time.sleep(2)

        ck = ctx.cookies("https://www.vinted.pl/")
        dd_after = None
        dd = next((c for c in ck if c.get("name") == "datadome"), None)
        if dd:
            dd_after = dd["value"][:50]
        res = {"status": captured.get("status"), "checkout_id": captured.get("checkout_id"),
               "dd_before": dd_before, "dd_after": dd_after, "item_id": item_id,
               "requests": captured["requests"][-6:]}
        results["t2"] = res
        print(f"  BUILD: status={res['status']} checkout_id={res['checkout_id']}", flush=True)
        print(f"  datadome po: {dd_after}", flush=True)


def main():
    t1()
    if results.get("t1", {}).get("status") != 200 and "--no-t2" not in sys.argv:
        # T2 tylko gdy T1 nie rozwiazal problemu (oszczedzamy prob builda)
        try:
            t2()
        except Exception as e:  # noqa: BLE001
            results["t2"] = {"error": str(e)}
            print(f"  t2 err: {e}", flush=True)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT}")


if __name__ == "__main__":
    main()
