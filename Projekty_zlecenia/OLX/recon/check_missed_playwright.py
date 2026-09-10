import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
detect_log = (LOG_DIR / "detect.log").read_text(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    
    # 1. iPhone
    print("[*] Sprawdzam kategorie iPhone...")
    page.goto("https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc", timeout=60000)
    page.wait_for_timeout(3000)
    try:
        page.locator("#onetrust-accept-btn-handler").first.click(timeout=2000)
        page.wait_for_timeout(1000)
    except Exception:
        pass
    
    for _ in range(4):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(500)
        
    cards = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('div[data-cy="l-card"]')).map(c => {
            const titleEl = c.querySelector('h6, h4, [data-testid="ad-title"]');
            const priceEl = c.querySelector('[data-testid="ad-price"]');
            const locEl = c.querySelector('[data-testid="location-date"]');
            const idAttr = c.id || c.getAttribute('data-id') || '';
            const linkEl = c.querySelector('a[href*="/d/oferta/"]');
            return {
                id: idAttr,
                href: linkEl ? linkEl.getAttribute('href') : '',
                title: titleEl ? titleEl.innerText.trim() : '',
                price: priceEl ? priceEl.innerText.trim() : '',
                loc: locEl ? locEl.innerText.trim() : ''
            };
        });
    }""")
    
    print(f"DOM iPhone cards count: {len(cards)}")
    
    # Check each card if it was created in the last 40 minutes (18:50 - 19:25)
    recent_in_dom = []
    for c in cards:
        loc = c["loc"].lower()
        if "dzisiaj o 19:" in loc or "dzisiaj o 18:5" in loc:
            in_detect = False
            if c["id"] and c["id"] in detect_log:
                in_detect = True
            elif any(c["title"][:20].lower() in line.lower() for line in detect_log.splitlines()):
                in_detect = True
                
            recent_in_dom.append({
                "id": c["id"],
                "title": c["title"],
                "price": c["price"],
                "loc": c["loc"],
                "in_detect_log": in_detect
            })
            
    print(f"\nRecent iPhone offers in DOM (18:50-19:25): {len(recent_in_dom)}")
    captured_count = 0
    missed_count = 0
    for r in recent_in_dom:
        if r["in_detect_log"]:
            captured_count += 1
            status = "[CAPTURED]"
        else:
            missed_count += 1
            status = "[MISSED]"
        clean_title = r['title'].encode('ascii', 'ignore').decode('ascii')
        clean_loc = r['loc'].encode('ascii', 'ignore').decode('ascii')
        print(f"  {status} ID={r['id']} | {clean_title[:40]} | {r['price']} | {clean_loc}")

    print(f"\nPodsumowanie DOM: CAPTURED={captured_count}, MISSED={missed_count}")

    browser.close()
