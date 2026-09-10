"""Przechwyć PRAWDZIWY flow autobuy OLX: kliknij „Kup z przesyłką" i zarejestruj API.

ZAŁOŻENIE BEZPIECZEŃSTWA:
  - Klikamy przycisk KUP (tworzy rezerwację 15 min), ale NIE wpisujemy BLIK/karty
    i NIE przechodzimy do PayU. Zero ryzyka wysłania pieniędzy.
  - Celem jest potwierdzenie/obalenie mechanizmu rezerwacji (blokada 15 min,
    ewentualne 409 Conflict dla innych) oraz przechwycenie endpointów tworzących
    transakcję.

UŻYCIE:
  python capture_checkout_buy.py              # headless z cookies.txt
  python capture_checkout_buy.py --headed     # z widoczną przeglądarką
  python capture_checkout_buy.py --dry        # tylko ładuje stronę, NIE klika
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
COOKIES_PATH = BASE / "dane" / "cookies.txt"
OUT_PATH = BASE / "dane" / "checkout_buy_capture.json"

# Oferta testowa z delivery.rock.active=true (delivery.mode = BuyWithDelivery)
OFFER_ID = 1084508890
OFFER_URL = f"https://www.olx.pl/delivery/checkout/{OFFER_ID}/"

# Domeny, których ruch API nas interesuje
API_DOMAIN_PARTS = ("olx.pl", "payu", "payu.com", "cognito", "amazonaws", "rock")

# Selektor/frazy przycisku kupna
BUY_HINTS = ("kup z przesyłką", "kup z dostawą", "kup teraz", "kup i zapłać", "przejdź do płatności", "zamów")


def load_cookies_netscape(path: Path) -> list:
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
    if any(ext in low for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".ico", ".woff2", ".ttf")):
        return False
    return True


def main():
    dry = "--dry" in sys.argv
    headed = "--headed" in sys.argv

    cookies = []
    if COOKIES_PATH.exists():
        cookies = load_cookies_netscape(COOKIES_PATH)
        print(f"[*] Wczytano {len(cookies)} cookies")
    else:
        print("[!] Brak cookies.txt — logowanie ręczne wymagane")
        headed = True

    captured = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="pl-PL")
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
                if body and (body.lstrip().startswith(("{", "[")) or len(body) < 8000):
                    try:
                        entry["resp_json"] = resp.json()
                    except Exception:
                        entry["resp_text"] = body[:8000]
            except Exception as e:
                entry["resp_error"] = str(e)
            captured.append(entry)
            print(f"[{req.method}] {resp.status} {req.url}")

        page.on("response", on_response)

        print(f"[*] Otwieram checkout: {OFFER_URL}")
        page.goto(OFFER_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)

        shot = BASE / "dane" / "checkout_buy_page.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"[+] Zrzut strony checkoutu: {shot}")

        # Wylistuj przyciski, żeby zobaczyć co jest dostępne
        try:
            buttons = page.eval_on_selector_all(
                "button, a[role='button']",
                "els => els.slice(0,60).map(e => ({t: (e.textContent||'').trim().slice(0,80), d: e.getAttribute('data-testid'), h: e.getAttribute('href')}))"
            )
            print("Przyciski:", json.dumps(buttons, ensure_ascii=False, indent=2))
        except Exception as e:
            print("Błąd odczytu przycisków:", e)

        if dry:
            print("[i] Tryb --dry: nie klikam.")
            browser.close()
            OUT_PATH.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[+] Zapisano {len(captured)} przechwyconych API do {OUT_PATH}")
            return

        # Znajdź i kliknij przycisk KUP (bez płatności)
        clicked = False
        try:
            loc = page.locator("button, a[role='button']")
            n = loc.count()
            for i in range(min(n, 60)):
                el = loc.nth(i)
                try:
                    txt = (el.inner_text() or "").strip().lower()
                except Exception:
                    continue
                if any(h in txt for h in BUY_HINTS):
                    print(f"[*] Klikam przycisk: '{txt}'")
                    el.click(timeout=10000)
                    clicked = True
                    break
        except Exception as e:
            print("Błąd przy klikaniu:", e)

        if not clicked:
            print("[!] Nie znaleziono przycisku KUP — próbuję po data-testid")
            try:
                for tid in ("buy-button", "buyButton", "checkout-submit", "pay-button", "cta-buy"):
                    el = page.locator(f"[data-testid='{tid}']").first
                    if el.count() > 0:
                        el.click(timeout=10000)
                        clicked = True
                        print(f"[*] Kliknięto data-testid={tid}")
                        break
            except Exception as e:
                print("Błąd data-testid:", e)

        # Poczekaj na rezerwację / redirect / formularz płatności
        page.wait_for_timeout(8000)

        shot2 = BASE / "dane" / "checkout_buy_after_click.png"
        page.screenshot(path=str(shot2), full_page=True)
        print(f"[+] Zrzut po kliknięciu: {shot2}")

        cur_url = page.url
        print(f"[i] URL po kliknięciu: {cur_url}")
        if "payu" in cur_url.lower():
            print("[!] UWAGA: nastąpił redirect do PayU — nie kontynuujemy płatności.")

        browser.close()

    OUT_PATH.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Zapisano {len(captured)} przechwyconych API do {OUT_PATH}")


if __name__ == "__main__":
    main()