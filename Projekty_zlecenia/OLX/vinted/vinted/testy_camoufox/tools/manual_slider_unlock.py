# coding: utf-8
"""manual_slider_unlock.py — reczne rozwiazanie slidera DataDome (RAZ),
zeby odblokowac build/payment na flagowanym profilu (IP/fingerprint maja obnizony score).

Flow:
  1. headed + persistent profil (bez usuwania cookie - po 403 pojawi sie slider)
  2. wejdz na item, klik "Kup teraz" -> 403 + iframe geo.captcha-delivery.com (slider)
  3. CZEKA na reczne przeciagniecie slidera przez CZLOWIEKA (domyslnie do 180 s)
  4. po rozwiazaniu: reload + ponowne klikniecie "Kup teraz" -> 200
  5. zapis CZYSTEGO cookie datadome do cookies_profil.json (do uzycia przez curl)

Uzycie: python manual_slider_unlock.py [--item-id ID]
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
COOKIES_OUT = BASE_DIR / "cookies_profil.json"
OUT = BASE_DIR / "wynik_manual_slider_unlock.json"

results = {"ts": datetime.now(timezone.utc).isoformat()}


def wall():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


def _pick_item() -> dict | None:
    from curl_cffi import BrowserType, requests as cr

    cookies = json.loads(COOKIES_OUT.read_text(encoding="utf-8"))
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


def has_captcha_ctx(ctx) -> bool:
    """czy na stronie jest iframe slidera DataDome (geo.captcha-delivery.com)."""
    try:
        page = ctx.pages[0]
        return bool(page.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe'))
                .some(f => (f.src || '').includes('captcha-delivery.com'));
        }"""))
    except Exception:
        return True  # niepewnie -> traktuj jako nadal obecne


def dd_value(ctx):
    try:
        ck = ctx.cookies("https://www.vinted.pl/")
        d = next((c for c in ck if c.get("name") == "datadome"), None)
        return d["value"][:40] if d else "BRAK"
    except Exception:
        return "?"


def save_clean_cookie(ctx) -> str | None:
    """zapisz czysty datadome do cookies_profil.json (merge)."""
    try:
        ck = ctx.cookies("https://www.vinted.pl/")
        d = next((c for c in ck if c.get("name") == "datadome"), None)
    except Exception:
        d = None
    if not d:
        print("  BRAK datadome do zapisu", flush=True)
        return None
    cookies = json.loads(COOKIES_OUT.read_text(encoding="utf-8"))
    cookies = [c for c in cookies if c.get("name") != "datadome"]
    cookies.append({"name": "datadome", "value": d["value"], "domain": d.get("domain", ".vinted.pl"),
                    "path": d.get("path", "/"), "expires": int(d.get("expires", 0)),
                    "httpOnly": True, "secure": True, "sameSite": "Lax"})
    COOKIES_OUT.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ZAPISANO czyste datadome do cookies_profil.json: {d['value'][:40]}...", flush=True)
    return d["value"]


def main():
    from camoufox import Camoufox

    for lock in ("parent.lock", "lock", "lockfile"):
        p = PROFILE_DIR / lock
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    item_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if not item_id:
        item = _pick_item()
        if not item:
            results["error"] = "brak itemu"
            print("BRAK itemu")
            return
        item_id = item["id"]
    print(f"item {item_id}", flush=True)

    builds = []

    def on_response(resp):
        if resp.url.endswith("/api/v2/purchases/checkout/build"):
            entry = {"status": resp.status, "wall": wall()}
            if resp.status == 200:
                try:
                    j = resp.json()
                    entry["checkout_id"] = (j.get("checkout") or {}).get("id")
                except Exception:
                    pass
            elif resp.status == 403:
                try:
                    entry["body"] = resp.text()[:80]
                except Exception:
                    pass
            builds.append(entry)
            print(f"  BUILD#{len(builds)} status={entry['status']} {wall()}", flush=True)

    prefs = {
        "layers.acceleration.disabled": True,
        "gfx.webrender.software": True,
        "gfx.webrender.all": False,
        "gfx.canvas.accelerated": False,
        "dom.ipc.processPrelaunch.enabled": False,
    }

    with Camoufox(
        persistent_context=True,
        headless=False,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=False,
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
        time.sleep(10)
        print(f"  datadome start: {dd_value(ctx)}", flush=True)

        solved = False
        for runda in range(1, 4):
            if builds and builds[-1].get("status") == 200:
                solved = True
                break

            # klik "Kup teraz" zeby wywolac build (403 -> slider)
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

            n0 = len(builds)
            for _ in range(100):
                if len(builds) > n0:
                    break
                time.sleep(0.2)

            if builds and builds[-1].get("status") == 200:
                break

            # poczekaj az iframe slidera sie pojawi
            iframe_ok = False
            for _ in range(30):
                if has_captcha_ctx(ctx):
                    iframe_ok = True
                    break
                time.sleep(1)

            print(f"\n=== RUNA {runda}: ROZWIĄŻ SLIDER W OKNIE PRZEGLĄDARKI (przeciągnij suwak) ===", flush=True)
            print(f"    iframe captcha: {'TAK' if iframe_ok else 'NIE widac jeszcze'} | datadome={dd_value(ctx)}", flush=True)
            print("    masz do 180 s...", flush=True)

            # CZEKAJ az user rozwiąże: zniknie iframe LUB cookie sie zmieni
            t0 = time.monotonic()
            start_cookie = dd_value(ctx)
            while time.monotonic() - t0 < 180:
                if not has_captcha_ctx(ctx):
                    print(f"  [OK] iframe slidera zniknal po {int(time.monotonic()-t0)} s", flush=True)
                    break
                cur = dd_value(ctx)
                if cur != start_cookie and cur != "BRAK" and cur != "?":
                    print(f"  [OK] cookie sie zmienilo: {start_cookie} -> {cur}", flush=True)
                    break
                time.sleep(2)

            # po rozwiazaniu: odswiez i kliknij ponownie
            print(f"  reload po rozwiazaniu... datadome={dd_value(ctx)}", flush=True)
            try:
                page.reload(wait_until="commit", timeout=45000)
            except Exception as e:
                print(f"  reload err: {e}", flush=True)
            time.sleep(6)
            try:
                clicked = page.evaluate("""() => {
                    const b = document.querySelector('button[data-testid="item-buy-button"]');
                    if (!b) return false;
                    b.click();
                    return true;
                }""")
            except Exception as e:
                print(f"  click err: {e}", flush=True)
            n0 = len(builds)
            for _ in range(100):
                if len(builds) > n0:
                    break
                time.sleep(0.2)

        results["builds"] = builds
        results["item_id"] = item_id
        results["datadome_koniec"] = dd_value(ctx)

        if builds and builds[-1].get("status") == 200:
            save_clean_cookie(ctx)
            results["unlocked"] = True
            results["checkout_id"] = builds[-1].get("checkout_id")
        else:
            results["unlocked"] = False

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    statuses = [b["status"] for b in builds]
    print(f"\nWYNIK: {statuses} unlocked={results.get('unlocked')}")
    print(f"Zapisano: {OUT}")


if __name__ == "__main__":
    main()
