import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
detect_log = (LOG_DIR / "detect.log").read_text(encoding="utf-8")

# Let's import the actual classify from monitor_20min
import sys
sys.path.append("recon")
from monitor_20min import classify

print("=== AUTOPSJA IPHONE Z OSTATNICH 30 MINUT ===")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    
    page.goto("https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc", timeout=60000)
    page.wait_for_timeout(3000)
    try:
        page.locator("#onetrust-accept-btn-handler").first.click(timeout=2000)
        page.wait_for_timeout(1000)
    except Exception:
        pass
    
    for _ in range(5):
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
    
    browser.close()

print(f"Pobrano {len(cards)} kart z przegladarki.")

# Filter strictly for cards added between 19:40 and 20:10 (the last 30 minutes)
recent = []
for c in cards:
    loc = c["loc"].lower()
    if any(h in loc for h in ["19:4", "19:5", "20:0", "20:1"]):
        recent.append(c)

print(f"\nZnaleziono {len(recent)} ogloszen na stronie www z godzin 19:40-20:10:")

s = creq.Session(impersonate="chrome120")

for idx, r in enumerate(recent):
    oid = r["id"]
    title = r["title"].encode("ascii", "ignore").decode("ascii")
    loc = r["loc"].encode("ascii", "ignore").decode("ascii")
    
    # Check if in detect log
    in_log = oid in detect_log if oid else False
    
    # Fetch direct from API to see why it was or wasn't classified
    api_status = None
    classify_res = None
    if oid:
        res = s.get(f"https://www.olx.pl/api/v1/offers/{oid}/")
        api_status = res.status_code
        if res.status_code == 200:
            data = res.json().get("data", {})
            classify_res = classify(data)
            
    print(f"[{idx+1}] ID={oid} | in_log={in_log} | API={api_status} | classify={classify_res}")
    print(f"    Tytul: {title[:50]} | {r['price']} | {loc}")
