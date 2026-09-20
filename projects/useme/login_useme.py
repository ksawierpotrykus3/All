# -*- coding: utf-8 -*-
"""Skrypt logowania do Useme z automatycznym zapisem cookies do tech/cookies.json."""

import sys
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

BASE_DIR = Path(__file__).parent
TECH_DIR = BASE_DIR / "tech"
TECH_DIR.mkdir(parents=True, exist_ok=True)


def login_useme(account_id: str = "konto1"):
    cookie_filename = "cookies.json" if account_id == "konto1" else f"cookies_{account_id}.json"
    if account_id == "konto2":
        cookie_filename = "cookies2.json"
    target_path = TECH_DIR / cookie_filename

    print("=" * 60)
    print(f"   LOGOWANIE DO USEME ({account_id.upper()})")
    print(f"   Docelowy plik: tech/{cookie_filename}")
    print("=" * 60)
    print("\n[1/3] Uruchamianie przegladarki Chrome / Chromium...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 850}
        )
        Stealth().apply_stealth_sync(context)

        page = context.new_page()

        print("[2/3] Otwieranie strony logowania Useme...")
        try:
            page.goto("https://useme.com/pl/users/login/", wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[!] Info przy ladowaniu: {e}")

        # Automatyczne zamkniecie banera cookies jesli jest
        for sel in ["#cookiescript_accept", "button:has-text('AKCEPTUJ WSZYSTKIE')", "button:has-text('Akceptuj')"]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        print("\n" + "#" * 60)
        print(">>> PRZEJDZ DO OTWARTEGO OKNA I ZALOGUJ SIE NA USEME <<<")
        print(">>> PO ZALOGOWANIU PROGRAM SAM WYKRYJE SESJE I ZAPISZE PLIK <<<")
        print("#" * 60 + "\n")

        logged_in = False
        start_wait = time.time()
        max_wait_seconds = 300  # 5 minut

        while time.time() - start_wait < max_wait_seconds:
            try:
                cookies = context.cookies()
                has_sessionid = any(c.get("name") == "sessionid" for c in cookies)
                has_csrftoken = any(c.get("name") == "csrftoken" for c in cookies)
                
                curr_url = page.url.lower()
                is_past_login = ("/users/login" not in curr_url) and ("/login" not in curr_url)

                if has_sessionid and (is_past_login or has_csrftoken):
                    login_btns = page.locator('a:has-text("Zaloguj się"), a[href*="/login/"]').count()
                    if login_btns == 0 or is_past_login:
                        logged_in = True
                        print("\n[+] Wykryto aktywna sesje (sessionid)!")
                        
                        with open(target_path, "w", encoding="utf-8") as f:
                            json.dump(cookies, f, ensure_ascii=False, indent=2)

                        print("=" * 60)
                        print(f"[3/3] SUKCES! Zapisano sesje do: {target_path}")
                        print(f"      Liczba ciasteczek: {len(cookies)}")
                        print("=" * 60)
                        time.sleep(2)
                        break
            except Exception as e:
                pass
            time.sleep(1)

        if not logged_in:
            print("\n[-] Nie wykryto zalogowania w ciagu 5 minut lub anulowano.")
            browser.close()
            return False

        browser.close()
        return True


if __name__ == "__main__":
    acc = "konto1"
    if len(sys.argv) > 1:
        acc = sys.argv[1].strip().lower()
    login_useme(acc)
