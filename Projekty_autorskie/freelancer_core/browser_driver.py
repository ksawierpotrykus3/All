# -*- coding: utf-8 -*-
"""Sterownik przegladarki (Playwright) dla freelancer.pl - podejscie API-first.

Kluczowe odkrycie reconu: freelancer.pl udostepnia publiczne API JSON
(`/api/projects/0.1/...`), ktore dziala przez kontekst przegladarki z cookies.
Zwraca pelne dane projektu (opis, budzet, kategorie, statystyki bidow),
wiec NIE trzeba scrapowac HTML renderowanego client-side.

Sterownik sluzy do:
- zalogowania sie przez cookies (sesja Ksawiera),
- pobierania listy projektow przez API (z filtrem kategorii i pomijaniem lokalnych),
- pobierania pelnych detali projektu,
- weryfikacji salda konta (blokada bidowania przy ujemnym saldzie),
- (opcjonalnie) otwarcia strony projektu w przegladarce dla form_driver.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        self._page: Optional[Page] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """Uruchamia Chromium ze stealth i laduje cookies sesji freelancera."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 900},
            locale="pl-PL",
        )
        Stealth().apply_stealth_sync(self.context)

        if self.cookies_path.exists():
            try:
                data = json.loads(self.cookies_path.read_text(encoding="utf-8"))
                cookies = data.get("cookies", data if isinstance(data, list) else [])
                if cookies:
                    self.context.add_cookies(cookies)
                    print(f"[OK] Zaladowano {len(cookies)} cookies z {self.cookies_path.name}")
            except Exception as e:
                print(f"[WARN] Blad ladowania cookies: {e}")

        # Strona-wozak, przez ktora wykonujemy zapytania API (dziedziczy cookies/naglowki)
        self._page = self.context.new_page()

    def close(self):
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    # ------------------------------------------------------------------ API
    def api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Wykonuje GET do API freelancera i zwraca sparsowany JSON (lub None)."""
        url = f"{config.API_BASE}/{path.lstrip('/')}"
        try:
            r = self.context.request.get(url, params=params, timeout=30000)
            if r.ok:
                return r.json()
            print(f"[API {r.status}] {url}")
            return None
        except Exception as e:
            print(f"[API ERR] {url}: {e}")
            return None

    def check_account(self) -> Dict[str, Any]:
        """Sprawdza stan konta: saldo i limit bidow (blokada platformy)."""
        info = {"logged_in": False, "user_id": None, "balance_usd": None,
                "bids_remaining": None, "can_bid": False, "notes": []}
        # Sesja = cookies z GETAFREE_AUTH_HASH_V2 + GETAFREE_USER_ID
        cookies = {c.get("name"): c.get("value") for c in self.context.cookies()}
        info["user_id"] = cookies.get("GETAFREE_USER_ID")
        info["logged_in"] = bool(cookies.get("GETAFREE_AUTH_HASH_V2") and info["user_id"])

        # Saldo: API users/0.1 nie zwraca balance -> scrapujemy dashboard (widoczny napis -$12.29)
        uid = info["user_id"]
        if uid and info["balance_usd"] is None:
            try:
                page = self.context.new_page()
                page.goto("https://www.freelancer.pl/dashboard", wait_until="domcontentloaded",
                          timeout=config.NAV_TIMEOUT_MS)
                page.wait_for_timeout(6000)
                import re
                body = page.inner_text("body")
                # Preferuj wzorzec ze znakiem $ (saldo konta), potem sam USD.
                m = (re.search(r"([-+]?)\s*\$\s?([\d,]+\.\d{2})", body)
                     or re.search(r"([-+]?)\s*([\d,]+\.\d{2})\s*USD", body))
                if m:
                    val = float(m.group(2).replace(",", ""))
                    if m.group(1) == "-":
                        val = -val
                    info["balance_usd"] = val
                page.close()
            except Exception as e:
                print(f"[WARN] Scrape dashboard balansu: {e}")
        # Limit bidow przez /bids lub bezposrednio z projects
        info["can_bid"] = (
            info["logged_in"]
            and isinstance(info["balance_usd"], (int, float))
            and info["balance_usd"] > config.CAN_BID_MIN_USD
        )
        if not info["can_bid"]:
            info["notes"].append(
                f"Bidowanie zablokowane: saldo musi byc dodatnie "
                f"(aktualne: {info['balance_usd']} USD)."
            )
        elif isinstance(info["balance_usd"], (int, float)) and info["balance_usd"] < config.RECOMMENDED_BALANCE_USD:
            info["notes"].append(
                f"[OSTRZEZENIE] Saldo {info['balance_usd']} USD < zalecane "
                f"{config.RECOMMENDED_BALANCE_USD} USD. Formularz dziala, ale platforma "
                f"moze odrzucic submit (prog platformy)."
            )
        return info

    def fetch_category_jobs(self, category_key: str, max_jobs: int = config.MAX_OFFERS_PER_CATEGORY) -> List[Dict[str, Any]]:
        """Pobiera liste najnowszych projektow z kategorii przez API (bez scrapowania HTML)."""
        job_ids = config.CATEGORY_JOBS.get(category_key)
        if not job_ids:
            raise ValueError(f"Nieznana kategoria: {category_key}")

        # Budujemy query recznie - Playwright params gubi duplikaty klucza 'jobs[]'.
        # Uwaga: API ignoruje sort_field (zwraca staly zestaw), wiec pobieramy wiekszy
        # limit i sortujemy lokalnie po time_submitted (najnowsze pierwsze).
        from urllib.parse import urlencode
        q = [
            ("limit", 50),
            ("full_description", "true"),
            ("job_details", "true"),
            ("user_details", "true"),
            ("owner_info", "true"),
            ("upgrade_details", "true"),
            ("webapp", "1"),
            ("compact", "true"),
            ("new_errors", "true"),
            ("new_pools", "true"),
        ]
        for jid in job_ids:
            q.append(("jobs[]", jid))
        url = f"{config.API_BASE}/projects/active/?{urlencode(q)}"

        data = self._api_get_url(url)
        if not data:
            return []

        projects = data.get("result", {}).get("projects", [])
        # sort lokalny: najnowsze wg time_submitted
        projects = sorted(projects, key=lambda p: p.get("time_submitted") or 0, reverse=True)

        jobs: List[Dict[str, Any]] = []
        for pj in projects:
            if pj.get("deleted"):
                continue
            if config.SKIP_LOCAL_PROJECTS and pj.get("local"):
                continue
            jobs.append(self._normalize_list_item(pj, category_key))
            if len(jobs) >= max_jobs:
                break
        return jobs

    def _api_get_url(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            r = self.context.request.get(url, timeout=30000)
            if r.ok:
                return r.json()
            print(f"[API {r.status}] {url[:120]}")
            return None
        except Exception as e:
            print(f"[API ERR] {url[:120]}: {e}")
            return None

    def _normalize_list_item(self, pj: Dict[str, Any], category_key: str) -> Dict[str, Any]:
        budget = pj.get("budget") or {}
        cur = (pj.get("currency") or {}).get("code", "USD")
        bmin, bmax = budget.get("minimum"), budget.get("maximum")
        if bmin or bmax:
            budget_str = f"{bmin or '?'} - {bmax or '?'} {cur}"
        else:
            budget_str = f"Do negocjacji ({cur})"

        jobs_names = [j.get("name") for j in (pj.get("jobs") or []) if j.get("name")]
        owner = pj.get("owner_info") or {}
        return {
            "id": str(pj.get("id")),
            "url": f"https://www.freelancer.pl/projects/{pj.get('seo_url')}/details",
            "seo_url": pj.get("seo_url"),
            "title": pj.get("title", ""),
            "budget": budget_str,
            "budget_raw": budget,
            "currency": cur,
            "author": owner.get("username") or owner.get("display_name") or "Anonim",
            "short_desc": pj.get("preview_description", ""),
            "category": category_key,
            "project_type": pj.get("type"),
            "jobs": jobs_names,
            "bid_stats": pj.get("bid_stats") or {},
            "local": pj.get("local", False),
            "time_submitted": pj.get("time_submitted"),
        }

    def fetch_job_details(self, job_id: str) -> Dict[str, Any]:
        """Pobiera pelne dane pojedynczego projektu przez API."""
        data = self.api_get(f"projects/{job_id}/", {
            "full_description": "true", "job_details": "true",
            "user_details": "true", "upgrade_details": "true",
            "location_details": "true", "webapp": 1, "compact": True,
        })
        if not data:
            return {}
        pj = data.get("result", {})
        owner = pj.get("owner_info") or {}
        rep = owner.get("reputation") or {}
        return {
            "id": str(pj.get("id")),
            "title": pj.get("title", ""),
            "full_description": pj.get("description", ""),
            "budget_raw": pj.get("budget") or {},
            "currency": (pj.get("currency") or {}).get("code", "USD"),
            "project_type": pj.get("type"),
            "jobs": [j.get("name") for j in (pj.get("jobs") or [])],
            "bid_stats": pj.get("bid_stats") or {},
            "owner": {
                "username": owner.get("username"),
                "display_name": owner.get("display_name"),
                "country": (owner.get("country") or {}).get("name"),
                "city": owner.get("city"),
                "reputation": (rep.get("entire_history") or {}).get("overall") if isinstance(rep, dict) else None,
                "jobs_posted": (rep.get("entire_history") or {}).get("complete") if isinstance(rep, dict) else None,
            },
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def fetch_my_bids_remaining(self) -> Optional[int]:
        """Zwraca liczbe pozostalych bidow w tym cyklu (limit platformy)."""
        data = self.api_get("projects/active/", {
            "limit": 1, "job_details": "true", "webapp": 1,
            "compact": True, "new_errors": True, "new_pools": True,
        })
        # Endpoint limitowy wykryty w reconie: /projects/0.1/bids (bidders) zwraca bidsRemaining
        # Uzywamy dedykowanego: /projects/active/ nie zwraca; probujemy /bids
        try:
            uid = {c.get("name"): c.get("value") for c in self.context.cookies()}.get("GETAFREE_USER_ID")
            if uid:
                r = self.context.request.get(
                    "https://www.freelancer.com/ajax-api/projects/0.1/bids-limits/",
                    params={"user_id": uid}, timeout=20000,
                )
                if r.ok:
                    j = r.json()
                    return j.get("result", {}).get("bidsRemaining")
        except Exception:
            pass
        return None