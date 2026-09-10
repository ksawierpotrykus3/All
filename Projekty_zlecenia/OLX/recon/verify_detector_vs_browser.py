# coding: utf-8
"""
Weryfikacja detektor ID vs przegladarka (Playwright DOM) - diff ofert.

Metoda:
  1. Playwright otwiera strone kategorii iphone (jak uzytkownik).
  2. Po OneTrust liczy karty l-card i wyciaga hash URL z a[href*=d/oferta].
  3. Nasz detektor ID przechwytuje te same oferty przez /api/v1/offers/{id}/.
  4. Porownujemy: ktore oferty przegladarki NIE maja odpowiednika w detektorze.

Celem jest dowod, ze detektor nie pomija tego, co widzi uzytkownik.
"""
import re
from curl_cffi import requests as creq
from playwright.sync_api import sync_playwright

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"
URL = "https://www.olx.pl/elektronika/telefony/q-iphone/"


def get_offer_by_id(oid):
    try:
        r = creq.get(API + str(oid) + "/", impersonate=IMP, timeout=15)
        if r.status_code == 200:
            return r.json().get("data")
    except Exception:  # noqa: BLE001
        pass
    return None


def hash_to_numeric(hash_part):
    """Zamien alfanumeryczny hash z URL na numeryczne ID przez API? Nie bezposrednio.
    Zamiast tego pobieramy ID numeryczne z JSON-LD w HTML, ktore jest obok URL."""
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL",
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        # OneTrust
        try:
            if page.locator("button#onetrust-accept-btn-handler").count() > 0:
                page.locator("button#onetrust-accept-btn-handler").first.click(timeout=3000)
                page.wait_for_timeout(3000)
        except Exception:  # noqa: BLE001
            pass

        # wyciagnij href ofert (hash) + tytul + cene z DOM
        cards = page.locator("div[data-cy='l-card']")
        n_cards = cards.count()
        print(f"Liczba kart l-card w DOM: {n_cards}")

        browser_offers = []
        for i in range(min(n_cards, 52)):
            card = cards.nth(i)
            href = card.locator("a[href*='/d/oferta/']").first.get_attribute("href")
            title = card.locator("h4, h6, [data-cy='l-card__title']").first.inner_text() if card.locator("h4, h6, [data-cy='l-card__title']").count() else ""
            price = card.locator("[data-testid='ad-price'], [data-cy='l-card__price']").first.inner_text() if card.locator("[data-testid='ad-price'], [data-cy='l-card__price']").count() else ""
            browser_offers.append({"href": href, "title": title.strip()[:60], "price": price.strip()})
            if i < 5:
                print(f"  [{i}] {title[:40]!r} {price!r} | {href[-35:] if href else 'BRAK'}")

        # zapisz surowke
        import json
        from pathlib import Path
        LOG = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
        (LOG / "browser_cards.json").write_text(json.dumps(browser_offers, ensure_ascii=False, indent=2), encoding="utf-8")

        browser.close()

    # Teraz porownanie z detektorem: dla kazdego href wyciagnij ID numeryczne z JSON-LD
    # (prostsze: zrob to na biezaco przez nasze API: pobierz ostatnie N ofert i porownaj tytuly)
    print("\n--- Porownanie detektor vs przegladarka (tytulami) ---")
    # nasz detektor: pobierz ostatnie oferty z API kategorii 2298
    r = creq.get(API + "?offset=0&limit=50&category_id=2298", impersonate=IMP, timeout=20)
    api_titles = [d.get("title", "")[:60] for d in r.json().get("data", [])]
    print(f"API v1 kategoria 2298: {len(api_titles)} ofert")

    # porownanie: ile tytulow z przegladarki jest w API
    matched = 0
    for bo in browser_offers:
        if any(bo["title"] in at for at in api_titles):
            matched += 1
    print(f"Dopasowanie tytulow (przegladarka -> API): {matched}/{len(browser_offers)}")


if __name__ == "__main__":
    main()