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

def run_verification():
    print("=== START PLAYWRIGHT VERIFICATION PO WDROŻENIU HOLE SWEEPER ===")
    
    detect_log_path = LOGS_DIR / "detect.log"
    new_session_hits = []
    with open(detect_log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "2026-08-31 12:28" in line or "2026-08-31 12:29" in line or "2026-08-31 12:3" in line:
                if "TRAFIENIE" in line:
                    m_id = re.search(r"id=(\d+)", line)
                    m_cat = re.search(r"\[([A-Z]+)\]", line)
                    m_source = re.search(r"TRAFIENIE \[([A-Z_]+)\]", line)
                    m_price = re.search(r"cena=([0-9.]+)", line)
                    m_title = re.search(r"tytul=(.*?) created=", line)
                    m_created = re.search(r"created=(.*)", line)
                    m_region = re.search(r"region=(.*?) tytul=", line)
                    if m_id:
                        new_session_hits.append({
                            "id": int(m_id.group(1)),
                            "cat": m_cat.group(1) if m_cat else "",
                            "source": m_source.group(1) if m_source else "FRONTIER",
                            "price": float(m_price.group(1)) if m_price else 0.0,
                            "title": m_title.group(1) if m_title else "",
                            "created": m_created.group(1).strip() if m_created else "",
                            "region": m_region.group(1) if m_region else "",
                            "raw": line.strip()
                        })

    print(f"[*] Liczba ofert wykrytych w nowej sesji (od restartu): {len(new_session_hits)}")
    for h in new_session_hits:
        print(f"   -> [{h['source']}] ID {h['id']} [{h['cat']}]: {h['title']} ({h['price']} zł, {h['region']}) @ {h['created']}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="pl-PL"
        )
        page = context.new_page()

        # 1. Wejście na każdą nową ofertę i screenshot
        print("\n--- FAZA 1: ZRZUTY EKRANU NOWYCH OFERT ---")
        for h in new_session_hits:
            oid = h["id"]
            r = creq.get(f"https://www.olx.pl/api/v1/offers/{oid}/", impersonate="chrome124", timeout=10)
            data = r.json().get("data") if r.status_code == 200 else None
            url = data.get("url") if data else f"https://www.olx.pl/oferta/ID{oid}.html"
            
            shot_file = f"hit_new_{oid}.png"
            shot_path = ARTIFACTS_DIR / shot_file
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1500)
                page.screenshot(path=str(shot_path), full_page=False)
                shutil.copy(shot_path, LOGS_DIR / shot_file)
                print(f"[+] Zapisano zrzut nowego trafienia: {shot_file}")
            except Exception as e:
                print(f"[!] Błąd screenshotu dla {oid}: {e}")

        # 2. Zrzut listy najnowszych iPhone'ów
        print("\n--- FAZA 2: ZRZUT EKRANU LISTY IPHONE ---")
        try:
            page.goto("https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(ARTIFACTS_DIR / "live_iphone_final.png"), full_page=False)
            shutil.copy(ARTIFACTS_DIR / "live_iphone_final.png", LOGS_DIR / "live_iphone_final.png")
            print(f"[+] Zapisano screenshot listy: live_iphone_final.png")
        except Exception as e:
            print(f"[!] Błąd kategorii: {e}")

        browser.close()

    print("\n=== ZAKOŃCZONO WERYFIKACJĘ PLAYWRIGHT ===")

if __name__ == "__main__":
    run_verification()
