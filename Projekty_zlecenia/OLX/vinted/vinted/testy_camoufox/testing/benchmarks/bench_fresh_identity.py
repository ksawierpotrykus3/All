# coding: utf-8
"""Zdobadz SWIEZY cookie datadome z czystego kontekstu i przetestuj build.

Mechanizm (z obserwacji uzytkownika - telefon incognito na tym samym WiFi dziala):
  blokada to per-KLASTER (fingerprint + cookie datadome + reputacja), nie per-IP.
  Rozwiazanie: czysty kontekst (nowy losowy fingerprint) + wstrzyknac TYLKO tokeny
  auth (bez skazonego datadome), niech DataDome sam wystawi swiezy cookie dla tego
  fingerprintu, a build wykonac w TYM SAMYM kontekscie (fetch w page).

Nie wstrzykujemy: datadome, cf_clearance - niech DataDome wyda swieze.
"""
import json
import time
from pathlib import Path

from camoufox.sync_api import Camoufox, NewContext
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# tylko tokeny auth, BEZ datadome i cf_clearance
AUTH_COOKIE_NAMES = {"access_token_web", "refresh_token_web", "anon_id",
                     "_vinted_fr_session", "v_sid", "v_uid"}

def _auth_cookies():
    raw = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
    return [c for c in raw if c.get("name") in AUTH_COOKIE_NAMES]


def _pick_item():
    s = cr.Session(impersonate=BrowserType.firefox133)
    for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({"accept": "application/json", "locale": "pl-PL",
                      "x-csrf-token": CSRF, "x-anon-id": ANON})
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?price_to=50&order=newest_first&page=1&per_page=60&currency=PLN",
              impersonate=BrowserType.firefox133, timeout=30)
    for it in r.json().get("items", []):
        u = it.get("user", {})
        if not u or it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        return it["id"]
    return None


captured = {"status": None, "checkout_id": None, "datadome_before": None, "datadome_after": None}


def on_response(resp):
    if resp.url.endswith("/api/v2/purchases/checkout/build"):
        captured["status"] = resp.status
        if resp.status == 200:
            try:
                captured["checkout_id"] = (resp.json().get("checkout") or {}).get("id")
            except Exception:
                pass


def main():
    item_id = _pick_item()
    print(f"item_id={item_id}", flush=True)
    if not item_id:
        return

    with Camoufox(headless=True, humanize=True, os="windows",
                  webgl_config=("Google Inc. (AMD)", "ANGLE (AMD, Radeon R9 200 Series Direct3D11 vs_5_0 ps_5_0)")) as browser:
        ctx = NewContext(browser, os="windows")
        auth = _auth_cookies()
        print(f"wstrzykuje {len(auth)} auth cookies (bez datadome): "
              f"{[c['name'] for c in auth]}", flush=True)
        ctx.add_cookies(auth)

        # sprawdz stan datadome przed loadem (powinno byc brak)
        before = {c["name"] for c in ctx.cookies()}
        captured["datadome_before"] = "datadome" in before
        print(f"datadome przed loadem: {captured['datadome_before']}", flush=True)

        page = ctx.new_page()
        page.on("response", on_response)

        try:
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"goto err: {e}", flush=True)
        time.sleep(6)

        # DataDome powinien wydac swiezy datadome podczas loadu itemu
        after = {c["name"]: c["value"][:20] + "..." for c in ctx.cookies() if c["name"] == "datadome"}
        captured["datadome_after"] = bool(after)
        print(f"datadome po loadzie: {'TAK' if after else 'BRAK'} {after}", flush=True)

        # login check
        try:
            lg = page.evaluate(
                "async () => { const r = await fetch('/api/v2/users/current', "
                "{headers:{'Accept':'application/json'}}); const d = await r.json(); "
                "return {status:r.status, login:d.user?.login|d.login|null}; }")
            print(f"LOGIN: {lg}", flush=True)
        except Exception as e:
            print(f"login err: {e}", flush=True)

        # klik Kup teraz (prawdziwy frontend -> build w tym samym kontekscie)
        for attempt in range(1, 4):
            if captured["status"] is not None:
                break
            try:
                clicked = page.evaluate(
                    "() => { const b = document.querySelector('button[data-testid=\"item-buy-button\"]'); "
                    "if (!b) return false; b.click(); return true; }")
                print(f"click attempt={attempt} clicked={clicked}", flush=True)
            except Exception as e:
                print(f"click err: {e}", flush=True)
            for _ in range(100):
                if captured["status"] is not None:
                    break
                time.sleep(0.2)
            if captured["status"] is None:
                time.sleep(2)

    print(f"BUILD_STATUS={captured.get('status')} checkout_id={captured.get('checkout_id')}", flush=True)
    (BASE_DIR / "wynik_fresh_identity.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()