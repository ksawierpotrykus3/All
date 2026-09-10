# coding: utf-8
"""Test: nagłówki web vs app na checkout/build (tworzy checkout — używaj świadomie).

Porównuje PEŁNY flow: conversations -> checkout/build, dla dwóch różnych itemów:
  - item A: nagłówki web
  - item B: nagłówki app (X-Platform: android + X-App-Version + X-V-Udt + X-Device-UUID...)

Cel: czy na checkout/build backend traktuje requesty "app" inaczej (szybciej / inna odpowiedź).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from curl_cffi import requests as creq
from vintedbot.config import (
    tls_kwargs, csrf_z_cookies, CSRF_DEFAULT, ANON_DEFAULT,
    CONVERSATIONS_URL, BUILD_URL,
)
from vintedbot.detection import pobierz_oferty
from vintedbot.models import Filtry

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"wynik_headers_build_app_vs_web_{int(time.time())}.json"

APP_VERSION = "26.33.1"
APP_HEADERS = {
    "X-Platform": "android",
    "X-App-Version": APP_VERSION,
    "X-OS-Version": "15",
    "X-Device-Model": "Pixel 8",
    "X-Screen-Width": "1080",
    "X-Screen-Height": "2400",
    "X-Device-UUID": "0123456789abcdef0123456789abcdef",
}


def _swieze_cookies() -> dict:
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        raw = ctx.cookies()
    return {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}


def _run(cookies, item_id, seller_id, variant):
    csrf = csrf_z_cookies(cookies) or CSRF_DEFAULT
    anon = cookies.get("anon_id") or ANON_DEFAULT
    v_udt = cookies.get("v_udt", "")

    extra = {} if variant == "web" else dict(APP_HEADERS)
    base = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
        "x-anon-id": anon,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    if variant == "app" and v_udt:
        base["X-V-Udt"] = v_udt
    base.update(extra)

    s = creq.Session(headers=base, cookies=cookies, impersonate="firefox135", timeout=30)

    # 1. conversations
    t0 = time.monotonic()
    r = s.post(CONVERSATIONS_URL,
               json={"initiator": "buy", "item_id": int(item_id), "opposite_user_id": int(seller_id)},
               **tls_kwargs())
    t_conv = round((time.monotonic() - t0) * 1000)
    if r.status_code != 200:
        return {"variant": variant, "item_id": item_id, "conv_status": r.status_code,
                "conv_ms": t_conv, "conv_body": r.text[:300]}
    data = r.json()
    conv = data.get("conversation") or {}
    txn_obj = conv.get("transaction") or {}
    txn_id = data.get("transaction_id") or txn_obj.get("id") or conv.get("transaction_id")

    # 2. checkout/build
    t0 = time.monotonic()
    r2 = s.post(BUILD_URL,
                json={"purchase_items": [{"id": int(txn_id), "type": "transaction"}]},
                **tls_kwargs())
    t_build = round((time.monotonic() - t0) * 1000)
    body = r2.text
    checkout_id = None
    try:
        j = r2.json()
        checkout_id = ((j.get("checkout") or {}).get("id"))
    except Exception:
        pass
    return {"variant": variant, "item_id": item_id, "txn_id": txn_id,
            "conv_status": r.status_code, "conv_ms": t_conv,
            "build_status": r2.status_code, "build_ms": t_build,
            "checkout_id": checkout_id, "build_body_head": body[:300]}


def main() -> int:
    import traceback
    LOG = Path(r"F:\PROJEKTY\vinted\bot\output\_build_headers_log.txt")
    def log(m):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(m + "\n")
        print(m, flush=True)

    try:
        log("krok1: swieze cookies")
        cookies = _swieze_cookies()
        log("krok2: pobierz oferty")
        oferty = pobierz_oferty(Filtry(search_text="nike"), cookies=cookies)
        log(f"krok3: ofert={len(oferty)}")
        if len(oferty) < 2:
            log("[test] za mało ofert")
            return 1

        a, b = oferty[0], oferty[1]
        log(f"web item={a.id} seller={a.seller_id}")
        log(f"app item={b.id} seller={b.seller_id}")

        wyniki = [
            _run(cookies, a.id, a.seller_id, "web"),
            _run(cookies, b.id, b.seller_id, "app"),
        ]

        for w in wyniki:
            log(json.dumps(w, ensure_ascii=False, indent=2))

        OUT.write_text(json.dumps(wyniki, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"[test] zapisano -> {OUT}")
        return 0
    except Exception as e:
        log("EXCEPTION: " + repr(e))
        log(traceback.format_exc())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())