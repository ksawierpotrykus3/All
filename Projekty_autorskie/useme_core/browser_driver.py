# -*- coding: utf-8 -*-
"""Sterownik przeglądarki (Playwright) – pobieranie listy i detali zleceń.

Wykorzystuje Chromium z playwright-stealth, zachowując odporność na Cloudflare
oraz weryfikację struktury HTML.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright_stealth import Stealth

import config


class BrowserDriver:
    def __init__(self, cookies_path: Optional[Path] = None, headless: bool = config.HEADLESS):
        self.cookies_path = cookies_path or config.COOKIES_PATH
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """Uruchamia Chromium ze stealth i ładuje cookies jeśli istnieją."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        Stealth().apply_stealth_sync(self.context)

        if self.cookies_path.exists():
            try:
                with open(self.cookies_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cookies = data.get("cookies", data if isinstance(data, list) else [])
                if cookies:
                    self.context.add_cookies(cookies)
            except Exception as e:
                print(f"[WARN] Błąd ładowania cookies z {self.cookies_path}: {e}")

    def close(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def dismiss_cookie_banner(self, page: Page):
        """Zamyka okno zgody na ciasteczka, jeśli się pojawi."""
        for sel in ["#cookiescript_accept", "button:has-text('AKCEPTUJ WSZYSTKIE')", "button:has-text('Akceptuj')"]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

    def check_logged_in(self, page: Page) -> bool:
        """Deterministycznie sprawdza czy użytkownik ma aktywną sesję."""
        has_session = any(c.get("name") == "sessionid" for c in self.context.cookies())
        login_buttons = page.locator('a:has-text("Zaloguj się"), a[href*="/login/"]').count()
        return has_session and (login_buttons == 0 or page.locator('a[href*="/profil/"], a[href*="/dashboard/"]').count() > 0)

    def fetch_category_jobs(self, category_key: str, max_jobs: int = config.MAX_OFFERS_PER_CATEGORY) -> List[Dict[str, Any]]:
        """Pobiera listę najnowszych zleceń z danej kategorii."""
        url = config.CATEGORY_URLS.get(category_key)
        if not url:
            raise ValueError(f"Nieznana kategoria: {category_key}")

        page = self.context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(config.WAIT_AFTER_PAGE_LOAD_S * 1000)
            self.dismiss_cookie_banner(page)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            articles = soup.select("article.job")

            jobs = []
            for art in articles[:max_jobs]:
                # Szukamy pierwszego linku do zlecenia
                a_tags = art.select("a[href*='/jobs/']")
                job_link = None
                job_id = None
                full_url = None

                for a in a_tags:
                    href = a.get("href", "")
                    # Odrzucamy linki do kategorii np. /jobs/category/...
                    if "/jobs/category/" in href:
                        continue
                    # ID zlecenia jest po przecinku, np. /pl/jobs/programista-wordpress,144045/
                    m = re.search(r',(\d+)/?$', href) or re.search(r'/jobs/(\d+)/?', href)
                    if m:
                        job_id = m.group(1)
                        full_url = href if href.startswith("http") else f"https://useme.com{href}"
                        job_link = a
                        break

                if not job_id or not full_url:
                    continue

                title = job_link.get_text(strip=True) if job_link else "Brak tytułu"

                # Budżet
                budget_el = art.select_one(".job__budget, .job-budget, .job__details-budget, .job__detail--budget")
                budget = budget_el.get_text(strip=True) if budget_el else "Do negocjacji"

                # Autor
                author_el = art.select_one(".job__author, .job-author, .user-name")
                author = author_el.get_text(strip=True) if author_el else "Anonim"

                # Krótki opis
                desc_el = art.select_one(".job__desc, .job-desc, p")
                desc = desc_el.get_text(strip=True) if desc_el else ""

                jobs.append({
                    "id": job_id,
                    "url": full_url,
                    "title": title,
                    "budget": budget,
                    "author": author,
                    "short_desc": desc,
                    "category": category_key
                })

            return jobs
        finally:
            page.close()

    def fetch_job_details(self, job_url: str) -> Dict[str, Any]:
        """Pobiera pełne dane pojedynczego zlecenia."""
        page = self.context.new_page()
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(2000)
            self.dismiss_cookie_banner(page)

            # Kliknij "Pokaż pełny opis" jeśli istnieje
            for sel in ["button:has-text('pokaż pełny opis')", ".job-details__show-more", "a:has-text('więcej')"]:
                try:
                    more_btn = page.locator(sel).first
                    if more_btn.count() > 0 and more_btn.is_visible():
                        more_btn.click()
                        page.wait_for_timeout(500)
                        break
                except Exception:
                    pass

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            title = ""
            full_desc = ""
            for script in soup.select("script[type='application/ld+json']"):
                try:
                    ld = json.loads(script.get_text(strip=True))
                    if isinstance(ld, dict) and ld.get("@type") == "JobPosting":
                        title = ld.get("title", "")
                        full_desc = ld.get("description", "")
                        break
                except Exception:
                    pass

            if not title:
                h1 = soup.select_one("h1")
                title = h1.get_text(strip=True) if h1 else ""

            if not full_desc:
                desc_container = soup.select_one(".job-details__content, .job-description, article.job")
                full_desc = desc_container.get_text("\n", strip=True) if desc_container else ""

            # Znalezienie linku do formularza składania oferty lub wykrycie już złożonej oferty
            already_offer_btn = page.locator("a:has-text('Twoja oferta')").first
            is_already_submitted = already_offer_btn.count() > 0 and already_offer_btn.is_visible()
            my_offer_href = already_offer_btn.get_attribute("href") if is_already_submitted else None

            add_offer_btn = page.locator("a:has-text('Dodaj ofertę'), button:has-text('Dodaj ofertę'), a:has-text('Aplikuj')").first
            has_add_button = add_offer_btn.count() > 0 and add_offer_btn.is_visible()
            add_offer_href = add_offer_btn.get_attribute("href") if has_add_button else None

            return {
                "url": job_url,
                "title": title,
                "full_description": full_desc,
                "has_add_offer_button": has_add_button,
                "add_offer_href": add_offer_href,
                "is_already_submitted": is_already_submitted,
                "my_offer_href": my_offer_href,
                "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
        finally:
            page.close()
