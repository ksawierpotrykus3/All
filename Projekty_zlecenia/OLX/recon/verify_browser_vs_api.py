# coding: utf-8
"""
Weryfikacja: czy nasz detektor ID (API v1) widzi TO SAMO, co przegladarka
(server-side rendered HTML z JSON-LD) na stronach kategorii OLX.

Dla kazdej kategorii:
  1. Playwright otwiera strone kategorii (jak uzytkownik),
  2. wyciaga ID numeryczne ofert z HTML (JSON-LD),
  3. my pobieramy te same ID przez nasz endpoint /offers/{id}/,
  4. porownujemy: ktore ID przegladarki NIE sa w naszym API i vice versa.
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

KATEGORIE = [
    ("iphone", "https://www.olx.pl/elektronika/telefony/q-iphone/", 2298),
    ("macbook", "https://www.olx.pl/elektronika/komputery/laptopy/q-macbook/", 3102),
    ("auta", "https://www.olx.pl/motoryzacja/samochody/q-bmw/", 183),
]


def extract_offers_from_html(html):
    """Wyciagnij oferty z HTML (JSON-LD / embedded data)."""
    offers = []
    # 1. JSON-LD @type Offer
    for m in re.finditer(r'"@type":\s*"Offer"[\s\S]*?"url":\s*"(https://www\.olx\.pl/d/oferta/[^"]+)"', html):
        blob = m.group(0)
        url = m.group(1)
        nm = re.search(r'"name":\s*"([^"]+)"', blob)
        pr = re.search(r'"price":\s*([0-9.]+)', blob)
        offers.append({
            "title": nm.group(1) if nm else "",
            "price": pr.group(1) if pr else None,
            "url": url,
        })
    # 2. linki a[href*=olx.pl/d/oferta] - jako zapasowe
    if not offers:
        for m in re.finditer(r'href="(https://www\.olx\.pl/d/oferta/[^"]+)"', html):
            offers.append({"title": "", "price": None, "url": m.group(1)})
    return offers


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL",
        )
        page = ctx.new_page()

        all_results = {}
        for nazwa, url, cat_id in KATEGORIE:
            print(f"\n=== {nazwa} ({url}) ===")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
                html = page.content()
                offers = extract_offers_from_html(html)
                print(f"  przegladarka HTML: {len(offers)} ofert")
                for o in offers[:5]:
                    print(f"    {o['title'][:40]!r} {o['price']} | {o['url'][-30:]}")
                all_results[nazwa] = {
                    "cat_id": cat_id,
                    "count_html": len(offers),
                    "offers": offers[:20],
                }
            except Exception as e:  # noqa: BLE001
                print(f"  BLAD: {e}")
                all_results[nazwa] = {"cat_id": cat_id, "count_html": 0, "offers": [], "error": str(e)}

        browser.close()

    # zapisz surowke
    (LOG_DIR / "browser_offers.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nZapisano do logs/browser_offers.json")


if __name__ == "__main__":
    main()