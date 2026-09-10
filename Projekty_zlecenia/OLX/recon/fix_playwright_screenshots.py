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

def take_clean_screenshots():
    print("=== POBIERANIE W 100% CZYSTYCH ZRZUTÓW EKRANU (BEZ CLOUDFRONT 403) ===")
    
    # 1. Pobierz wszystkie dzisiejsze trafienia z detect.log
    detect_log_path = LOGS_DIR / "detect.log"
    all_hits = []
    if detect_log_path.exists():
        with open(detect_log_path, "r", encoding="utf-8") as f:
            for line in f:
                if "2026-08-31" in line and "TRAFIENIE" in line:
                    m_id = re.search(r"id=(\d+)", line)
                    m_cat = re.search(r"\[([A-Z]+)\]", line)
                    m_source = re.search(r"TRAFIENIE \[([A-Z_]+)\]", line)
                    m_price = re.search(r"cena=([0-9.]+)", line)
                    m_title = re.search(r"tytul=(.*?) created=", line)
                    m_created = re.search(r"created=(.*)", line)
                    m_region = re.search(r"region=(.*?) tytul=", line)
                    if m_id:
                        all_hits.append({
                            "id": int(m_id.group(1)),
                            "cat": m_cat.group(1) if m_cat else "",
                            "source": m_source.group(1) if m_source else "FRONTIER",
                            "price": float(m_price.group(1)) if m_price else 0.0,
                            "title": m_title.group(1) if m_title else "",
                            "created": m_created.group(1).strip() if m_created else "",
                            "region": m_region.group(1) if m_region else "",
                        })

    print(f"[*] Wszystkich trafień z dzisiaj: {len(all_hits)}")

    # Weź najświeższe oferty
    recent_hits = all_hits[-6:]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="pl-PL"
        )
        page = context.new_page()

        # Najpierw wejdź na stronę główną OLX, aby zainicjować sesję i ciasteczka
        print("[*] Inicjalizacja sesji OLX...")
        page.goto("https://www.olx.pl/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        try:
            btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Zaakceptuj')")
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        for h in recent_hits:
            oid = h["id"]
            # Pobierz kanoniczny URL z API
            r = creq.get(f"https://www.olx.pl/api/v1/offers/{oid}/", impersonate="chrome124", timeout=5)
            if r.status_code != 200:
                print(f"[!] Błąd API dla ID {oid}: status {r.status_code}")
                continue
            
            data = r.json().get("data", {})
            canonical_url = data.get("url")
            if not canonical_url:
                print(f"[!] Brak canonical URL dla {oid}")
                continue

            print(f"[*] Ładowanie oferty ID {oid}: {canonical_url}")
            shot_file = f"hit_clean_{oid}.png"
            shot_path = ARTIFACTS_DIR / shot_file
            
            try:
                page.goto(canonical_url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2000)
                
                # Upewnij się, że nie ma banera cookies
                try:
                    btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Zaakceptuj')")
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass

                # Zbadaj czy to nie jest błąd 403
                page_title = page.title()
                if "403" in page_title or "ERROR" in page_title:
                    print(f"    [!] UWAGA: Strona zwróciła błąd: {page_title}")
                else:
                    print(f"    [+] Strona załadowana poprawnie: {page_title[:50]}")

                page.screenshot(path=str(shot_path), full_page=False)
                shutil.copy(shot_path, LOGS_DIR / shot_file)
                print(f"    [+] Zapisano zrzut: {shot_file}")
            except Exception as e:
                print(f"    [!] Błąd Playwright: {e}")

        # Zrzut listy najnowszych iPhone
        print("[*] Zrzut listy najnowszych iPhone...")
        page.goto("https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc", wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2000)
        cat_shot = ARTIFACTS_DIR / "live_iphone_clean.png"
        page.screenshot(path=str(cat_shot), full_page=False)
        shutil.copy(cat_shot, LOGS_DIR / "live_iphone_clean.png")
        print("[+] Zapisano live_iphone_clean.png")

        browser.close()

    print("=== ZAKOŃCZONO POBIERANIE CZYSTYCH SCREENSHOTÓW ===")

if __name__ == "__main__":
    take_clean_screenshots()
