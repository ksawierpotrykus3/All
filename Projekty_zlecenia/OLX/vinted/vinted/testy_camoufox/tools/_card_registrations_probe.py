# coding: utf-8
"""_card_registrations_probe.py — znajduje wlasciwy URL card_registrations.

Testuje rozne kandydaty host/sciezke w zywej sesji przegladarki (Camoufox).
Szukamy statusu != 404 (200/403/400) = endpoint istnieje.
"""
import json
import time
from pathlib import Path

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
OUT_JSON = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_card_registrations_probe.json")

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

CANDIDATES = [
    "https://www.vinted.pl/api/v2/payments/public/api/card_registrations",
    "https://www.vinted.pl/payments/public/api/card_registrations",
    "https://www.vinted.pl/api/v2/payments/card_registrations",
    "https://www.vinted.pl/api/v2/card_registrations",
]

results = []


def log(m):
    print("[PROBE] " + m, flush=True)


def main():
    from camoufox import Camoufox

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
        # odswiez sesje
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "locale": "pl-PL",
            "x-csrf-token": CSRF,
            "x-anon-id": ANON,
            "origin": "https://www.vinted.pl",
            "referer": "https://www.vinted.pl/",
        }

        for url in CANDIDATES:
            t0 = time.monotonic()
            r = ctx.request.post(url, data=json.dumps({"card_registration": None}), headers=headers)
            ms = round((time.monotonic() - t0) * 1000)
            body = ""
            try:
                body = r.body()[:200].decode("utf-8", "ignore")
            except Exception:
                pass
            results.append({"url": url, "status": r.status, "ms": ms, "body": body})
            log("POST %-70s -> %d (%d ms)" % (url, r.status, ms))

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log("SAVED -> " + str(OUT_JSON))


if __name__ == "__main__":
    main()
