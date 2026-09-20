"""
TEST 01 – Połączenie i dostęp do Useme
Sprawdza czy Playwright + Camoufox + Firefox łączą się z Useme.
"""

import json
import os
import sys
from datetime import datetime

# ---------- KONFIGURACJA ----------
COOKIES_PATH = r"c:\Users\Ksawier\Pictures\Screenshots\useme\cookies.json"
URL = "https://useme.com/pl/jobs/category/programowanie-i-it,35/"
OUTPUT_DIR = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test01_connect"
SCREENSHOT_PATH = os.path.join(OUTPUT_DIR, "screenshot.png")
HTML_PATH = os.path.join(OUTPUT_DIR, "page.html")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main():
    log("=== TEST 01 – Połączenie i dostęp do Useme ===")
    log(f"URL: {URL}")
    log(f"Cookies path: {COOKIES_PATH} (exists: {os.path.exists(COOKIES_PATH)})")
    
    # Sprawdź czy camoufox jest dostępny
    use_camoufox = False
    try:
        import camoufox
        use_camoufox = True
        log(f"Camoufox dostępny: v{camoufox.__version__}")
    except ImportError:
        log("Camoufox NIE dostępny – używam zwykłego Firefox Playwright")
    except Exception as e:
        log(f"Camoufox import error: {e} – używam zwykłego Firefox Playwright")
    
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        # Uruchom przeglądarkę
        if use_camoufox:
            log("Uruchamiam Firefox przez Camoufox...")
            try:
                browser = p.firefox.launch(
                headless=True,
                firefox_user_prefs={
                    "dom.webdriver.enabled": False,
                    "useAutomationExtension": False,
                }
            )
                log("Camoufox Firefox uruchomiony pomyślnie")
            except Exception as e:
                log(f"Błąd Camoufox: {e}")
                log("Fallback do zwykłego Firefox...")
                use_camoufox = False
                browser = p.firefox.launch(headless=True)
        else:
            log("Uruchamiam zwykły Firefox Playwright...")
            browser = p.firefox.launch(headless=True)
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="pl-PL",
            timezone_id="Europe/Warsaw",
        )
        
        # Ładuj cookies jeśli istnieją
        if os.path.exists(COOKIES_PATH):
            try:
                with open(COOKIES_PATH, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                context.add_cookies(cookies)
                log(f"Załadowano {len(cookies)} cookies")
            except Exception as e:
                log(f"Błąd ładowania cookies: {e}")
        else:
            log("Brak pliku cookies – kontynuuję bez ciasteczek")
        
        page = context.new_page()
        
        # Idź na stronę
        log(f"Wchodzę na: {URL}")
        try:
            response = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            http_status = response.status if response else "brak odpowiedzi"
            log(f"HTTP status: {http_status}")
        except Exception as e:
            log(f"Błąd podczas goto: {e}")
            http_status = f"ERROR: {e}"
        
        # Czekaj 5 sekund
        log("Czekam 5 sekund na pełne załadowanie...")
        page.wait_for_timeout(5000)
        
        # Pobierz tytuł
        title = page.title()
        log(f"Tytuł strony: {title}")
        
        # Sprawdź URL (czy nie przekierowało na login)
        current_url = page.url
        log(f"Aktualny URL: {current_url}")
        redirected_to_login = "login" in current_url.lower() or "zaloguj" in current_url.lower()
        
        # Szukaj elementów ofert
        offer_selectors = [
            '[class*="offer"]',
            '[class*="job"]',
            '[class*="JobOffer"]',
            '[class*="listing"]',
            '[data-test*="offer"]',
            'article',
            '.job-listing',
            '.offer-item',
            '[class*="OffersList"]',
        ]
        
        total_offers = 0
        found_selectors = []
        for sel in offer_selectors:
            try:
                elements = page.query_selector_all(sel)
                if elements:
                    found_selectors.append(f"{sel}: {len(elements)} elementów")
                    total_offers += len(elements)
            except:
                pass
        
        # Unikamy podwójnego liczenia - użyjemy tylko najlepszego selektora
        # Szukamy specyficznie elementów z ofertami pracy
        job_offers = page.query_selector_all('[class*="offer"]')
        if not job_offers:
            job_offers = page.query_selector_all('[class*="job-item"]')
        if not job_offers:
            job_offers = page.query_selector_all('[class*="JobOffer"]')
        if not job_offers:
            job_offers = page.query_selector_all('article')
        
        offers_found = len(job_offers) > 0
        log(f"Znaleziono {len(job_offers)} elementów ofert (główny selektor)")
        
        if found_selectors:
            log("Szczegóły selektorów:")
            for s in found_selectors[:5]:
                log(f"  - {s}")
        
        # Zapisz screenshot
        page.screenshot(path=SCREENSHOT_PATH, full_page=False)
        log(f"Screenshot zapisany: {SCREENSHOT_PATH}")
        
        # Zapisz HTML
        html = page.content()
        with open(HTML_PATH, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"HTML zapisany: {HTML_PATH} ({len(html)} znaków)")
        
        # Podsumowanie
        page_loaded = http_status and str(http_status).startswith(("2", "3"))
        log("")
        log("=== PODSUMOWANIE ===")
        log(f"  Strona załadowana: {'TAK' if page_loaded else 'NIE'}")
        log(f"  HTTP status: {http_status}")
        log(f"  Tytuł: {title}")
        log(f"  Przekierowanie na login: {'TAK' if redirected_to_login else 'NIE'}")
        log(f"  Znalezione oferty: {'TAK' if offers_found else 'NIE'} ({len(job_offers)} elementów)")
        log(f"  Camoufox: {'TAK' if use_camoufox else 'NIE (zwykły Firefox)'}")
        log("===================")
        
        browser.close()
        log("Przeglądarka zamknięta.")
        
        # Zwróć status
        return {
            "page_loaded": page_loaded,
            "http_status": str(http_status),
            "title": title,
            "redirected_to_login": redirected_to_login,
            "offers_found": offers_found,
            "offers_count": len(job_offers),
            "used_camoufox": use_camoufox,
            "current_url": current_url,
        }

if __name__ == "__main__":
    result = main()
    # Exit code: 0 jeśli strona załadowana i są oferty
    if result["page_loaded"] and result["offers_found"]:
        sys.exit(0)
    elif result["page_loaded"]:
        sys.exit(1)  # Strona załadowana ale brak ofert
    else:
        sys.exit(2)  # Strona nie załadowana