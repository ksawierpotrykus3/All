# -*- coding: utf-8 -*-
"""Główny silnik (Skeleton) – Ofertowarka Useme.

Koordynuje cały proces od pobrania do przygotowania wysyłki.
Raportuje postęp w czasie rzeczywistym do Cortexa (cortex-app/data/pipelines/useme/stan.json).
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
from ai_pipeline import get_ai_pipeline
from browser_driver import BrowserDriver
from cortex_bridge import Chain
from form_driver import AuthenticationRequiredError, FormDriver
from storage import Storage


def run_pipeline(dry_run: bool = config.DRY_RUN) -> Dict[str, Any]:
    chain = Chain(
        id="useme-bot",
        nazwa="Automatyczna Ofertowarka Useme (Bot)",
        opis="Proces pobierania zleceń, selekcji, wyceny oraz wypełniania formularzy Useme",
        silnik="Playwright + AI Slots",
        wyzwalacz="manual"
    )
    storage = Storage()
    ai = get_ai_pipeline()
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "nowe_zlecenia": 0,
        "przetworzone": 0,
        "wyniki": []
    }

    with BrowserDriver(headless=config.HEADLESS) as driver:
        # Krok 1: Weryfikacja sesji
        with chain.step("Weryfikacja sesji i połączenia", typ="kod",
                        opis="Otwiera Useme i sprawdza, czy jesteś zalogowany oraz czy strona działa poprawnie.") as krok:
            krok.log("Sprawdzam dostępność Useme i status sesji...")
            # Sprawdzenie wykonamy na stronie głównej lub pierwszej kategorii
            page = driver.context.new_page()
            try:
                page.goto(config.CATEGORY_URLS["programowanie-i-it"], wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
                driver.dismiss_cookie_banner(page)
                logged_in = driver.check_logged_in(page)
                krok.wyjscie = f"Połączenie OK. Zalogowany: {logged_in}"
                krok.log(krok.wyjscie)
            finally:
                page.close()

        # Krok 2: Pobranie list zleceń
        wszystkie_zlecenia: List[Dict[str, Any]] = []
        with chain.step("Pobranie zleceń z kategorii IT i Serwisy", typ="kod",
                        opis="Przegląda listy zleceń w kategoriach IT i Serwisy i zbiera wszystkie dostępne ogłoszenia.") as krok:
            for cat_key in config.CATEGORY_URLS.keys():
                krok.log(f"Pobieranie zleceń z kategorii: {cat_key}...")
                jobs = driver.fetch_category_jobs(cat_key)
                wszystkie_zlecenia.extend(jobs)
                krok.log(f"Znaleziono {len(jobs)} zleceń w {cat_key}")
            krok.wyjscie = f"Łącznie pobrano {len(wszystkie_zlecenia)} ofert z listy"

        # Krok 3: Sprawdzenie nowości w magazynie (Deduplikacja)
        nowe_zlecenia: List[Dict[str, Any]] = []
        with chain.step("Deduplikacja w magazynie", typ="kod",
                        opis="Porównuje pobrane ogłoszenia z zapisanymi wcześniej i wybiera tylko nowe, których jeszcze nie widzieliśmy.") as krok:
            for job in wszystkie_zlecenia:
                if not storage.exists(job["id"], job["category"]):
                    storage.save_new_job(job, job["category"])
                    nowe_zlecenia.append(job)
                else:
                    krok.log(f"Oferta {job['id']} już istnieje w magazynie – pomijam.")
            
            # W trybie demonstracyjnym DRY-RUN: jeśli wszystkie już są w magazynie,
            # weź 1 najnowszą ofertę do sprawdzenia formularza.
            # W trybie WYSYŁKI NA ŻYWO (dry_run=False): absolutny zakaz wysyłania starych ofert!
            if not nowe_zlecenia and wszystkie_zlecenia and dry_run:
                krok.log("[INFO] Wszystkie oferty były już w bazie. W trybie DRY-RUN testuję 1 najnowszą.")
                nowe_zlecenia = [wszystkie_zlecenia[0]]

            report["nowe_zlecenia"] = len(nowe_zlecenia)
            krok.wyjscie = f"Wytypowano {len(nowe_zlecenia)} ofert do przetworzenia"

        # Krok 4: Pobranie pełnych detali dla wszystkich nowych zleceń
        with chain.step("Pobranie pełnych detali nowych zleceń", typ="kod",
                        opis="Wchodzi w każde nowe ogłoszenie na Useme i pobiera jego pełny opis przed selekcją.") as krok:
            for job in nowe_zlecenia:
                job_id = job["id"]
                krok.log(f"Pobieranie pełnego opisu dla #{job_id} ({job.get('title', '')[:30]}...)...")
                try:
                    details = driver.fetch_job_details(job["url"])
                    job.update(details)
                    storage.update_job(job_id, {"full_details": details, "status": "POBRANO_DETALE"})
                except Exception as e:
                    krok.log(f"[WARN] Błąd pobierania detali #{job_id}: {e}")
            krok.wyjscie = f"Pobrano pełne opisy dla {len(nowe_zlecenia)} nowych zleceń"

        # Krok 5: Selekcja przez AI
        wybrane_oferty: List[Dict[str, Any]] = []
        with chain.step("Selekcja zleceń przez AI", typ="ai",
                        opis="AI czyta pełne opisy nowych ogłoszeń i decyduje, które pasują do naszych umiejętności — resztę odrzuca.") as krok:
            krok.narzedzie = "AI Pipeline"
            wybrane_oferty = ai.filter_offers(nowe_zlecenia)
            krok.wyjscie = f"AI zakwalifikowało {len(wybrane_oferty)} z {len(nowe_zlecenia)} ofert"
            krok.log(krok.wyjscie)

        # Krok 6 & 7: Przetwarzanie wyselekcjonowanych zleceń
        form_driver = FormDriver(driver.context, dry_run=dry_run)

        for job in wybrane_oferty:
            job_id = job["id"]
            try:
                # Twardy bezpiecznik: nie wysyłaj dwa razy tej samej oferty!
                existing_record = storage.load_job(job_id)
                if existing_record and existing_record.get("status") == "WYSLANO":
                    print(f"[BLOKADA] Oferta #{job_id} ma już status WYSLANO w magazynie. Pomijam.")
                    report["wyniki"].append({"job_id": job_id, "status": "JUZ_WYSLANO", "message": "Oferta była już wcześniej wysłana."})
                    continue

                # Upewnienie się, że mamy pełne detale zlecenia
                if not job.get("full_description"):
                    details = driver.fetch_job_details(job["url"])
                    job.update(details)
                    storage.update_job(job_id, {"full_details": details, "status": "POBRANO_DETALE"})

                # Generowanie propozycji przez AI (1 czat = 1 oferta)
                with chain.step(f"Generowanie wyceny i oferty #{job_id}", typ="ai",
                                opis="AI przygotowuje gotową treść oferty oraz proponuje stawkę i liczbę dni pracy dla tego zlecenia.") as krok:
                    proposal = ai.generate_proposal(job)
                    storage.update_job(job_id, {
                        "ai_proposal": {
                            "opis": proposal.opis,
                            "wycena": proposal.wycena,
                            "dni": proposal.dni,
                            "powod": proposal.powod_wyboru
                        },
                        "status": "PRZYGOTOWANA"
                    })
                    krok.wyjscie = f"Wycena: {proposal.wycena} PLN, Dni: {proposal.dni}"
                    krok.log(f"Treść oferty:\n{proposal.opis[:200]}...")

                # Wypełnienie formularza (DRY-RUN)
                with chain.step(f"Formularz Useme #{job_id} ({'DRY-RUN' if dry_run else 'WYSYŁKA'})", typ="kod",
                                opis="Wypełnia formularz odpowiedzi na ogłoszenie gotową treścią oferty i wyceną (w trybie DRY-RUN tylko przygotowuje, nie wysyła).") as krok:
                    try:
                        res = form_driver.fill_and_prepare_offer(job_id, proposal)
                        storage.update_job(job_id, {"submission_result": res, "status": res["status"]})
                        krok.wyjscie = f"{res['status']}: {res['message']}"
                        report["wyniki"].append(res)
                        report["przetworzone"] += 1
                    except AuthenticationRequiredError as auth_err:
                        krok.log(f"[STOP] {auth_err}")
                        krok.wyjscie = "Wymagane logowanie (cookies wygasły)"
                        report["wyniki"].append({"job_id": job_id, "status": "AUTH_REQUIRED", "error": str(auth_err)})
                        break  # Brak sesji uniemożliwia dalsze formularze
                    except Exception as form_err:
                        krok.log(f"[BŁĄD FORMULARZA] {form_err}")
                        krok.wyjscie = f"BŁĄD: {form_err}"
                        storage.update_job(job_id, {"status": "BLAD_FORMULARZA", "error": str(form_err)})
                        report["wyniki"].append({"job_id": job_id, "status": "BLAD_FORMULARZA", "error": str(form_err)})

            except Exception as job_err:
                print(f"[BŁĄD OFERTY #{job_id}] {job_err}", flush=True)
                storage.update_job(job_id, {"status": "BLAD_PRZETWARZANIA", "error": str(job_err)})
                report["wyniki"].append({"job_id": job_id, "status": "BLAD_PRZETWARZANIA", "error": str(job_err)})
                continue

    return report


if __name__ == "__main__":
    print("=== START USEME CORE ENGINE ===")
    wyniki = run_pipeline(dry_run=config.DRY_RUN)
    print("=== WYNIKI RUNU ===")
    print(wyniki)
