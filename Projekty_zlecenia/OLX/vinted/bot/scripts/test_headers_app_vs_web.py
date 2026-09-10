# coding: utf-8
"""Test: czy nagłówki "app" (Android) zmieniają odpowiedź backendu vs nagłówki "web".

Porównuje ten sam request (GET /users/current) z:
  1. nagłówkami web   (jak obecny bot)
  2. nagłówkami app    (X-Platform: android, X-App-Version, X-V-Udt, ...)

Bezpieczny endpoint: users/current — nie tworzy transakcji, zero ryzyka bana.
Cel: rozstrzygnąć hipotezę, czy backend "ufa" requestom z sygnaturą aplikacji.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vintedbot.config import tls_kwargs, csrf_z_cookies, CSRF_DEFAULT, ANON_DEFAULT

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"wynik_headers_app_vs_web_{int(time.time())}.json"

# Wersja APK z dekompilacji (ANALIZA_APK_VINTED_26_33_1.md)
APP_VERSION = "26.33.1"

# Wartości nagłówków app z interceptorów (HeadersInterceptor / ApiHeadersInterceptor / ...).
# X-Device-UUID jest MD5 urządzenia (nie znamy składników -> wstawiamy placeholder do testu).
APP_HEADERS = {
    "X-Platform": "android",
    "X-App-Version": APP_VERSION,
    "X-OS-Version": "15",                 # placeholder (Build.VERSION.RELEASE)
    "X-Device-Model": "Pixel 8",          # placeholder (Build.MODEL)
    "X-Screen-Width": "1080",             # placeholder
    "X-Screen-Height": "2400",            # placeholder
    "X-Device-UUID": "0123456789abcdef0123456789abcdef",  # placeholder MD5 (klientowo generowany)
    "X-Local-Time": str(int(time.time() * 1000)),
}

WEB_HEADERS = {
    "X-Platform": "web",  # kontrolna wartość (backend rozróżnia po tym)
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


def main() -> int:
    cookies = _swieze_cookies()
    csrf = csrf_z_cookies(cookies) or CSRF_DEFAULT
    anon = cookies.get("anon_id") or ANON_DEFAULT
    v_udt = cookies.get("v_udt", "")

    from curl_cffi import requests as creq

    # Bazowe nagłówki wspólne (jak w config bota)
    base = {
        "Accept": "application/json",
        "X-CSRF-Token": csrf,
        "x-anon-id": anon,
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }

    results = []

    for label, extra in [("web", WEB_HEADERS), ("app", APP_HEADERS)]:
        s = creq.Session(headers={**base, **extra}, cookies=cookies,
                         impersonate="firefox135", timeout=30)
        # dodaj X-V-Udt (device token z cookies) tylko przy wariancie app
        if label == "app" and v_udt:
            s.headers["X-V-Udt"] = v_udt

        url = "https://www.vinted.pl/api/v2/users/current"
        t0 = time.monotonic()
        try:
            r = s.get(url, **tls_kwargs())
            dt_ms = round((time.monotonic() - t0) * 1000)
            entry = {
                "variant": label,
                "status": r.status_code,
                "ms": dt_ms,
                "body_head": r.text[:200],
            }
            print(f"\n[{label}] status={r.status_code} | {dt_ms} ms")
            print(f"  {r.text[:200]}")
        except Exception as e:
            entry = {"variant": label, "error": repr(e)}
            print(f"\n[{label}] BLAD: {e!r}")
        results.append(entry)

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[test] zapisano -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())