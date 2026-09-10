"""Test 1 (PLAN_TESTY_DATADOME): determinizm build=200 w petli (H-A).

N=5 kolejnych zrealizuj_zakup (dry-run bez payment) na 5 ROZNYCH ofertach —
retry tej samej oferty idzie przez SKIP-BUILD (conversations zwraca
purchase_id != null), wiec nie mierzy build. Rozne oferty = pelny build kazda.

Kryterium sukcesu: 5/5 status_build=200, bez 403.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vintedbot.checkout import zrealizuj_zakup, _COORDS_CACHE, prewarm_sesje
from vintedbot.config import csrf_z_cookies
from vintedbot.detection import pobierz_oferty
from vintedbot.models import Filtry, KonfiguracjaKonta

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"test1_determinizm_{int(time.time())}.json"


def _swieze_cookies() -> dict:
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG
    from vintedbot.slider_solver import rozwiaz_slider
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        # Auto-unlock: jeśli profil ma wygasłe odblokowanie DataDome, challenge
        # pojawia się jako iframe captcha-delivery.com -> rozwiąż slider i kontynuuj.
        for fr in getattr(page, "frames", []):
            if "captcha-delivery.com" in (getattr(fr, "url", "") or ""):
                print("[test] wykryto slider DataDome, próba rozwiązania...", flush=True)
                try:
                    rozwiaz_slider(page)
                except Exception as e:
                    print(f"[test] błąd slider_solver: {e}", flush=True)
                break
        raw = ctx.cookies()
    return {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}


def main() -> int:
    # 1) Samo-odblokowanie: harvest na znanym dobrym itemie (buy=1 wg probe6,
    #    2026-09-01). UWAGA: JEDEN harvest — każdy klik "Kup teraz" w przeglądarce
    #    robi POST conversations i zużywa limit rate-limit (code 106); zbyt wiele
    #    harvestów z fallbackiem spala limit i kolejne próby dostają 429
    #    (obserwacja test v5: 6 harvestów -> 5/5 rate_limit_exceeded).
    #    To NIE jest część mierzonego checkoutu — to koszt "zimnego startu".
    from vintedbot.incognia_harvest import przechwyc_token_incognia
    UNLOCK_ITEM = 9859422415  # buy=1 wg probe6 (9859424771 został sprzedany)
    print(f"[test] samo-odblokowanie przez harvest na item={UNLOCK_ITEM}...", flush=True)
    t_unlock = time.monotonic()
    h = przechwyc_token_incognia(UNLOCK_ITEM, PROFIL)
    print(f"[test] harvest: build={h.get('status_build')} "
          f"token={'TAK' if h.get('token') else 'BRAK'} "
          f"({round(time.monotonic()-t_unlock,1)}s)", flush=True)
    cookies = h.get("cookies") or _swieze_cookies()
    csrf = csrf_z_cookies(cookies)
    konto = KonfiguracjaKonta(cookies=cookies)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})

    oferty = pobierz_oferty(Filtry(search_text="nike"), cookies=cookies, limit=15)
    if len(oferty) < 5:
        print(f"[test] za malo ofert: {len(oferty)}", flush=True)
        return 1

    print("[test] pre-warm sesji...", flush=True)
    prewarm_sesje(konto)
    print("[test] sesje gotowe", flush=True)

    wyniki = []
    for i, o in enumerate(oferty[:5]):
        print(f"[test] proba {i+1}/5: item={o.id} seller={o.seller_id}", flush=True)
        t0 = time.monotonic()
        # dry-run: bez payment (proba_payment=False) — cel: status_build.
        # profil=PROFIL: auto-unlock na build=403 (checkout.py: odblokuj przez slider i ponów).
        w = zrealizuj_zakup(o.id, o.seller_id, konto, proba_payment=False, profil=PROFIL)
        total_ms = round((time.monotonic() - t0) * 1000)
        wynik = w.model_dump()
        wynik["total_ms"] = total_ms
        wynik["numer"] = i + 1
        wynik["item_id"] = o.id
        wynik["seller_id"] = o.seller_id
        wynik["cache"] = dict(_COORDS_CACHE)
        wyniki.append(wynik)
        print(f"  -> build={wynik['status_build']} "
              f"purchase_id={wynik['purchase_id']} total={total_ms}ms", flush=True)
        time.sleep(2.0)  # przerwa miedzy probami (jak w planie)

    OUT.write_text(json.dumps(wyniki, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[test] zapisano -> {OUT}", flush=True)
    print("[test] statusy build:", [w["status_build"] for w in wyniki], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
