# coding: utf-8
"""Cleanse — nowa sesja/tozsamosc, zdobycie swiezego datadome przez REALNY flow kupna.

Sekwencja (dokladnie jak uzytkownik na telefonie):
  1. otworz trwaly profil (zaladowany maksks0)
  2. wejdz na swiezy produkt
  3. kliknij "Kup teraz" (prawdziwy frontend -> conversations + build + wydanie datadome)
  4. po przejsciu builda wyeksportuj cookies (w tym swiezy datadome) do cookies_profil.json
  5. ten swiezy datadome + odzyskana reputacja IP/konta ma odblokowac stary flow

Tryb headed=False w testach mial problem z datadome; tu uzywamy persistent headless
z cieplym profilem, ale klik realnym przyciskiem (nie evaluate-click).
"""
import json
import sys
import time
from pathlib import Path

from camoufox.sync_api import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
OUT = BASE_DIR / "cookies_profil.json"

captured = {"build_status": None, "datadome_before": None, "datadome_after": None}


def on_response(resp):
    if resp.url.endswith("/api/v2/purchases/checkout/build"):
        captured["build_status"] = resp.status


def _pick_item():
    # szybki wybor itemu z katalogu przez curl (publiczny GET, bez ryzyka)
    from curl_cffi import requests as cr, BrowserType
    s = cr.Session(impersonate=BrowserType.firefox133)
    for c in json.loads(OUT.read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    r = s.get("https://www.vinted.pl/api/v2/catalog/items"
              "?price_to=50&order=newest_first&page=1&per_page=60&currency=PLN",
              impersonate=BrowserType.firefox133, timeout=30)
    for it in r.json().get("items", []):
        u = it.get("user", {})
        if not u or it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        return it["id"]
    return None


def main():
    item_id = sys.argv[1] if len(sys.argv) > 1 else _pick_item()
    print(f"item_id={item_id}", flush=True)
    if not item_id:
        return

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        webgl_config=("Google Inc. (AMD)", "ANGLE (AMD, Radeon R9 200 Series Direct3D11 vs_5_0 ps_5_0)"),
    ) as ctx:
        page = ctx.new_page()
        page.on("response", on_response)

        before = {c["name"] for c in ctx.cookies()}
        captured["datadome_before"] = "datadome" in before
        print(f"datadome przed: {captured['datadome_before']}", flush=True)

        try:
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"goto err: {e}", flush=True)
        time.sleep(6)

        # klik Kup teraz REALNYM locatorem (isTrusted), jak frontend
        for attempt in range(1, 4):
            if captured["build_status"] is not None:
                break
            try:
                btn = page.locator('button[data-testid="item-buy-button"]').first
                if btn.is_visible(timeout=5000):
                    btn.click(timeout=10000)
                    print(f"click attempt={attempt}", flush=True)
                else:
                    print(f"click attempt={attempt}: button not visible", flush=True)
            except Exception as e:
                print(f"click err: {e}", flush=True)
            for _ in range(100):
                if captured["build_status"] is not None:
                    break
                time.sleep(0.2)
            if captured["build_status"] is None:
                time.sleep(2)

        after = {c["name"] for c in ctx.cookies()}
        captured["datadome_after"] = "datadome" in after
        print(f"datadome po: {captured['datadome_after']} build={captured['build_status']}", flush=True)

        # eksport cookies
        cookies = []
        for c in ctx.cookies():
            cookies.append({
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": c.get("sameSite", "Lax"),
            })
        OUT.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        dd = [c for c in cookies if c["name"] == "datadome"]
        print(f"zapisano {len(cookies)} cookies, datadome={dd[0]['value'][:25] if dd else 'BRAK'}...", flush=True)

    (BASE_DIR / "wynik_cleanse.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()