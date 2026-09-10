"""Test: czy build+payment wystarczy BEZ osobnego pickup_point/pickup_details?

Przeglądarka robi TYLKO: conversations -> build -> 1x PUT (puste komponenty) -> payment.
Nie ma osobnego GET pickup_point ani PUT pickup_details. Sprawdzamy czy Vinted
sam wybiera punkt odbioru i czy payment przechodzi bez ręcznego ustawiania pickup.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vintedbot.checkout import _build, _payment, _put_payment_method, _nowa_sesja, _find_checksum
from vintedbot.config import csrf_z_cookies
from vintedbot.detection import pobierz_oferty, utworz_transakcje
from vintedbot.models import Filtry, KonfiguracjaKonta

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"minimal_checkout_{int(time.time())}.json"


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
    csrf = csrf_z_cookies(cookies)
    konto = KonfiguracjaKonta(cookies=cookies)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})

    oferty = pobierz_oferty(Filtry(search_text="nike"), cookies=cookies)
    if not oferty:
        return 1
    o = oferty[0]
    wynik = {"item": o.id, "err": None, "timings": {}}

    try:
        with _nowa_sesja(konto) as s:
            t0 = time.monotonic()
            txn = utworz_transakcje(o.id, o.seller_id, konto)
            wynik["timings"]["transaction"] = round((time.monotonic() - t0) * 1000)
            wynik["txn"] = txn

            t0 = time.monotonic()
            r_build = _build(s, int(txn), "", konto)
            wynik["timings"]["build"] = round((time.monotonic() - t0) * 1000)
            wynik["build"] = r_build.status_code

            bj = r_build.json()
            checkout = bj.get("checkout") or {}
            cid = checkout.get("id")
            wynik["checkout_id"] = cid
            # Co build już zwraca o pickup?
            comps = checkout.get("components") or {}
            spd = comps.get("shipping_pickup_details") or {}
            wynik["build_pickup_details"] = spd
            checksum = (_find_checksum(bj) or [""])[0]

            # 1x PUT puste komponenty (jak przeglądarka)
            t0 = time.monotonic()
            r_put = _put_payment_method(s, cid)
            wynik["timings"]["put_puste"] = round((time.monotonic() - t0) * 1000)
            wynik["put"] = r_put.status_code
            if r_put.status_code == 200:
                checksum = (_find_checksum(r_put.json()) or [""])[0] or checksum
                # Czy po PUT jest wybrany pickup point?
                pj = r_put.json()
                spd2 = ((pj.get("checkout") or {}).get("components") or {}).get("shipping_pickup_details") or {}
                wynik["put_pickup_details"] = spd2

            # Payment
            t0 = time.monotonic()
            r_pay = _payment(s, cid, checksum)
            wynik["timings"]["payment"] = round((time.monotonic() - t0) * 1000)
            wynik["payment"] = r_pay.status_code
            wynik["payment_body"] = r_pay.text[:800]
    except Exception as e:
        wynik["err"] = str(e)
    finally:
        OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(wynik, indent=2, ensure_ascii=False)[:3500], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
