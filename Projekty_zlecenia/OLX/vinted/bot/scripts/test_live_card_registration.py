"""Skrypt diagnostyczny do testowania rejestracji karty na żywej sesji Vinted.

Użycie:
  python bot/scripts/test_live_card_registration.py --number "4111..." --exp-month 12 --exp-year 2026 --cvc 123
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vintedbot.card_manager import zarejestruj_karte, pobierz_zapisane_karty
from vintedbot.config import wczytaj_cookies, csrf_z_cookies
from vintedbot.models import KonfiguracjaKonta

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT_DIR = ROOT / "output"


def _pobierz_swieze_cookies() -> dict:
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG
    print("[1/3] Pobieranie świeżych cookies z profilu...")
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        raw = ctx.cookies()
    return {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}


def main():
    parser = argparse.ArgumentParser(description="Test rejestracji karty przez Adyen CSE")
    parser.add_argument("--number", required=True, help="Numer karty")
    parser.add_argument("--exp-month", required=True, help="Miesiąc MM")
    parser.add_argument("--exp-year", required=True, help="Rok YYYY")
    parser.add_argument("--cvc", required=True, help="CVC")
    parser.add_argument("--single-use", action="store_true", help="Karta jednorazowa")
    args = parser.parse_args()

    cookies = _pobierz_swieze_cookies()
    konto = KonfiguracjaKonta(cookies=cookies)
    csrf = csrf_z_cookies(cookies)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})

    print(f"[2/3] Sprawdzanie istniejących kart na koncie...")
    try:
        istniejace = pobierz_zapisane_karty(konto)
        print(f"Liczba zapisanych kart: {len(istniejace)}")
    except Exception as e:
        print(f"Błąd pobierania kart: {e}")

    karta = {
        "number": args.number.replace(" ", "").replace("-", ""),
        "expiryMonth": str(args.exp_month).zfill(2),
        "expiryYear": str(args.exp_year),
        "cvc": str(args.cvc),
    }

    print(f"[3/3] Szyfrowanie przez Adyen CSE i wysyłanie do API...")
    t0 = time.time()
    try:
        wynik = zarejestruj_karte(karta, konto, single_use=args.single_use)
        dt = (time.time() - t0) * 1000
        print(f"SUKCES w {dt:.1f}ms! Odpowiedź serwera: {json.dumps(wynik, indent=2, ensure_ascii=False)}")
        
        out_file = OUT_DIR / f"wynik_rejestracji_karty_{int(time.time())}.json"
        out_file.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Zapisano dowód w {out_file}")
    except Exception as e:
        print(f"BŁĄD rejestracji: {e}")


if __name__ == "__main__":
    main()
