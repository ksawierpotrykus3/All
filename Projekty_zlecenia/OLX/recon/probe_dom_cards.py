# coding: utf-8
"""
Weryfikacja: ile REALNIE kart ofert renderuje przegladarka na stronie kategorii OLX.

Gemini twierdzi: 52 karty (div[data-cy="l-card"]) po zaakceptowaniu OneTrust,
a moje wczesniejsze "20" pochodzilo z JSON-LD (SEO, limit 20).

Test deterministyczny:
  1. Otwiera strone kategorii iphone.
  2. Czeka na hydration + OneTrust.
  3. Liczy selektory: div[data-cy="l-card"], [data-testid="l-card"], a[href*="/d/oferta/"].
"""
from playwright.sync_api import sync_playwright

URL = "https://www.olx.pl/elektronika/telefony/q-iphone/"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL",
        )
        page = ctx.new_page()

        print(f"goto {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        # proba akceptacji OneTrust (rozne selektory)
        for sel in [
            "button#onetrust-accept-btn-handler",
            "button[aria-label*='Akceptuj']",
            "button[aria-label*='Zgadzam']",
            "#onetrust-accept-btn-handler",
        ]:
            try:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click(timeout=3000)
                    print(f"  zaakceptowano cookies: {sel}")
                    page.wait_for_timeout(3000)
                    break
            except Exception:  # noqa: BLE001
                pass

        # po akceptacji poczekaj na liste
        page.wait_for_timeout(3000)

        # liczba kart w DOM
        for sel in [
            "div[data-cy='l-card']",
            "[data-testid='l-card']",
            "div[data-cy='listing-grid'] a[href*='/d/oferta/']",
            "a[href*='/d/oferta/']",
        ]:
            try:
                n = page.locator(sel).count()
                print(f"  {sel}: {n}")
            except Exception as e:  # noqa: BLE001
                print(f"  {sel}: blad {e}")

        # czy sa widoczne karty z cena
        visible = page.locator("div[data-cy='l-card']:visible").count()
        print(f"  WIDOCZNE karty l-card: {visible}")

        # zrzut ekranu dla dowodu
        (page.screenshot(path=r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs\browser_cards.png"))
        print("  screenshot zapisany")

        browser.close()


if __name__ == "__main__":
    run()