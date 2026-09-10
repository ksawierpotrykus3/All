"""Debug: co dokładnie zwraca POST /api/v2/conversations (pełna odpowiedź)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from curl_cffi import requests as creq
from vintedbot.config import CONVERSATIONS_URL, csrf_z_cookies, tls_kwargs, IMPERSONATE
from vintedbot.detection import pobierz_oferty
from vintedbot.models import Filtry, KonfiguracjaKonta

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = ROOT / "output" / f"conv_resp_{int(time.time())}.json"


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

    r = creq.post(
        CONVERSATIONS_URL,
        json={"initiator": "buy", "item_id": int(o.id), "opposite_user_id": int(o.seller_id)},
        headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "X-CSRF-Token": konto.csrf, "x-anon-id": konto.anon_id,
            "Origin": "https://www.vinted.pl", "Referer": "https://www.vinted.pl/",
        },
        cookies=konto.cookies, impersonate=IMPERSONATE, **tls_kwargs(), timeout=30,
    )
    wynik = {"status": r.status_code, "body": r.text[:3000], "item": o.id}
    OUT.write_text(json.dumps(wynik, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(wynik, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
