import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

sys.path.append("recon")
from monitor_20min import classify

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
detect_log_text = (LOG_DIR / "detect.log").read_text(encoding="utf-8") if (LOG_DIR / "detect.log").exists() else ""
compare_log_text = (LOG_DIR / "compare.log").read_text(encoding="utf-8") if (LOG_DIR / "compare.log").exists() else ""

CATEGORIES = {
    "IPHONE": "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc",
    "MACBOOK": "https://www.olx.pl/elektronika/komputery/laptopy/q-macbook/?search%5Border%5D=created_at:desc",
    "AUTA": "https://www.olx.pl/motoryzacja/samochody/mazowieckie/?search%5Bfilter_float_price%3Ato%5D=12000&search%5Border%5D=created_at:desc"
}

def audit():
    s = creq.Session(impersonate="chrome120")
    
    dom_results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        
        for name, url in CATEGORIES.items():
            print(f"\n========================================================")
            print(f"[*] Badam w Playwright: {name}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)
            
            try:
                btn = page.locator("#onetrust-accept-btn-handler")
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click(timeout=2000)
                    page.wait_for_timeout(1000)
            except Exception:
                pass
                
            for _ in range(4):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(400)
                
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
            dom_results[name] = cards
            print(f"[*] Znaleziono {len(cards)} kart w DOM dla {name}")
            
        browser.close()

    # Analyze DOM cards for each category
    print("\n========================================================")
    print("=== SZCZEGÓŁOWY AUDYT KART Z PRZEGLĄDARKI VS DETEKTOR ===")
    
    for cat_name, cards in dom_results.items():
        print(f"\n--- Kategoria: {cat_name} (Liczba kart: {len(cards)}) ---")
        
        # Count stats
        new_captured = 0
        new_missed = 0
        refreshed = 0
        older = 0
        
        for idx, c in enumerate(cards):
            oid = c["id"]
            loc = c["loc"].lower()
            title = c["title"].encode("ascii", "ignore").decode("ascii")
            
            # Check if refreshed or created today
            is_refreshed = "odswiezono" in loc or "odświeżono" in loc
            is_recent_hour = any(h in loc for h in ["20:", "19:5", "19:4", "19:3"])
            
            in_detect = oid in detect_log_text if oid else False
            in_compare = oid in compare_log_text if oid else False
            
            if is_refreshed:
                refreshed += 1
                status = "[ODSWIEZONE]"
            elif is_recent_hour:
                if in_detect:
                    new_captured += 1
                    status = "[ZLAPANE]"
                else:
                    new_missed += 1
                    status = "[POMINIETE]"
            else:
                older += 1
                status = "[STARSZE]"
                
            # If recent and missed, query API directly to see why
            diag = ""
            if status == "[POMINIETE]" and oid:
                res = s.get(f"https://www.olx.pl/api/v1/offers/{oid}/")
                if res.status_code == 200:
                    d = res.json().get("data", {})
                    cls_res = classify(d)
                    partner = (d.get("partner") or {}).get("code")
                    diag = f"-> classify={cls_res}, partner={partner}"
                else:
                    diag = f"-> API code {res.status_code}"
                    
            if idx < 15 or status == "[POMINIETE]":
                print(f"  {status:12} ID={oid:10} | {title[:35]:35} | {c['price']:12} | {c['loc']:25} {diag}")
                
        print(f"Podsumowanie {cat_name}: NoweZlapane={new_captured}, NowePominiete={new_missed}, Odswiezone={refreshed}, Starsze={older}")

    # Inspect comparator performance
    print("\n========================================================")
    print("=== AUDYT KOMPARATORA (Czy komparator znajduje oferty w wyszukiwarce?) ===")
    
    # Extract all detections from detect.log
    detections = []
    for line in detect_log_text.splitlines():
        if "TRAFIENIE" in line:
            m_id = re.search(r"id=(\d+)", line)
            m_label = re.search(r"\[(\w+)\]", line)
            m_title = re.search(r"tytul=(.*?) created=", line)
            if m_id:
                detections.append({
                    "id": m_id.group(1),
                    "label": m_label.group(1) if m_label else "",
                    "title": m_title.group(1) if m_title else ""
                })
                
    print(f"Liczba wszystkich detekcji w historii: {len(detections)}")
    
    # Check each detection in compare.log
    matched_found = 0
    matched_not_found = 0
    pending = 0
    
    for d in detections[-15:]:
        oid = d["id"]
        found_in_compare = [l for l in compare_log_text.splitlines() if oid in l]
        if any("ZNALEZIONO" in l for l in found_in_compare):
            matched_found += 1
            line = [l for l in found_in_compare if "ZNALEZIONO" in l][0]
            przewaga = re.search(r"przewaga=([\d\.]+ min)", line)
            p_str = przewaga.group(1) if przewaga else "OK"
            print(f"  [ZNALEZIONO] ID={oid} [{d['label']}] | Przewaga: {p_str:10} | Tytul: {d['title'][:35]}")
        elif any("NIE_POJAWILO_SIE" in l for l in found_in_compare):
            matched_not_found += 1
            print(f"  [NIE_POJAWILO_SIE] ID={oid} [{d['label']}] (detektor wyprzedzil o cale okno) | Tytul: {d['title'][:35]}")
        else:
            pending += 1
            print(f"  [PENDING / W TRAKCIE] ID={oid} [{d['label']}] | Tytul: {d['title'][:35]}")

if __name__ == "__main__":
    audit()
