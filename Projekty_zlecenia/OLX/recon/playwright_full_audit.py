import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

def run_thorough_check():
    categories = {
        "IPHONE": "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc",
        "MACBOOK": "https://www.olx.pl/elektronika/komputery/laptopy/q-macbook/?search%5Border%5D=created_at:desc",
        "AUTA": "https://www.olx.pl/motoryzacja/samochody/mazowieckie/?search%5Bfilter_float_price%3Ato%5D=12000&search%5Border%5D=created_at:desc"
    }

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL"
        )
        page = context.new_page()

        for cat_name, url in categories.items():
            print(f"\n========================================================")
            print(f"[*] Badam kategorie: {cat_name} -> {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # Accept cookies
            try:
                btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Zaakceptuj')")
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass

            # Scroll to load all 52 cards
            for _ in range(4):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(500)

            # Extract card info directly from DOM
            dom_offers = page.evaluate("""
                () => {
                    const cards = Array.from(document.querySelectorAll('div[data-cy="l-card"]'));
                    return cards.map(c => {
                        const linkEl = c.querySelector('a[href*="/d/oferta/"]');
                        const titleEl = c.querySelector('h6, h4, [data-testid="ad-title"]');
                        const priceEl = c.querySelector('[data-testid="ad-price"]');
                        const locEl = c.querySelector('[data-testid="location-date"]');
                        const idAttr = c.id || c.getAttribute('data-id') || '';
                        
                        return {
                            id: idAttr,
                            href: linkEl ? linkEl.getAttribute('href') : '',
                            title: titleEl ? titleEl.innerText.trim() : '',
                            price: priceEl ? priceEl.innerText.trim() : '',
                            locationDate: locEl ? locEl.innerText.trim() : ''
                        };
                    });
                }
            """)

            print(f"[*] Liczba kart w DOM na stronie {cat_name}: {len(dom_offers)}")
            results[cat_name] = dom_offers
            
            # Print top 5 newest/visible from DOM
            for idx, item in enumerate(dom_offers[:5]):
                print(f"  DOM [{idx+1}] {item['title'][:45]} | {item['price']} | {item['locationDate']} | ID={item['id']}")

        browser.close()

    # Read detect.log from the current monitor run
    detect_log_path = LOG_DIR / "detect.log"
    detected_ids = set()
    detected_titles = []
    if detect_log_path.exists():
        with open(detect_log_path, "r", encoding="utf-8") as f:
            for line in f:
                if "TRAFIENIE" in line:
                    match_id = re.search(r"id=(\d+)", line)
                    if match_id:
                        detected_ids.add(int(match_id.group(1)))
                    detected_titles.append(line.strip())

    print(f"\n========================================================")
    print(f"[*] Wszystkie trafienia w detect.log: {len(detected_ids)}")
    print(f"[*] Ostatnie trafienia:")
    for t in detected_titles[-10:]:
        print(f"    {t}")

if __name__ == "__main__":
    run_thorough_check()
