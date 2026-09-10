"""Test determinizmu checkoutu z równoległym generowaniem dowodów wizualnych (screenshoty + raporty timingów)."""
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
from vintedbot import evidence
from vintedbot.session_state import USERS_CURRENT_URL
from vintedbot.config import IMPERSONATE, tls_kwargs
from vintedbot.json_utils import json_loads
from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"test1_determinizm_with_evidence_{int(time.time())}.json"


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
    from vintedbot.incognia_harvest import przechwyc_token_incognia
    UNLOCK_ITEM = 9859422415
    print(f"[test] samo-odblokowanie przez harvest na item={UNLOCK_ITEM}...", flush=True)
    t_unlock = time.monotonic()
    try:
        h = przechwyc_token_incognia(UNLOCK_ITEM, PROFIL)
        print(f"[test] harvest: build={h.get('status_build')} "
              f"token={'TAK' if h.get('token') else 'BRAK'} "
              f"({round(time.monotonic()-t_unlock,1)}s)", flush=True)
        harvest_cookies = h.get("cookies") or {}
        dd = harvest_cookies.get("datadome", "")
        # Używaj cookies z harvestu tylko gdy datadome jest ODBLOKOWANE (len>=150).
        # build=403 → datadome=128 (zablokowane) → _swieze_cookies() odnowi sesję.
        if h.get("status_build") == 200 and len(dd) >= 150:
            cookies = harvest_cookies
            print(f"[test] cookies z harvestu OK (datadome len={len(dd)})", flush=True)
        else:
            print(f"[test] harvest zablokowany (build={h.get('status_build')} dd_len={len(dd)}), "
                  f"odświeżam przez Camoufox...", flush=True)
            cookies = _swieze_cookies()
    except Exception as e:
        print(f"[test] błąd harvestu: {e}, pobieram świeże cookies przez Camoufox...", flush=True)
        cookies = _swieze_cookies()
    csrf = csrf_z_cookies(cookies)
    konto = KonfiguracjaKonta(cookies=cookies)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})
    # Pobierz user_id z /users/current (wymagane przez check_availability pre-filter).
    try:
        r_uc = creq.get(USERS_CURRENT_URL, headers={"Accept": "application/json"},
                        cookies=cookies, impersonate=IMPERSONATE, timeout=20, **tls_kwargs())
        if r_uc.status_code == 200:
            _ujson = json_loads(r_uc.content)
            _u = (_ujson.get("user") or {})
            _uid = _u.get("id") or _ujson.get("id")
            if _uid is not None:
                konto = konto.model_copy(update={"user_id": int(_uid)})
                print(f"[test] user_id={int(_uid)}", flush=True)
    except Exception as _e:
        print(f"[test] user_id nie pobrany: {_e!r}", flush=True)

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
        try:
            w = zrealizuj_zakup(o.id, o.seller_id, konto, proba_payment=False, profil=PROFIL,
                                detection_span=o.detection_span)
        except Exception as exc:
            print(f"[test] błąd checkoutu item={o.id}: {exc!r}", flush=True)
            continue
        total_ms = round((time.monotonic() - t0) * 1000)
        
        # Async evidence: screenshot w tle + timing report w JSON
        ev_res = evidence.zapisz_dowody_async(
            w,
            prefix=f"test1_ev_{o.id}",
            timings=True,
            screenshot=True,
            payment=False,
            profil=PROFIL,
        )
        
        wynik = w.model_dump()
        wynik["total_ms"] = total_ms
        wynik["numer"] = i + 1
        wynik["item_id"] = o.id
        wynik["seller_id"] = o.seller_id
        wynik["cache"] = dict(_COORDS_CACHE)
        wynik["evidence"] = ev_res
        wyniki.append(wynik)
        print(f"  -> build={wynik['status_build']} purchase_id={wynik['purchase_id']} total={total_ms}ms (evidence async triggered)", flush=True)
        if i < 4:
            time.sleep(2.5)  # Rate-limit safety: 0.83 req/s budget na conversations
        time.sleep(2.0)

    OUT.write_text(json.dumps(wyniki, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[test] zapisano JSON -> {OUT}", flush=True)
    
    # Czekamy chwilę na dokończenie screenshotów w tle
    print("[test] oczekiwanie na zakończenie screenshotów w tle...", flush=True)
    time.sleep(15.0)
    
    # Sprawdzamy zapisane screeny
    screens_dir = ROOT / "output" / "screens"
    found_screens = list(screens_dir.glob("test1_ev_*.png"))
    print(f"[test] znaleziono wygenerowanych screenów: {len(found_screens)}", flush=True)
    for s in found_screens[-5:]:
        print(f"  -> Screen: {s.name} ({s.stat().st_size // 1024} KB)")

    print("[test] statusy build:", [w["status_build"] for w in wyniki], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
