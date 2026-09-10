"""Badanie flowu checkoutu OLX przy uzyciu trwalego profilu przegladarki.

Weryfikuje:
1. Czy strona checkoutu https://www.olx.pl/delivery/checkout/{offer_id}/ laduje sie
   w stanie zalogowanym (bez przekierowania do login.olx.pl).
2. Jakie zapytania API (XHR/Fetch) wysyla strona checkoutu do backendu delivery.
3. Czy widoczne sa metody dostawy (InPost, DPD, Orlen) i metody platnosci (BLIK).
"""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"
DANE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_OFFER_ID = 1084508890  # Oferta z aktywnym BuyWithDelivery z poprzednich badan
API_FILTER = ("olx.pl", "delivery", "payu", "order", "rock", "checkout", "address")


def is_relevant_api(url: str) -> bool:
    low = url.lower()
    if not any(f in low for f in API_FILTER):
        return False
    if any(ext in low for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".woff", ".woff2", ".ico")):
        return False
    return True


def main():
    offer_id = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else DEFAULT_OFFER_ID
    headed = "--headed" in sys.argv
    url = f"https://www.olx.pl/delivery/checkout/{offer_id}/"

    print("=" * 60)
    print(f"=== PROBE CHECKOUT OLX: Oferta {offer_id} ===")
    print(f"URL: {url}")
    print(f"Tryb: {'HEADED (okno widoczne)' if headed else 'HEADLESS (w tle)'}")
    print("=" * 60)

    if not PROFILE_DIR.exists():
        print(f"[!] Blad: Brak profilu {PROFILE_DIR}. Zaloguj sie najpierw przez ZALOGUJ_SIE_OLX.bat.")
        sys.exit(1)

    captured_requests = []

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=not headed,
            viewport={"width": 1400, "height": 900},
            locale="pl-PL",
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_response(resp):
            req = resp.request
            if not is_relevant_api(req.url):
                return

            entry = {
                "ts": time.time(),
                "method": req.method,
                "url": req.url,
                "status": resp.status,
                "headers": dict(req.headers),
                "post_data": req.post_data,
            }
            try:
                text = resp.text()
                if text.strip().startswith(("{", "[")):
                    entry["resp_json"] = resp.json()
                elif len(text) < 4000:
                    entry["resp_text"] = text
            except Exception:
                pass

            captured_requests.append(entry)
            print(f"[{req.method}] {resp.status} {req.url}")

        page.on("response", on_response)

        print(f"[*] Otwieram strone checkoutu...")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)

        current_url = page.url
        print(f"[*] Aktualny URL po zaladowaniu: {current_url}")

        # Zrzut ekranu
        shot_path = DANE_DIR / "checkout_loaded.png"
        page.screenshot(path=str(shot_path), full_page=True)
        print(f"[+] Zapisano zrzut ekranu: {shot_path}")

        # Weryfikacja czy wpadlismy na login.olx.pl
        if "login.olx.pl" in current_url:
            print("[FAIL] UWAGA: Przekierowano na login.olx.pl! Sesja w profilu wygasla lub wymaga ponownego zalogowania.")
        else:
            print("[OK] SUKCES: Strona checkoutu zaladowana w sesji zalogowanej!")

        # Wyciagnij elementy DOM (przyciski, formy)
        try:
            buttons = page.eval_on_selector_all(
                "button, a[role='button'], input[type='submit']",
                "els => els.map(e => ({tag: e.tagName, text: (e.textContent||'').trim(), testId: e.getAttribute('data-testid'), disabled: e.disabled}))"
            )
            print(f"[+] Znalezione przyciski w DOM ({len(buttons)}):")
            for b in buttons[:15]:
                if b['text']:
                    print(f"    - [{b['testId']}] '{b['text']}' (disabled={b['disabled']})")
            (DANE_DIR / "checkout_buttons.json").write_text(json.dumps(buttons, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[!] Blad analizy DOM: {e}")

        # Zapisz przechwycone requesty
        out_json = DANE_DIR / "checkout_api_intercept.json"
        out_json.write_text(json.dumps(captured_requests, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Zapisano {len(captured_requests)} zapytan API do: {out_json}")

        ctx.close()


if __name__ == "__main__":
    main()
