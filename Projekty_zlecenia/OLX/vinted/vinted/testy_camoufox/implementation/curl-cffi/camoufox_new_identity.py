# coding: utf-8
"""camoufox_new_identity.py — czy NOWA tozsamosc (losowy fingerprint, czysty kontekst)
+ cookies z zapisanego profilu przechodza przez build na tym samym IP?

Hipoteza użytkownika: blokada jest przypieta do FINGERPRINTU zapisanego profilu
(fingerprint_preset=True = staly, rozpoznawalny przez DataDome), nie do IP.
Jesli z nowym fingerprintem build = 200 -> potwierdzenie; rozwiazanie: kazdy flow
na swiezym kontekcie z nowa tozsamoscia (cookies z profilu, bez trwalego storage).

Uzycie: python camoufox_new_identity.py [item_id]
"""
import json
import sys
import time
from pathlib import Path

from camoufox.sync_api import Camoufox, NewContext
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
# UWAGA (2026-08-30): cookies_profil.json musi zawierac datadome (skrypt _merge_datadome.py).
# Bez niego DataDome zwraca 403 na build niezaleznie od tozsamosci.
COOKIES = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))

captured = {"requests": []}


def _pick_item() -> int:
    s = cr.Session()
    for c in COOKIES:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({"accept": "application/json", "locale": "pl-PL",
                      "origin": "https://www.vinted.pl", "referer": "https://www.vinted.pl/",
                      "x-csrf-token": CSRF, "x-anon-id": ANON})
    try:
        r = s.get("https://www.vinted.pl/api/v2/catalog/items"
                  "?price_to=100&order=newest_first&page=1&per_page=40&currency=PLN",
                  impersonate=BrowserType.firefox133, timeout=30)
        for it in r.json().get("items", []):
            if it.get("status") == "sold" or it.get("is_visible") is False:
                continue
            return it["id"]
    except Exception as e:
        print(f"BLAD wyboru itemu: {e}")
    return 0


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
        captured["requests"].append(f"{req.method} {req.url[:110]}")


def main():
    item_id = int(sys.argv[1]) if len(sys.argv) > 1 else _pick_item()
    if not item_id:
        print("brak itemu (podaj: python camoufox_new_identity.py <item_id>)", flush=True)
        return

    # NOWY kontekst: bez user_data_dir (czysty profil, zero storage z profilu).
    # NewContext -> unikalny, losowy fingerprint (nowa tozsamosc) kazdego runu.
    with Camoufox(headless=True, humanize=True) as browser:
        ctx = NewContext(browser, os="windows")
        # wstrzyknij zalogowana sesje z zapisanego profilu (tylko cookies)
        ctx.add_cookies(COOKIES)
        page = ctx.new_page()
        page.on("response", on_response)
        page.on("request", on_request)
        try:
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"goto err: {e}", flush=True)
        time.sleep(6)
        # login check
        try:
            lg = page.evaluate(
                """async () => {
                    const r = await fetch('/api/v2/users/current', {headers: {'Accept': 'application/json'}});
                    const d = await r.json();
                    return {status: r.status, login: d.user?.login || d.login || null};
                }"""
            )
            print(f"LOGIN: {lg}", flush=True)
        except Exception as e:
            print(f"login err: {e}", flush=True)
        # dismiss OneTrust
        try:
            page.evaluate("""() => {
                const b = document.querySelector('#onetrust-accept-btn-handler');
                if (b) b.click();
            }""")
        except Exception:
            pass
        time.sleep(1)
        # klik Kup teraz
        for attempt in range(1, 4):
            if "status" in captured:
                break
            try:
                clicked = page.evaluate("""() => {
                    const b = document.querySelector('button[data-testid="item-buy-button"]');
                    if (!b) return false;
                    b.click();
                    return true;
                }""")
                print(f"click attempt={attempt} clicked={clicked}", flush=True)
            except Exception as e:
                print(f"click err: {e}", flush=True)
            for _ in range(100):
                if "status" in captured:
                    break
                time.sleep(0.2)
            if "status" not in captured:
                time.sleep(2)

    print(f"BUILD_STATUS={captured.get('status')} checkout_id={captured.get('checkout_id')}", flush=True)
    print(f"requesty: {captured['requests'][-6:]}", flush=True)
    (BASE_DIR / "wynik_camoufox_new_identity.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
