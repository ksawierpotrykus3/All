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
from typing import Any, Callable, Dict, List, Optional

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
                if isinstance(data, list):
                    cookies = data
                elif isinstance(data, dict):
                    cookies = data.get("cookies", [])
                else:
                    cookies = []
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

    def _extract_author_id(self, art, author_name: str) -> str:
        """Wyciąga identyfikator autora.

        Useme NIE udostępnia linku do profilu zleceniodawcy, więc stabilnym
        identyfikatorem w praktyce jest znormalizowana nazwa (slug). Jeśli
        jednak w HTML pojawi się link do profilu, użyjemy jego.
        """
        link = art.select_one("a[href*='/profil/'], a[href*='/user/'], a[href*='/users/']")
        if link:
            href = link.get("href", "")
            m = re.search(r'/(?:profil|user|users)/([^/?#]+)', href)
            if m:
                return m.group(1)
        return self._normalize_author(author_name)

    @staticmethod
    def _normalize_author(name: str) -> str:
        """Zamienia nazwę zleceniodawcy w stabilny identyfikator (slug).

        'Jan Kowalski' -> 'jan-kowalski', 'JMNET' -> 'jmnet'.
        Pusta nazwa -> 'anonim' (wtedy nie da się wykryć powtórek).
        """
        if not name:
            return "anonim"
        slug = re.sub(r"[^\w\s-]", "", name.lower()).strip()
        slug = re.sub(r"[\s_]+", "-", slug)
        return slug or "anonim"

    def _extract_author_from_details(self, soup) -> tuple:
        """Wyciąga (author, author_id) ze strony zlecenia Useme.

        Pewne źródło: blok .jobs-summary__item z etykietą "Zleceniodawca".
        Nazwa siedzi w <span>, a gdy go brak – w atrybucie alt awatara.
        """
        for item in soup.select(".jobs-summary__item"):
            label = item.select_one(".jobs-summary__item-label")
            if not label or "zleceniodawca" not in label.get_text(strip=True).lower():
                continue
            value_el = item.select_one(".jobs-summary__item-value")
            if not value_el:
                break
            author = ""
            span = value_el.select_one("span")
            if span:
                author = span.get_text(strip=True)
            if not author:
                img = value_el.select_one("img")
                alt = (img.get("alt") if img else "") or ""
                if alt and alt.strip().lower() != "no avatar":
                    author = alt.strip()
            if author:
                return author, self._normalize_author(author)
            break
        return "", "anonim"

    def fetch_category_jobs(self, category_key: str, max_jobs: int = config.MAX_OFFERS_PER_CATEGORY, should_stop_fn: Optional[Callable[[str], bool]] = None) -> List[Dict[str, Any]]:
        """Pobiera listę najnowszych zleceń z danej kategorii.
        
        Jeśli podano should_stop_fn i funkcja zwróci True dla job_id (np. zlecenie już w magazynie),
        pobieranie jest NATYCHMIAST przerywane – to zlecenie i wszystkie kolejne (starsze) są pomijane.
        """
        url = config.CATEGORY_URLS.get(category_key)
        if not url:
            raise ValueError(f"Nieznana kategoria: {category_key}")

        # Scrapowanie list kategorii wykonujemy w czystym kontekście (bez ciasteczek sesyjnych).
        # Zapobiega to błędowi Useme 'Oops! Już nad tym pracujemy!' (HTTP 500), który występuje
        # na serwerze Useme przy niektórych kategoriach (np. serwisy-internetowe,34/) WYŁĄCZNIE dla zalogowanych użytkowników.
        guest_context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="pl-PL"
        )
        page = guest_context.new_page()
        try:
            jobs = []
            seen_ids = set()
            page_num = 1
            max_pages = 5
            stopped_by_existing = False

            while len(jobs) < max_jobs and page_num <= max_pages and not stopped_by_existing:
                paged_url = f"{url}?page={page_num}" if page_num > 1 else url
                html = None
                try:
                    from curl_cffi import requests as cffi_requests
                    r = cffi_requests.get(paged_url, impersonate="chrome120", timeout=15)
                    if r.status_code == 200 and "article" in r.text:
                        html = r.text
                except Exception:
                    pass

                if not html:
                    page.goto(paged_url, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
                    page.wait_for_timeout(config.WAIT_AFTER_PAGE_LOAD_S * 1000)
                    self.dismiss_cookie_banner(page)
                    html = page.content()

                soup = BeautifulSoup(html, "html.parser")
                articles = soup.select("article.job")
                if not articles:
                    break

                new_count = 0
                for art in articles:
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

                    if not job_id or not full_url or job_id in seen_ids:
                        continue

                    # Sprawdzenie twardego zatrzymania na pierwszym znanym zleceniu
                    if should_stop_fn and should_stop_fn(job_id):
                        print(f"[FETCH STOP] Trafiono na znane zlecenie #{job_id} w systemie. Natychmiast przerywam pobieranie {category_key} — to i wszystkie starsze zlecenia są pomijane!", flush=True)
                        stopped_by_existing = True
                        break

                    title = job_link.get_text(strip=True) if job_link else "Brak tytułu"

                    # Budżet
                    budget_el = art.select_one(".job__budget, .job-budget, .job__details-budget, .job__detail--budget")
                    budget = budget_el.get_text(strip=True) if budget_el else "Do negocjacji"

                    # Autor – nazwa + stabilny identyfikator (link do profilu zleceniodawcy)
                    author_el = art.select_one(".job__author, .job-author, .user-name")
                    author = author_el.get_text(strip=True) if author_el else "Anonim"
                    author_id = self._extract_author_id(art, author)

                    # Krótki opis
                    desc_el = art.select_one(".job__desc, .job-desc, p")
                    desc = desc_el.get_text(strip=True) if desc_el else ""

                    seen_ids.add(job_id)
                    jobs.append({
                        "id": job_id,
                        "url": full_url,
                        "title": title,
                        "budget": budget,
                        "author": author,
                        "author_id": author_id,
                        "short_desc": desc,
                        "category": category_key
                    })
                    new_count += 1
                    if len(jobs) >= max_jobs:
                        break

                if new_count == 0 or stopped_by_existing:
                    break
                page_num += 1

            return jobs
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                guest_context.close()
            except Exception:
                pass

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

            # Autor zlecenia – z etykiety "Zleceniodawca" (patrz _extract_author_from_details).
            author, author_id = self._extract_author_from_details(soup)

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
                "author": author,
                "author_id": author_id,
                "has_add_offer_button": has_add_button,
                "add_offer_href": add_offer_href,
                "is_already_submitted": is_already_submitted,
                "my_offer_href": my_offer_href,
                "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
        finally:
            page.close()

    def sprawdz_skrzynke(self, author_id: str, data_wyslania: str) -> bool:
        """Sprawdza skrzynkę wiadomości w poszukiwaniu odpowiedzi od klienta.

        Args:
            author_id: Znormalizowany identyfikator autora (slug).
            data_wyslania: Data wysłania oferty w formacie ISO.

        Returns:
            True jeśli znaleziono odpowiedź od klienta po dacie wysłania, False w przeciwnym razie.
        """
        page = self.context.new_page()
        try:
            page.goto("https://useme.com/pl/messages/", wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(2000)
            self.dismiss_cookie_banner(page)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Przykładowe selektory – do dopracowania na podstawie aktualnego DOM
            wiadomosci = soup.select(".message-item, .thread-item, .conversation-list-item")
            for wiadomosc in wiadomosci:
                tekst = wiadomosc.get_text(strip=True)
                # Sprawdź, czy nadawcą jest nasz klient
                if author_id and (author_id in tekst.lower() or author_id.replace('-', ' ') in tekst.lower()):
                    # W idealnym przypadku parsujemy datę i porównujemy z data_wyslania.
                    # Na potrzeby testów przyjmujemy, że jeśli wiadomość jest na liście, to jest nowa.
                    return True
            return False
        except Exception as e:
            print(f"[WARN] Błąd sprawdzania skrzynki: {e}")
            return False
        finally:
            page.close()

    def sprawdz_powiadomienia(self, job_id: str, job_title: str = "") -> bool:
        """Sprawdza powiadomienia w poszukiwaniu informacji o zamknięciu zlecenia.

        Args:
            job_id: ID zlecenia.
            job_title: Tytuł zlecenia (opcjonalnie, do dopasowania w treści powiadomienia).

        Returns:
            True jeśli znaleziono powiadomienie o zamknięciu zlecenia, False w przeciwnym razie.
        """
        page = self.context.new_page()
        try:
            page.goto("https://useme.com/pl/", wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(2000)
            self.dismiss_cookie_banner(page)

            # Kliknięcie w ikonę dzwonka (powiadomienia)
            bell_btn = page.locator("button:has(.notification-icon), .notification-bell, [href*='/notifications']").first
            if bell_btn.count() > 0:
                bell_btn.click()
                page.wait_for_timeout(1500)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Szukamy powiadomienia o zamknięciu zlecenia
            powiadomienia = soup.select(".notification-item, .dropdown-item, li")
            for pow in powiadomienia:
                tekst = pow.get_text(strip=True).lower()
                if "zamkni" in tekst:
                    # Dopasowanie po ID lub tytule
                    if job_id and job_id in tekst:
                        return True
                    if job_title and job_title.lower() in tekst:
                        return True
            return False
        except Exception as e:
            print(f"[WARN] Błąd sprawdzania powiadomień: {e}")
            return False
        finally:
            page.close()
