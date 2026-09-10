# coding: utf-8
"""camoufox_challenge_retry.py — czy 403 na build to przejsciowe WYZWANIE DataDome,
ktore przegladarka rozwiazuje po chwili, czy trwaly per-IP rate limit?

Test: persistent profil Camoufox, strona itemu -> klik "Kup teraz".
Po kazdym 403 CZEKAMY na wykonanie JS challenge (cookie datadome sie zmienia)
i klikamy PONOWNIE (az do 3 prob). Jesli ktorys retry -> 200: to challenge,
nie rate limit (uzytkownik ma racje). Jesli wszystkie 403 -> per-IP limit/bot-detekcja.

Rejestruje: statusy WSZYSTKICH buildow, wartosc datadome przed/po kazdym kliku,
czy strona przekierowala na geo.captcha-delivery.com, iframe captcha.

Uzycie: python camoufox_challenge_retry.py
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_camoufox_challenge_retry.json"

results = {"ts": datetime.now(timezone.utc).isoformat()}


def _pick_item() -> dict | None:
    cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
    s = cr.Session()
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({"accept": "application/json", "locale": "pl-PL",
                      "origin": "https://www.vinted.pl", "referer": "https://www.vinted.pl/",
                      "x-csrf-token": CSRF, "x-anon-id": ANON})
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?price_to=100&order=newest_first&page=1&per_page=40&currency=PLN",
              impersonate=BrowserType.firefox133, timeout=30)
    for it in r.json().get("items", []):
        if it.get("status") != "sold" and it.get("is_visible") is not False:
            return it
    return None


def main():
    from camoufox import Camoufox

    headed = "--headed" in sys.argv
    fresh = "--fresh" in sys.argv
    print(f"MODE: {'HEADED' if headed else 'HEADLESS'} | fresh_cookie={fresh}", flush=True)

    for lock in ("parent.lock", "lock", "lockfile"):
        p = PROFILE_DIR / lock
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    if fresh:
        # skasuj spalone cookie datadome -> przegladarka dostanie swieze od DataDome
        import sqlite3

        db = PROFILE_DIR / "cookies.sqlite"
        if db.exists():
            conn = sqlite3.connect(str(db))
            n = conn.execute("DELETE FROM moz_cookies WHERE name='datadome'").rowcount
            conn.commit()
            conn.close()
            print(f"FRESH: usunieto {n} cookie datadome", flush=True)

    item = _pick_item()
    if not item:
        results["error"] = "brak itemu"
        print("BRAK itemu")
        return
    item_id = item["id"]
    print(f"item {item_id} ({item.get('title', '')[:45]})", flush=True)

    builds = []

    def on_response(resp):
        if resp.url.endswith("/api/v2/purchases/checkout/build"):
            entry = {"status": resp.status, "wall": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"}
            if resp.status == 200:
                try:
                    j = resp.json()
                    entry["checkout_id"] = (j.get("checkout") or {}).get("id")
                except Exception:
                    pass
            elif resp.status == 403:
                try:
                    body = resp.text()[:120]
                    entry["body"] = body
                except Exception:
                    pass
            builds.append(entry)
            print(f"  BUILD#{len(builds)} status={entry['status']}", flush=True)

    def dd_value(ctx):
        try:
            ck = ctx.cookies("https://www.vinted.pl/")
            d = next((c for c in ck if c.get("name") == "datadome"), None)
            return d["value"][:40] if d else "BRAK"
        except Exception:
            return "?"

    prefs = {}
    if headed:
        # headed na Windows: wymus soft render (kompozytor GPU sie wywala -> AbnormalShutdown)
        prefs = {
            "layers.acceleration.disabled": True,
            "gfx.webrender.software": True,
            "gfx.webrender.all": False,
            "gfx.canvas.accelerated": False,
            "dom.ipc.processPrelaunch.enabled": False,
        }

    with Camoufox(
        persistent_context=True,
        headless=not headed,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
        firefox_user_prefs=prefs,
        i_know_what_im_doing=True,
    ) as ctx:
        page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"goto err: {e}", flush=True)
        time.sleep(12)  # czas na wstepny JS DataDome
        print(f"  datadome start: {dd_value(ctx)}", flush=True)

        for attempt in range(1, 4):
            if builds and builds[-1].get("status") == 200:
                break
            try:
                clicked = page.evaluate("""() => {
                    const b = document.querySelector('button[data-testid="item-buy-button"]');
                    if (!b) return false;
                    b.click();
                    return true;
                }""")
            except Exception as e:
                print(f"  click err: {e}", flush=True)
                clicked = False
            print(f"  klik#{attempt} clicked={clicked} datadome_przed={dd_value(ctx)}", flush=True)

            # czekaj na odpowiedz build (max 20 s)
            n0 = len(builds)
            for _ in range(100):
                if len(builds) > n0:
                    break
                time.sleep(0.2)

            if builds and builds[-1].get("status") == 200:
                break

            # po 403: czekaj na rozwiazanie challenge JS (cookie sie rotuje)
            print(f"  czekam na challenge JS (20 s)...", flush=True)
            for _ in range(5):
                time.sleep(4)
                print(f"    datadome_po {4 * (_ + 1)}s: {dd_value(ctx)}", flush=True)

            # czy strona poszla na captcha? czy iframe?
            try:
                diag = page.evaluate("""() => {
                    const ifr = Array.from(document.querySelectorAll('iframe')).map(f => (f.src || '').slice(0, 70));
                    return {url: location.href, ddCaptcha: !!document.querySelector('.datadome-captcha'),
                            iframes: ifr};
                }""")
                print(f"  DIAG: {json.dumps(diag, ensure_ascii=False)[:400]}", flush=True)
            except Exception:
                pass

        results["builds"] = builds
        results["item_id"] = item_id
        results["datadome_koniec"] = dd_value(ctx)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    statuses = [b["status"] for b in builds]
    print(f"\nWYNIK: {statuses}")
    print(f"Zapisano: {OUT}")


if __name__ == "__main__":
    main()
