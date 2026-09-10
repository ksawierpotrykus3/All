import json
import time
import base64
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/"

def test_deep_browser_and_api():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL"
        )
        page = context.new_page()
        
        print(f"[*] Navigating to {URL}...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        
        # Click cookie consent
        try:
            cookie_btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Zaakceptuj'), button:has-text('Akceptuję')")
            if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
                cookie_btn.first.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # Scroll down to load images & cards
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(2000)
        
        # Screenshot cards area
        screenshot_cards = LOG_DIR / "olx_iphone_cards.png"
        page.screenshot(path=str(screenshot_cards), full_page=False)
        print(f"[*] Cards screenshot saved to: {screenshot_cards}")

        # Extract detailed card info from DOM
        cards_info = page.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('div[data-cy="l-card"]'));
                return cards.map(c => {
                    const link = c.querySelector('a[href*="/d/oferta/"]');
                    const title = c.querySelector('h6, h4, [data-testid="ad-title"]') ? c.querySelector('h6, h4, [data-testid="ad-title"]').innerText : '';
                    const price = c.querySelector('[data-testid="ad-price"]') ? c.querySelector('[data-testid="ad-price"]').innerText : '';
                    const locationDate = c.querySelector('[data-testid="location-date"]') ? c.querySelector('[data-testid="location-date"]').innerText : '';
                    const isPromoted = !!c.querySelector('[data-testid="adCard-featured"], [data-testid="badge-highlighted"]');
                    const idAttr = c.getAttribute('id') || c.getAttribute('data-id') || '';
                    return {
                        title,
                        price,
                        locationDate,
                        href: link ? link.getAttribute('href') : '',
                        isPromoted,
                        idAttr
                    };
                });
            }
        """)

        print(f"[*] Extracted {len(cards_info)} cards from DOM via evaluate")
        for i, card in enumerate(cards_info[:10]):
            print(f"  [{i+1}] {card['title']} | {card['price']} | {card['locationDate']} | promoted={card['isPromoted']}")
            print(f"       href: {card['href']}")

        browser.close()

    # Now let's query API v1 for iPhone category
    print("\n[*] Querying API v1 for category 2298 (iPhone)...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    r = requests.get("https://www.olx.pl/api/v1/offers/?category_id=2298&limit=50", headers=headers, timeout=10)
    print(f"[*] API Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        api_offers = data.get("data", [])
        print(f"[*] API returned {len(api_offers)} offers")
        print(f"[*] API metadata: {data.get('metadata', {})}")
        for i, o in enumerate(api_offers[:5]):
            print(f"  API [{i+1}] ID={o.get('id')} | {o.get('title')} | {o.get('created_time')} | {o.get('url')}")

if __name__ == "__main__":
    test_deep_browser_and_api()
