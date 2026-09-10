"""Test check_availability (batch pre-filter) — bez Incognii, bez checkoutu.

Z APK: GatewayCheckoutApi.checkItemsAvailability
  @POST("checkout/purchases/check_availability")
  body: {buyerId, itemIds[]}  (batch)

Cel: sprawdzić czy endpoint przyjmuje batch i zwraca Purchase/Reservation/MarkAsSold
bez kosztu conversations. Idealny pre-filter pollera.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vintedbot.config import (
    tls_kwargs,
    csrf_z_cookies,
    CSRF_DEFAULT,
    ANON_DEFAULT,
)
from vintedbot.detection import pobierz_oferty
from vintedbot.models import Filtry

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"wynik_check_availability_{int(time.time())}.json"

# Nasze konto (kupujacy) — z /users/current (id 3180346878)
BUYER_ID = "3180346878"

# Kandydaci na bazowy host gateway (z dekompilacji: vintedGatewayApiFactory).
URLS = [
    "https://api.vinted.pl/checkout/purchases/check_availability",
    "https://www.vinted.pl/api/v2/checkout/purchases/check_availability",
]


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


def main() -> int:
    cookies = _swieze_cookies()
    csrf = csrf_z_cookies(cookies) or CSRF_DEFAULT
    anon = cookies.get("anon_id") or ANON_DEFAULT

    from curl_cffi import requests as creq
    s = creq.Session(
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "x-anon-id": anon,
            "Origin": "https://www.vinted.pl",
            "Referer": "https://www.vinted.pl/",
        },
        cookies=cookies,
        impersonate="firefox135",
        timeout=30,
    )

    # Pobierz kilka ofert (batch do sprawdzenia).
    oferty = pobierz_oferty(Filtry(search_text="nike"), cookies=cookies)
    if not oferty:
        print("[test] brak ofert", flush=True)
        return 1
    item_ids = [str(o.id) for o in oferty[:5]]
    print(f"[test] item_ids={item_ids}", flush=True)

    wyniki = []
    for url in URLS:
        # Serwer (400 "item_ids must not be empty") wymaga snake_case, mimo że w APK pola są camelCase.
        body = {"buyer_id": BUYER_ID, "item_ids": item_ids}
        t0 = time.monotonic()
        try:
            r = s.post(url, json=body, **tls_kwargs())
            dt_ms = round((time.monotonic() - t0) * 1000)
            entry = {"url": url, "status": r.status_code, "ms": dt_ms,
                     "body_head": r.text[:800]}
            print(f"\n[check_availability] {url}\n  http={r.status_code} | {dt_ms} ms\n  {r.text[:800]}", flush=True)
        except Exception as e:
            entry = {"url": url, "error": repr(e)}
            print(f"\n[check_availability] {url}\n  BLAD: {e!r}", flush=True)
        wyniki.append(entry)

    OUT.write_text(json.dumps(wyniki, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[test] zapisano -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())