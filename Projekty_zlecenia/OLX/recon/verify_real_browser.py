import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/"

def test_browser_rendering():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL"
        )
        page = context.new_page()
        
        requests_log = []
        page.on("request", lambda req: requests_log.append({
            "url": req.url,
            "method": req.method,
            "resource_type": req.resource_type
        }))

        print(f"[*] Navigating to {URL}...")
        response = page.goto(URL, wait_until="networkidle", timeout=60000)
        print(f"[*] HTTP Status: {response.status if response else 'None'}")
        
        # Check cookie consent
        try:
            cookie_btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Zaakceptuj'), button:has-text('Akceptuję')")
            if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
                print("[*] Cookie banner found, clicking accept...")
                cookie_btn.first.click()
                page.wait_for_timeout(2000)
            else:
                print("[*] No cookie banner visible or already passed.")
        except Exception as e:
            print(f"[!] Cookie click error: {e}")

        page.wait_for_timeout(3000)
        
        # Take screenshot of initial view
        screenshot_path = LOG_DIR / "olx_iphone_view.png"
        page.screenshot(path=str(screenshot_path), full_page=False)
        print(f"[*] Screenshot saved to: {screenshot_path}")

        # Check DOM elements
        title = page.title()
        print(f"[*] Page Title: {title}")
        
        # Find offer links / cards
        card_locators = [
            'div[data-cy="l-card"]',
            '[data-testid="l-card"]',
            'a[href*="/d/oferta/"]',
            'div[data-testid="listing-grid"] > div'
        ]
        
        for loc in card_locators:
            count = page.locator(loc).count()
            print(f"[*] Locator '{loc}': count = {count}")
            
        # Extract all offer URLs and titles
        offers = []
        offer_links = page.locator('a[href*="/d/oferta/"]')
        count = offer_links.count()
        for i in range(count):
            link = offer_links.nth(i)
            href = link.get_attribute("href")
            text = link.inner_text().strip().replace("\n", " ")
            if href and "/d/oferta/" in href:
                offers.append({"href": href, "text": text})
                
        # Deduplicate by href
        unique_offers = {}
        for o in offers:
            base_href = o["href"].split("?")[0].split("#")[0]
            if base_href not in unique_offers:
                unique_offers[base_href] = o["text"]

        print(f"[*] Total raw offer links: {len(offers)}, Unique offer URLs: {len(unique_offers)}")
        for idx, (href, txt) in enumerate(list(unique_offers.items())[:10]):
            print(f"    [{idx+1}] {txt[:60]} -> {href}")

        # Inspect API calls intercepted
        api_calls = [r for r in requests_log if "/api/" in r["url"] or "graphql" in r["url"]]
        print(f"[*] Total intercepted API/GraphQL calls: {len(api_calls)}")
        for c in api_calls[:10]:
            print(f"    {c['method']} {c['resource_type']} {c['url'][:100]}")

        browser.close()

if __name__ == "__main__":
    test_browser_rendering()
