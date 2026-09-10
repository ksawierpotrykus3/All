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

def run_post_restart_audit():
    print("=== START AUDYTU PO RESTARCIE (ZERO-MISS HOLE SWEEPER) ===")
    session_start = "2026-08-31T12:28:50"
    
    # 1. Odczytaj trafienia po restarcie
    detect_log_path = LOGS_DIR / "detect.log"
    restart_hits = []
    if detect_log_path.exists():
        with open(detect_log_path, "r", encoding="utf-8") as f:
            for line in f:
                if "2026-08-31 12:2" in line or "2026-08-31 12:3" in line:
                    if "TRAFIENIE" in line:
                        m_time = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                        m_id = re.search(r"id=(\d+)", line)
                        m_cat = re.search(r"\[([A-Z]+)\]", line)
                        m_price = re.search(r"cena=([0-9.]+)", line)
                        m_title = re.search(r"tytul=(.*?) created=", line)
                        m_created = re.search(r"created=(.*)", line)
                        m_region = re.search(r"region=(.*?) tytul=", line)
                        m_source = re.search(r"TRAFIENIE \[([A-Z_]+)\]", line)
                        
                        if m_time and m_time.group(1) >= "2026-08-31 12:28:50" and m_id:
                            restart_hits.append({
                                "id": int(m_id.group(1)),
                                "cat": m_cat.group(1) if m_cat else "",
                                "source": m_source.group(1) if m_source else "LEGACY",
                                "price": float(m_price.group(1)) if m_price else 0.0,
                                "title": m_title.group(1) if m_title else "",
                                "created": m_created.group(1).strip() if m_created else "",
                                "region": m_region.group(1) if m_region else "",
                                "raw": line.strip()
                            })

    print(f"[*] Wykryte oferty w nowej sesji bota (od restartu 12:28:50): {len(restart_hits)}")
    for h in restart_hits:
        print(f"    -> ID {h['id']} [{h['source']}]: [{h['cat']}] {h['title']} ({h['price']} zł) @ {h['created']}")

    detected_ids = {h["id"] for h in restart_hits}

    # 2. Playwright live check
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="pl-PL"
        )
        page = context.new_page()

        print("\n--- FAZA 1: ZRZUTY EKRANU Z PLAYWRIGHTA DLA NOWYCH HITÓW ---")
        for h in restart_hits:
            oid = h["id"]
            r = creq.get(f"https://www.olx.pl/api/v1/offers/{oid}/", impersonate="chrome124", timeout=10)
            data = r.json().get("data") if r.status_code == 200 else None
            offer_url = data.get("url") if data else f"https://www.olx.pl/oferta/ID{oid}.html"
            
            shot_file = f"hit_restart_{oid}.png"
            shot_path = ARTIFACTS_DIR / shot_file
            try:
                page.goto(offer_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1500)
                page.screenshot(path=str(shot_path), full_page=False)
                shutil.copy(shot_path, LOGS_DIR / shot_file)
                print(f"[+] Zapisano zrzut nowego trafienia: {shot_file}")
            except Exception as e:
                print(f"[!] Błąd screenshotu dla {oid}: {e}")

        # Screenshot listy iPhone i MacBook
        print("\n--- FAZA 2: ZRZUTY LIST KATEGORII PO RESTARCIE ---")
        for cat_name, url in [
            ("IPHONE", "https://www.olx.pl/elektronika/telefony/smartfony-telefony-komorkowe/iphone/?search%5Border%5D=created_at:desc"),
            ("MACBOOK", "https://www.olx.pl/elektronika/komputery/laptopy/apple/?search%5Border%5D=created_at:desc"),
            ("AUTA_MAZOWIECKIE_12K", "https://www.olx.pl/motoryzacja/samochody/mazowieckie/?search%5Bfilter_float_price%3Ato%5D=12000&search%5Border%5D=created_at:desc")
        ]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2000)
                cat_shot = f"live_after_restart_{cat_name.lower()}.png"
                page.screenshot(path=str(ARTIFACTS_DIR / cat_shot), full_page=False)
                shutil.copy(ARTIFACTS_DIR / cat_shot, LOGS_DIR / cat_shot)
                print(f"[+] Zapisano screenshot kategorii: {cat_shot}")
            except Exception as e:
                print(f"[!] Błąd kategorii {cat_name}: {e}")

        browser.close()

    # 3. Analiza strumienia API dla okresu po restarcie
    print("\n--- FAZA 3: MATEMATYCZNY AUDYT: CZY PO RESTARCIE COŚ ZOSTAŁO POMINIĘTE? ---")
    post_audit = {
        "iphone": {"total": 0, "hits": 0, "filtered": 0, "missed": 0, "details": []},
        "macbook": {"total": 0, "hits": 0, "filtered": 0, "missed": 0, "details": []},
        "auta": {"total": 0, "hits": 0, "filtered": 0, "missed": 0, "details": []}
    }

    # iPhone
    r = creq.get("https://www.olx.pl/api/v1/offers/?offset=0&limit=50&category_id=2298&sort_by=created_at:desc", impersonate="chrome124")
    if r.status_code == 200:
        for off in r.json().get("data", []):
            created = off.get("created_time", "")
            if created >= "2026-08-31T12:26:00":  # badamy oferty z okolic i po restarcie
                oid = off["id"]
                title = off.get("title", "")
                price = classifier.parse_price(classifier._price(off))
                c_res = classifier.classify(off)
                was_hit = oid in detected_ids
                
                filter_reason = None
                t_lower = title.lower()
                for w in classifier.BLACKLIST_IPHONE:
                    if w in t_lower:
                        filter_reason = f"Czarna lista: '{w}'"
                        break
                
                post_audit["iphone"]["total"] += 1
                if was_hit:
                    post_audit["iphone"]["hits"] += 1
                    status = "WYKRYTY"
                elif filter_reason:
                    post_audit["iphone"]["filtered"] += 1
                    status = f"ODRZUCONY_SMIEC ({filter_reason})"
                else:
                    post_audit["iphone"]["missed"] += 1
                    status = "POMINIETY"
                
                post_audit["iphone"]["details"].append({
                    "id": oid,
                    "title": title,
                    "price": price,
                    "created": created,
                    "status": status,
                    "filter_reason": filter_reason
                })
                print(f"  [IPHONE] Status={status} | ID={oid} | {created[11:19]} | {title[:40]} | {price} zł")

    # MacBook
    r = creq.get("https://www.olx.pl/api/v1/offers/?offset=0&limit=50&category_id=3102&sort_by=created_at:desc", impersonate="chrome124")
    if r.status_code == 200:
        for off in r.json().get("data", []):
            created = off.get("created_time", "")
            if created >= "2026-08-31T12:26:00":
                oid = off["id"]
                title = off.get("title", "")
                price = classifier.parse_price(classifier._price(off))
                c_res = classifier.classify(off)
                was_hit = oid in detected_ids
                
                filter_reason = None
                t_lower = title.lower()
                norm = re.sub(r"\s+", "", t_lower)
                if "macbook" not in t_lower and "mac book" not in t_lower and "macbookpro" not in norm:
                    filter_reason = "Brak słowa macbook"
                else:
                    for w in classifier.BLACKLIST_MACBOOK:
                        if w in t_lower:
                            filter_reason = f"Czarna lista: '{w}'"
                            break
                
                post_audit["macbook"]["total"] += 1
                if was_hit:
                    post_audit["macbook"]["hits"] += 1
                    status = "WYKRYTY"
                elif filter_reason:
                    post_audit["macbook"]["filtered"] += 1
                    status = f"ODRZUCONY_SMIEC ({filter_reason})"
                else:
                    post_audit["macbook"]["missed"] += 1
                    status = "POMINIETY"
                
                post_audit["macbook"]["details"].append({
                    "id": oid,
                    "title": title,
                    "price": price,
                    "created": created,
                    "status": status,
                    "filter_reason": filter_reason
                })
                print(f"  [MACBOOK] Status={status} | ID={oid} | {created[11:19]} | {title[:40]} | {price} zł")

    report_path = LOGS_DIR / "post_restart_audit_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "restart_hits": restart_hits,
            "post_audit": post_audit
        }, f, indent=2, ensure_ascii=False)

    print("\n=== WYNIKI AUDYTU PO RESTARCIE ===")
    print(f"IPHONE: Wszystkich={post_audit['iphone']['total']}, Trafienia={post_audit['iphone']['hits']}, Odsiane śmieci={post_audit['iphone']['filtered']}, POMINIĘCIA={post_audit['iphone']['missed']}")
    print(f"MACBOOK: Wszystkich={post_audit['macbook']['total']}, Trafienia={post_audit['macbook']['hits']}, Odsiane śmieci={post_audit['macbook']['filtered']}, POMINIĘCIA={post_audit['macbook']['missed']}")

if __name__ == "__main__":
    run_post_restart_audit()
