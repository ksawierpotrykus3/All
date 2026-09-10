import asyncio
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

BASE_DIR = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX")
LOGS_DIR = BASE_DIR / "logs"
ARTIFACTS_DIR = Path(r"C:\Users\Ksawier\.gemini\antigravity\brain\dda6a6ab-b8d9-4fbb-bd33-521ac9843d92")

sys.path.insert(0, str(BASE_DIR))
from bot import classifier, config

def run_deep_live_audit():
    print("=== START DEEP AUDIT PO 50 MINUTACH PRACY BOTA ===")
    
    # 1. Wczytaj wszystkie trafienia z detect.log
    detect_log_path = LOGS_DIR / "detect.log"
    detected_ids = set()
    detected_hits = []
    with open(detect_log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "2026-08-31" in line and "TRAFIENIE" in line:
                m_id = re.search(r"id=(\d+)", line)
                m_cat = re.search(r"\[([A-Z]+)\]", line)
                m_price = re.search(r"cena=([0-9.]+)", line)
                m_title = re.search(r"tytul=(.*?) created=", line)
                m_created = re.search(r"created=(.*)", line)
                m_source = re.search(r"TRAFIENIE \[([A-Z_]+)\]", line)
                if m_id:
                    oid = int(m_id.group(1))
                    detected_ids.add(oid)
                    detected_hits.append({
                        "id": oid,
                        "cat": m_cat.group(1) if m_cat else "",
                        "source": m_source.group(1) if m_source else "FRONTIER",
                        "price": float(m_price.group(1)) if m_price else 0.0,
                        "title": m_title.group(1) if m_title else "",
                        "created": m_created.group(1).strip() if m_created else "",
                    })

    print(f"[*] Wszystkich trafień w detect.log: {len(detected_hits)}")

    # 2. Uruchom Playwright do zbadania stanu faktycznego w przeglądarce
    categories_to_check = [
        ("IPHONE", "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc", config.IPHONE_CAT_ID),
        ("MACBOOK", "https://www.olx.pl/elektronika/komputery/laptopy/apple/?search%5Border%5D=created_at:desc", config.MACBOOK_CAT_ID),
        ("AUTA_MAZOWIECKIE_12K", "https://www.olx.pl/motoryzacja/samochody/mazowieckie/?search%5Bfilter_float_price%3Ato%5D=12000&search%5Border%5D=created_at:desc", None)
    ]

    dom_findings = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="pl-PL"
        )
        page = context.new_page()

        # Cookie accept
        print("[*] Akceptacja cookies...")
        page.goto("https://www.olx.pl/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)
        try:
            btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Zaakceptuj')")
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        for cat_name, cat_url, cat_id in categories_to_check:
            print(f"\n[*] Skanowanie kategorii {cat_name} na żywo...")
            page.goto(cat_url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)

            for _ in range(4):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(300)

            # Screenshot
            shot_file = f"audit_50m_{cat_name.lower()}.png"
            page.screenshot(path=str(ARTIFACTS_DIR / shot_file), full_page=False)
            shutil.copy(ARTIFACTS_DIR / shot_file, LOGS_DIR / shot_file)
            print(f"[+] Zapisano zrzut kategorii: {shot_file}")

            # Wyciągnij karty z DOM
            cards = page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('div[data-cy="l-card"]').forEach(c => {
                    const linkEl = c.querySelector('a[href*="/d/oferta/"]');
                    const titleEl = c.querySelector('h6, h4, [data-testid="ad-title"]');
                    const priceEl = c.querySelector('[data-testid="ad-price"]');
                    const locDateEl = c.querySelector('[data-testid="location-date"]');
                    
                    results.push({
                        href: linkEl ? linkEl.getAttribute('href') : '',
                        title: titleEl ? titleEl.innerText.trim() : '',
                        price: priceEl ? priceEl.innerText.trim() : '',
                        locDate: locDateEl ? locDateEl.innerText.trim() : ''
                    });
                });
                return results;
            }""")
            print(f"[+] Zidentyfikowano {len(cards)} kart w DOM dla {cat_name}.")
            dom_findings[cat_name] = cards

        # Weź 3 najświeższe oferty z detect.log i zrób im zrzut
        print("\n[*] Pobieranie świeżych zrzutów najnowszych trafień...")
        for h in detected_hits[-3:]:
            oid = h["id"]
            r = creq.get(f"https://www.olx.pl/api/v1/offers/{oid}/", impersonate="chrome124", timeout=5)
            if r.status_code == 200:
                c_url = r.json().get("data", {}).get("url")
                if c_url:
                    page.goto(c_url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1500)
                    h_shot = f"audit_hit_{oid}.png"
                    page.screenshot(path=str(ARTIFACTS_DIR / h_shot), full_page=False)
                    shutil.copy(ARTIFACTS_DIR / h_shot, LOGS_DIR / h_shot)
                    print(f"[+] Zapisano zrzut trafienia {oid}: {h_shot}")

        browser.close()

    print("\n=== PODSUMOWANIE AUDYTU 50 MINUT ===")
    print(f"Liczba trafień od początku dnia: {len(detected_hits)}")
    print(f"Liczba kart w DOM: iPhone={len(dom_findings.get('IPHONE', []))}, MacBook={len(dom_findings.get('MACBOOK', []))}, Auta={len(dom_findings.get('AUTA_MAZOWIECKIE_12K', []))}")

if __name__ == "__main__":
    run_deep_live_audit()
