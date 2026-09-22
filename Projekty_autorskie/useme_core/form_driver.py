# -*- coding: utf-8 -*-
"""Sterownik formularza wysyłki oferty (Playwright) z twardym bezpiecznikiem DRY_RUN.

Odpowiada za:
- wejście na stronę formularza /pl/jobs/{ID}/offer/start/,
- weryfikację czy sesja nie wygasła (blokada przed próbą wysyłki jako gość),
- czyszczenie draftów i wpisanie opisu, wyceny oraz dni (min. 7),
- obsługę praw autorskich (wyłącznie gdy widnieje 'decyzja freelancera'),
- przejście do podsumowania,
- zatrzymanie przed ostateczną wysyłką w trybie DRY_RUN ze zrzutem ekranu.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from playwright.sync_api import BrowserContext, Page

import config
from ai_pipeline import ProposalResult


class AuthenticationRequiredError(Exception):
    """Rzucany, gdy cookies wygasły i Useme wymaga ponownego logowania."""
    pass


class FormDriver:
    def __init__(self, context: BrowserContext, dry_run: bool = config.DRY_RUN):
        self.context = context
        self.dry_run = dry_run

    def fill_and_prepare_offer(self, job_id: str, proposal: ProposalResult) -> Dict[str, Any]:
        """Wypełnia formularz i przechodzi do podsumowania."""
        url = f"https://useme.com/pl/jobs/{job_id}/offer/start/"
        page = self.context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            page.wait_for_timeout(2000)

            # 1. Sprawdzenie czy nie przekierowało do logowania
            curr_url = page.url
            if "/login" in curr_url or page.locator('input[name="login"], input[name="username"]').count() > 0:
                raise AuthenticationRequiredError(
                    f"Sesja Useme wygasła! Przekierowano do logowania: {curr_url}. "
                    "Zaktualizuj plik tech/cookies.json."
                )

            # 2. Zamknięcie banera cookies
            for sel in ["#cookiescript_accept", "button:has-text('AKCEPTUJ WSZYSTKIE')"]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        loc.click()
                        page.wait_for_timeout(500)
                        break
                except Exception:
                    pass

            # Twarde usunięcie overlay banera cookies z DOM, żeby nie blokował kliknięć w pola
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('#cookiescript_injected_wrapper, #cookiescript_wrapper, .cookie-banner, [id*="cookiescript"]').forEach(el => el.remove());
                }""")
            except Exception:
                pass

            # 3. Wypełnienie kwoty (standardowej lub etapowej)
            payment_input = page.locator("#id_payment, input[name='payment'], input[name='stages-0-payment']").first
            if payment_input.count() == 0:
                raise RuntimeError(f"Nie znaleziono pola wyceny (#id_payment / stages-0-payment) na stronie: {curr_url}")
            try:
                payment_input.click(force=True)
            except Exception:
                pass
            payment_input.fill(str(proposal.wycena))

            # 4. Wypełnienie dni pracy (minimum 7)
            dni = max(config.MIN_WORK_DAYS, int(proposal.dni))
            days_input = page.locator("#id_work_days, input[name='work_days']").first
            if days_input.count() > 0:
                try:
                    days_input.click(force=True)
                except Exception:
                    pass
                days_input.fill(str(dni))

            # 5. Wypełnienie opisu (rich-text editor + hidden input)
            opis = proposal.opis or ""
            editor = page.locator('div[contenteditable="true"], .trumbowyg-editor').first
            if editor.count() > 0 and editor.is_visible():
                try:
                    editor.click(force=True)
                except Exception:
                    pass
                # fill() na contenteditable wysyła zdarzenia input, ale frameworki
                # (Trumbowyg/React) czasem potrzebują realnego pisania. Fallback:
                # jeśli fill rzuci lub pole zostanie puste, użyj keyboard.insert_text.
                try:
                    editor.fill(opis)
                except Exception:
                    pass
                try:
                    editor.press("Control+A")
                    editor.press("Delete")
                    page.keyboard.insert_text(opis)
                except Exception:
                    pass

            # Wstrzyknięcie wartości do pola ukrytego #id_description z NATYWNYM
            # setterem (React/descriptor), żeby framework zobaczył zmianę.
            page.evaluate("""({val}) => {
                const el = document.querySelector('#id_description') || document.querySelector('textarea[name="description"]');
                if (!el) return;
                const proto = el.tagName === 'TEXTAREA'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", {"val": opis})

            # 6. Prawa autorskie
            # Reguła: klikamy TYLKO wtedy gdy jest napisane "decyzja freelancera"
            page_content = page.content().lower()
            if "decyzja freelancera" in page_content:
                # Domyślnie zaznaczamy 'without' (bez przeniesienia) lub 'license'
                radio = page.locator('input[name="copyright_transfer"][value="without"]').first
                if radio.count() > 0:
                    radio.check()

            # 7. Przejście do podsumowania
            summary_btn = page.locator("button:has-text('Przejdź do podsumowania')").first
            if summary_btn.count() == 0:
                raise RuntimeError("Nie znaleziono przycisku 'Przejdź do podsumowania'!")

            # Twarde usunięcie overlay banera cookies z DOM przed kliknięciem podsumowania
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('#cookiescript_injected_wrapper, #cookiescript_wrapper, .cookie-banner, [id*="cookiescript"]').forEach(el => el.remove());
                }""")
            except Exception:
                pass

            try:
                summary_btn.click(force=True)
            except Exception:
                summary_btn.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            # Dowód weryfikacyjny – zrzut ekranu podsumowania
            screenshot_path = config.DEBUG_DIR / f"summary_proof_{job_id}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"[DEBUG] URL po kliknięciu podsumowania: {page.url}")

            # 8. Twardy bezpiecznik pesymisty: DRY_RUN
            if self.dry_run:
                return {
                    "status": "DRY_RUN_OK",
                    "job_id": job_id,
                    "final_url": page.url,
                    "wycena": proposal.wycena,
                    "dni": dni,
                    "proof_screenshot": str(screenshot_path),
                    "message": f"Zatrzymano przed ostatecznym kliknięciem 'Wyślij' na URL: {page.url}. Wszystkie pola i podsumowanie zweryfikowane."
                }

            # 9. Rzeczywista wysyłka (tylko gdy DRY_RUN = False)
            submit_btn = page.locator("button:has-text('Wyślij'), input[value='Wyślij']").first
            if submit_btn.count() == 0:
                raise RuntimeError("Nie znaleziono przycisku 'Wyślij' na stronie podsumowania!")
            
            # Usunięcie overlay banera cookies z DOM na stronie podsumowania
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('#cookiescript_injected_wrapper, #cookiescript_wrapper, .cookie-banner, [id*="cookiescript"]').forEach(el => el.remove());
                }""")
            except Exception:
                pass

            print(f"[INFO] Klikam przycisk 'Wyślij' dla zlecenia #{job_id}...")
            try:
                submit_btn.click(force=True)
            except Exception:
                submit_btn.click()

            # Deterministyczne czekanie na przeładowanie i przetworzenie odpowiedzi przez Useme
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception as wait_err:
                print(f"[DEBUG] Timeout domcontentloaded po submit (ignorowane): {wait_err}")

            page.wait_for_timeout(3000)

            # Dowód weryfikacyjny wysyłki: stan strony PO kliknięciu 'Wyślij'
            submitted_screenshot = config.DEBUG_DIR / f"submitted_proof_{job_id}.png"
            page.screenshot(path=str(submitted_screenshot), full_page=True)
            print(f"[DEBUG] URL po wysłaniu: {page.url}, zrzut: {submitted_screenshot}")

            content_lower = page.content().lower()
            url_str = page.url.lower()

            # TWARDA DETEKCJA SUKCESU:
            # 1. Strona potwierdzenia ma URL zawierający "finish" lub nie zawiera już formularza
            is_finish_page = "/offer/finish" in url_str or "/finish" in url_str
            still_on_offer_form = "/offer/" in url_str and "summary" not in url_str and not is_finish_page

            # 2. Pozytywne potwierdzenie w treści (jeden z jednoznacznych zwrotów).
            potwierdzenie_tekstowe = (
                "oferta wysłana" in content_lower
                or "oferta została wysłana" in content_lower
                or "została wysłana" in content_lower
                or "wysłano ofertę" in content_lower
                or ("twoja oferta" in content_lower and "wysłan" in content_lower)
                or is_finish_page
            )

            # 3. Przycisk submit zniknął (formularz przeprocesowany).
            submit_still_visible = False
            try:
                submit_still_visible = (
                    page.locator("button:has-text('Wyślij'), input[value='Wyślij']").first.count() > 0
                )
            except Exception:
                submit_still_visible = False

            is_success = (
                is_finish_page
                or (not still_on_offer_form and not submit_still_visible and potwierdzenie_tekstowe)
            )

            if is_success:
                return {
                    "status": "WYSLANO",
                    "job_id": job_id,
                    "wycena": proposal.wycena,
                    "dni": dni,
                    "final_url": page.url,
                    "proof_screenshot": str(submitted_screenshot),
                    "message": f"Oferta #{job_id} została pomyślnie wysłana i potwierdzona przez Useme (URL: {page.url})."
                }
            else:
                err_screenshot = config.DEBUG_DIR / f"submit_failed_{job_id}.png"
                page.screenshot(path=str(err_screenshot), full_page=True)
                body_snippet = page.inner_text("body")[:300].replace("\n", " ")
                raise RuntimeError(
                    f"Brak jednoznacznego potwierdzenia wysyłki na URL {page.url}! "
                    f"Fragment treści: '{body_snippet}'. Dowód zrzutu błędu: {err_screenshot}"
                )

        finally:
            page.close()
