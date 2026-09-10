"""Przechwyć PRAWDZIWY flow checkoutu OLX (BuyWithDelivery) w przeglądarce.

WYMAGA ŚWIEŻEJ SESJI — access_token OLX ma TTL ~15 min. Skrypt wspiera:
  1) podane cookies (jeśli świeże) → headless z przechwytywaniem,
  2) tryb ręcznego logowania (headed) → użytkownik loguje się, potem skrypt
     przechwytuje flow checkoutu.

Przechwytuje WSZYSTKIE requesty/response do domen olx.pl (i pokrewnych),
zapisuje do `dane/checkout_capture.json`. To jest źródło prawdy dla portu
architektury Vinted → OLX (detection → checkout → payment).
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
COOKIES_PATH = BASE / "dane" / "cookies.txt"
OUT_PATH = BASE / "dane" / "checkout_capture.json"

# Oferta testowa z delivery.rock.active=true (z dane/oferty_z_dostawa.json)
OFFER_ID = 1084508890
OFFER_URL = f"https://www.olx.pl/delivery/checkout/{OFFER_ID}/"

# Domeny, których ruch nas interesuje (API)
API_DOMAIN_PARTS = ("olx.pl", "payu", "payu.com", "cognito", "amazonaws", "rock")


def load_cookies_netscape(path: Path) -> list:
    """Netscape cookie file → lista słowników dla Playwright."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 7:
            out.append({
                "name": p[5],
                "value": p[6],
                "domain": p[0],
                "path": p[2],
                "secure": p[3] == "TRUE",
            })
    return out


def is_api(url: str) -> bool:
    low = url.lower()
    if not any(d in low for d in API_DOMAIN_PARTS):
        return False
    # pomiń statyczne zasoby
    if any(ext in low for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".ico")):
        return False
    return True


def capture(cookies: list, headed: bool):
    captured = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        if cookies:
            ctx.add_cookies(cookies)
        page = ctx.new_page()

        def on_response(resp):
            if not is_api(resp.url):
                return
            req = resp.request
            entry = {
                "ts": time.time(),
                "method": req.method,
                "url": req.url,
                "req_headers": dict(req.headers),
                "post_data": req.post_data,
                "status": resp.status,
            }
            try:
                body = resp.text()
                if body and (body.lstrip().startswith(("{", "[")) or len(body) < 5000):
                    try:
                        entry["resp_json"] = resp.json()
                    except Exception:
                        entry["resp_text"] = body[:5000]
            except Exception as e:
                entry["resp_error"] = str(e)
            captured.append(entry)
            print(f"[{req.method}] {resp.status} {req.url}")

        page.on("response", on_response)

        print(f"[*] Otwieram checkout: {OFFER_URL}")
        page.goto(OFFER_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        shot = BASE / "dane" / "checkout_page.png"
        page.screenshot(path=str(shot))
        print(f"[+] Zrzut: {shot}")

        try:
            buttons = page.eval_on_selector_all(
                "button, a[role='button'], [data-testid]",
                "els => els.slice(0,40).map(e => ({t: e.textContent.trim().slice(0,80), d: e.getAttribute('data-testid')}))"
            )
            print("Przyciski na stronie:", json.dumps(buttons, ensure_ascii=False))
        except Exception as e:
            print("Błąd odczytu przycisków:", e)

        browser.close()

    OUT_PATH.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Zapisano {len(captured)} przechwyconych API do {OUT_PATH}")


if __name__ == "__main__":
    import sys
    headed = "--headed" in sys.argv or "--login" in sys.argv
    cookies = []
    if COOKIES_PATH.exists():
        cookies = load_cookies_netscape(COOKIES_PATH)
        print(f"[*] Wczytano {len(cookies)} cookies z {COOKIES_PATH}")
    else:
        print("[!] Brak cookies.txt — przechodzę w tryb ręcznego logowania.")
        headed = True

    print(f"[*] Tryb: {'headed (ręczne logowanie)' if headed else 'headless (cookies)'}")
    capture(cookies, headed)