# -*- coding: utf-8 -*-
"""Sterownik formularza skladania oferty (Place Bid / Zloz oferte) na freelancer.pl.

Selektory potwierdzone reconem (formularz Angular):
- #bidAmountInput        -> kwota oferty (type=number)
- #periodInput           -> liczba dni (type=number)
- #descriptionTextArea   -> tresc oferty (textarea)
- przycisk submit        -> tekst "Zloz oferte" / "Place Bid"

Przeplyw:
1. Otwiera strone projektu.
2. Wykrywa blokade konta (ujemne saldo / restricted).
3. Klika "Zloz oferte" (przycisk otwiera formularz inline, bez zmiany URL).
4. Wypelnia kwote, dni, opis.
5. DRY_RUN: zrzut ekranu i STOP przed submitem.
   WYSYLKA: klika submit i weryfikuje potwierdzenie.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from playwright.sync_api import BrowserContext, Page

import config
from ai_pipeline import ProposalResult


class AuthenticationRequiredError(Exception):
    """Cookies wygasly - wymagane ponowne zalogowanie."""
    pass


class AccountBiddingBlockedError(Exception):
    """Konto zablokowane od bidowania (ujemne saldo / brak wplaty)."""
    pass


# Przyblizone kursy: ile PLN za 1 jednostke waluty projektu.
# AI wycenia w PLN (mechanika_wyceniania), a formularz jest w walucie projektu.
_PLN_PER_UNIT = {
    "PLN": 1.0,
    "USD": 4.0,
    "EUR": 4.3,
    "GBP": 5.0,
    "AUD": 2.6,
    "CAD": 2.9,
    "INR": 0.048,
    "CHF": 4.5,
}


def convert_pln_to_currency(pln: float, currency: str) -> int:
    """Konwertuje wycene AI (PLN) na walute projektu. Zwraca zaokraglona liczbe calkowita."""
    rate = _PLN_PER_UNIT.get((currency or "USD").upper(), 4.0)
    value = pln / rate
    # rozsadne zaokraglenie zaleznie od rzedu wielkosci
    if value >= 1000:
        return int(round(value / 50) * 50)
    if value >= 100:
        return int(round(value / 5) * 5)
    return max(1, int(round(value)))


class FormDriver:
    def __init__(self, context: BrowserContext, dry_run: bool = config.DRY_RUN):
        self.context = context
        self.dry_run = dry_run

    def _dismiss_banners(self, page: Page):
        for sel in ["button:has-text('Akceptuj')", "button:has-text('Accept')",
                    "button:has-text('Got it')", "[aria-label='Close']"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

    def fill_and_prepare_offer(self, job_id: str, seo_url: str, proposal: ProposalResult,
                               currency: str = "USD") -> Dict[str, Any]:
        """Otwiera formularz bida, wypelnia i (w DRY_RUN) zatrzymuje przed wysylka.

        `currency` to waluta projektu (formularz jest w tej walucie). Wycena AI jest w PLN,
        wiec konwertujemy ja do waluty projektu i podmieniamy kwote takze w tresci oferty.
        """
        url = f"https://www.freelancer.pl/projects/{seo_url}/details"
        page = self.context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            self._dismiss_banners(page)

            curr = page.url
            if "/login" in curr:
                raise AuthenticationRequiredError(f"Sesja wygasla: {curr}")

            body_lower = page.inner_text("body").lower()
            if "restricted from bidding" in body_lower or "negative balance" in body_lower:
                raise AccountBiddingBlockedError(
                    "Konto zablokowane od bidowania (ujemne saldo). "
                    f"Wymagane dodatnie saldo (zalecane min. {config.RECOMMENDED_BALANCE_USD} USD)."
                )

            # Angular laduje przycisk dopiero po kilku sekundach - czekamy jawnie.
            try:
                page.wait_for_selector("button:has-text('Złóż ofertę'), button:has-text('Place Bid')",
                                       timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(1000)

            # Otwarcie formularza: klikamy przycisk "Zloz oferte"/"Place Bid"
            opened = False
            for txt in ["Złóż ofertę", "Złóż Ofertę", "Place Bid", "Place a Bid"]:
                btn = page.locator(f"button:has-text('{txt}')").first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(4000)
                    opened = True
                    print(f"[FORM] Otworzono formularz przyciskiem: {txt}")
                    break
            if not opened:
                raise AccountBiddingBlockedError(
                    "Nie znaleziono przycisku zlozenia oferty - konto moze byc "
                    "zablokowane lub projekt ma ograniczenia (np. tylko Ulubieni)."
                )

            # Kwota - konwertujemy wycene AI (PLN) na walute projektu
            amount = convert_pln_to_currency(proposal.wycena, currency)
            amt = page.locator("#bidAmountInput").first
            if amt.count() == 0:
                raise RuntimeError("Nie znaleziono pola #bidAmountInput.")
            amt.click(); amt.fill(str(amount))

            # Dni
            dni = max(config.MIN_WORK_DAYS, int(proposal.dni))
            per = page.locator("#periodInput").first
            if per.count() > 0:
                per.click(); per.fill(str(dni))

            # Opis - podmieniamy kwote PLN w tresci na wyliczona w walucie projektu,
            # zeby oferta byla spojna z polem kwoty.
            opis = proposal.opis
            pln_str = str(proposal.wycena)
            if pln_str in opis and currency.upper() != "PLN":
                opis = opis.replace(pln_str, f"{amount} {currency.upper()}")
            desc = page.locator("#descriptionTextArea").first
            if desc.count() > 0:
                desc.click(); desc.fill(opis)

            shot = config.DEBUG_DIR / f"bid_form_{job_id}.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
            except Exception:
                pass

            if self.dry_run:
                return {
                    "status": "DRY_RUN_OK", "job_id": job_id, "final_url": page.url,
                    "wycena": amount, "dni": dni,
                    "filled": {"amount": amount, "days": dni, "description": True},
                    "proof_screenshot": str(shot),
                    "message": "Formularz wypelniony; zatrzymano przed 'Zloz oferte' (DRY_RUN).",
                }

            # Wysylka
            submit = None
            for txt in ["Złóż ofertę", "Zloz oferte", "Place Bid", "Submit"]:
                loc = page.locator(f"button:has-text('{txt}')").last
                if loc.count() > 0 and loc.is_visible():
                    submit = loc
                    break
            if not submit:
                raise RuntimeError("Nie znaleziono przycisku submit oferty.")
            submit.click()
            page.wait_for_timeout(5000)
            ok = any(t in page.inner_text("body").lower() for t in
                     ["oferta złożona", "bid placed", "proposal", "sukces", "success"])
            if ok:
                return {"status": "WYSLANO", "job_id": job_id, "wycena": amount, "dni": dni,
                        "final_url": page.url, "message": "Oferta zlozona."}
            fail = config.DEBUG_DIR / f"bid_fail_{job_id}.png"
            try:
                page.screenshot(path=str(fail), full_page=True)
            except Exception:
                pass
            raise RuntimeError(f"Brak potwierdzenia wysylki na {page.url} (zrzut: {fail})")
        finally:
            page.close()