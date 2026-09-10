"""Jednorazowy test harvest->build na realnej ofercie z katalogu.

Pobiera pierwszą ofertę z katalogu (search=nike), potem wywołuje
zrealizuj_zakup bezpośrednio (omija monitoruj), żeby zweryfikować
czy Camoufox harvest JWE + curl_cffi build daje status 200.

UWAGA: to REALNE wywołanie rezerwacyjne na koncie użytkownika.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vintedbot.checkout import zrealizuj_zakup
from vintedbot.config import wczytaj_cookies, csrf_z_cookies
from vintedbot.detection import pobierz_oferty
from vintedbot.models import Filtry, KonfiguracjaKonta

COOKIES = ROOT / "output" / "cookies_152_export.txt"
PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"wynik_harvest_build_{int(time.time())}.json"


def _swieze_cookies_z_profilu(profil: str) -> dict[str, str]:
    """Pobiera świeże cookies z trwałego profilu Camoufox (headless)."""
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG
    with Camoufox(persistent_context=True, headless=True, user_data_dir=profil,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        raw = ctx.cookies()
    return {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}


def main() -> int:
    # 1. Świeże cookies z profilu (stare z pliku są nieważne -> 401).
    print("[test] odświeżam cookies z profilu Camoufox (headless)...")
    cookies = _swieze_cookies_z_profilu(PROFIL)
    csrf = csrf_z_cookies(cookies)
    print(f"[test] cookies: {len(cookies)}, access_token_web: {'tak' if cookies.get('access_token_web') else 'BRAK'}, csrf: {csrf or 'BRAK'}")

    konto = KonfiguracjaKonta(cookies=cookies)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})
    if cookies.get("anon_id"):
        konto = konto.model_copy(update={"anon_id": cookies["anon_id"]})

    filtry = Filtry(search_text="nike")
    oferty = pobierz_oferty(filtry, cookies=cookies)
    if not oferty:
        print("[test] brak ofert w katalogu")
        return 1
    oferta = oferty[0]
    print(f"[test] item={oferta.id} seller={oferta.seller_id} cena={oferta.cena} profil={PROFIL}")

    t0 = time.monotonic()
    w = zrealizuj_zakup(oferta.id, oferta.seller_id, konto, proba_payment=False, profil=PROFIL)
    total_ms = round((time.monotonic() - t0) * 1000)
    wynik = w.model_dump()
    wynik["total_ms"] = total_ms
    OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(wynik, indent=2, ensure_ascii=False))
    print(f"[test] zapisano -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
