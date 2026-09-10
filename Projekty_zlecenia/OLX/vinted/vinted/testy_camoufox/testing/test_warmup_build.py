# coding: utf-8
"""Test: warmup Camoufoxem ze sciezka nawigacji do itemu, potem build przez curl_cffi.

Hipoteza: DataDome wymaga 'rozgrzania' sciezki items/{id} -> checkout, nie tylko strony glownej.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}-genesis-krypton-700"
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"


def warmup_and_get_cookies() -> list:
    """Warmup: strona glowna -> strona itemu (sciezka nawigacji jak uzytkownik)."""
    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
    ) as ctx:
        page = ctx.new_page()
        # 1. Strona glowna
        print("[warmup] strona glowna...")
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        # 2. Strona itemu (sciezka nawigacji)
        print(f"[warmup] strona itemu {ITEM_ID}...")
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        # 3. Eksport cookies
        raw = ctx.cookies()
        print(f"[warmup] wyeksportowano {len(raw)} cookies")
        return raw


def test_build(cookies: list, transaction_id: int) -> dict:
    """Build przez curl_cffi z cookies z warmupu."""
    s = cr.Session()
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": ITEM_URL,
    })
    H = {"x-csrf-token": CSRF, "x-anon-id": ANON}
    body = {"purchase_items": [{"id": transaction_id, "type": "transaction"}]}
    r = s.post(
        "https://www.vinted.pl/api/v2/purchases/checkout/build",
        json=body, headers=H, impersonate="firefox133", timeout=30, allow_redirects=False,
    )
    return {"status": r.status_code, "body": r.text[:500]}


def main():
    cookies = warmup_and_get_cookies()
    print("\n[test] build przez curl_cffi od razu po warmupie...")
    result = test_build(cookies, 21872241924)
    print(f"Status: {result['status']}")
    print(f"Body: {result['body'][:300]}")
    (BASE_DIR / "wynik_warmup_build.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
