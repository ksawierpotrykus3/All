# -*- coding: utf-8 -*-
"""Glowny silnik - Ofertowarka Freelancer.pl.

Koordynuje proces: weryfikacja sesji -> pobranie projektow (API) -> deduplikacja
-> detale -> selekcja AI -> generowanie oferty -> formularz (DRY_RUN/wysylka).

Raportuje postep do Cortexa (cortex-app/data/pipelines/freelancer-bot/stan.json).
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
from form_driver import AccountBiddingBlockedError, AuthenticationRequiredError, FormDriver
from storage import Storage


def run_pipeline(dry_run: bool = config.DRY_RUN) -> Dict[str, Any]:
    chain = Chain(
        id="freelancer-bot",
        nazwa="Automatyczna Ofertowarka Freelancer.pl",
        opis="Pobieranie projektow (API), selekcja, wycena oraz skladanie ofert na freelancer.pl",
        silnik="Playwright + API + AI Slots",
        wyzwalacz="manual",
    )
    storage = Storage()
    ai = get_ai_pipeline()
    report = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
              "nowe_zlecenia": 0, "przetworzone": 0, "wyniki": []}

    with BrowserDriver(headless=config.HEADLESS) as driver:
        # Krok 1: Weryfikacja sesji i stanu konta
        with chain.step("Weryfikacja sesji i salda konta", typ="kod",
                        opis="Sprawdza cookies sesji oraz saldo konta (blokada bidowania przy ujemnym saldzie).") as krok:
            acc = driver.check_account()
            krok.wyjscie = (f"Zalogowany: {acc['logged_in']} | user_id={acc['user_id']} | "
                            f"saldo={acc['balance_usd']} USD | can_bid={acc['can_bid']}")
            krok.log(krok.wyjscie)
            for n in acc.get("notes", []):
                krok.log("[UWAGA] " + n)
            report["konto"] = acc
            if not acc["logged_in"]:
                raise AuthenticationRequiredError("Brak aktywnej sesji freelancera (cookies).")

        # Krok 2: Pobranie listy projektow per kategoria (API)
        wszystkie: List[Dict[str, Any]] = []
        with chain.step("Pobranie projektow z kategorii (API)", typ="kod",
                        opis="Pobiera najnowsze projekty z kategorii IT/web/AI/sklepy/scraping przez API, pomijajac lokalne.") as krok:
            for cat_key in config.CATEGORY_JOBS.keys():
                jobs = driver.fetch_category_jobs(cat_key)
                krok.log(f"{cat_key}: {len(jobs)} projektow")
                wszystkie.extend(jobs)
            krok.wyjscie = f"Lacznie pobrano {len(wszystkie)} projektow"

        # Krok 3: Deduplikacja
        nowe: List[Dict[str, Any]] = []
        with chain.step("Deduplikacja w magazynie", typ="kod",
                        opis="Porownuje z magazynem i wybiera tylko nowe projekty.") as krok:
            for job in wszystkie:
                if not storage.exists(job["id"], job["category"]):
                    storage.save_new_job(job, job["category"])
                    nowe.append(job)
                else:
                    krok.log(f"Projekt {job['id']} juz w magazynie - pomijam.")
            if not nowe and wszystkie and dry_run:
                krok.log("[INFO] Wszystkie w magazynie; DRY-RUN testuje 1 najnowszy.")
                nowe = [wszystkie[0]]
            report["nowe_zlecenia"] = len(nowe)
            krok.wyjscie = f"Wytypowano {len(nowe)} projektow"

        # Krok 4: Pelne detale
        with chain.step("Pobranie pelnych detali", typ="kod",
                        opis="Pobiera pelny opis i dane wlasciciela dla nowych projektow przez API.") as krok:
            for job in nowe:
                try:
                    det = driver.fetch_job_details(job["id"])
                    job.update(det)
                    storage.update_job(job["id"], {"full_details": det, "status": "POBRANO_DETALE"})
                except Exception as e:
                    krok.log(f"[WARN] Detale #{job['id']}: {e}")
            krok.wyjscie = f"Pobrano detale dla {len(nowe)} projektow"

        # Krok 5: Selekcja AI
        with chain.step("Selekcja projektow przez AI", typ="ai",
                        opis="AI czyta opisy i decyduje, ktore projekty pasuja.") as krok:
            krok.narzedzie = "AI Pipeline"
            wybrane = ai.filter_offers(nowe)
            krok.wyjscie = f"AI zakwalifikowalo {len(wybrane)} z {len(nowe)}"
            krok.log(krok.wyjscie)

        # Krok 6/7: Przetwarzanie
        form = FormDriver(driver.context, dry_run=dry_run)
        for job in wybrane:
            jid = job["id"]
            try:
                existing = storage.load_job(jid)
                if existing and existing.get("status") in ("WYSLANO", "WYSLANO_OFERTE"):
                    print(f"[BLOKADA] #{jid} juz wyslany.")
                    report["wyniki"].append({"job_id": jid, "status": "JUZ_WYSLANO"})
                    continue
                if not job.get("full_description"):
                    det = driver.fetch_job_details(jid)
                    job.update(det)

                with chain.step(f"Generowanie oferty #{jid}", typ="ai",
                                opis="AI przygotowuje tresc oferty oraz stawke i dni.") as krok:
                    proposal = ai.generate_proposal(job)
                    storage.update_job(jid, {"ai_proposal": {
                        "opis": proposal.opis, "wycena": proposal.wycena,
                        "dni": proposal.dni, "powod": proposal.powod_wyboru},
                        "status": "PRZYGOTOWANA"})
                    krok.wyjscie = f"Wycena: {proposal.wycena}, Dni: {proposal.dni}"

                with chain.step(f"Formularz #{jid} ({'DRY-RUN' if dry_run else 'WYSYLKA'})", typ="kod",
                                opis="Wypelnia formularz Place Bid (w DRY-RUN zatrzymuje sie przed wysylka).") as krok:
                    try:
                        res = form.fill_and_prepare_offer(jid, job.get("seo_url", ""), proposal,
                                                          currency=job.get("currency", "USD"))
                        storage.update_job(jid, {"submission_result": res, "status": res["status"]})
                        krok.wyjscie = f"{res['status']}: {res.get('message','')}"
                        report["wyniki"].append(res)
                        report["przetworzone"] += 1
                    except AccountBiddingBlockedError as be:
                        krok.log(f"[STOP] {be}")
                        krok.wyjscie = "KONTO ZABLOKOWANE DO BIDOWANIA"
                        report["wyniki"].append({"job_id": jid, "status": "KONTO_ZABLOKOWANE", "error": str(be)})
                        break  # blokada konta - dalsze formularze nie maja sensu
                    except AuthenticationRequiredError as ae:
                        krok.log(f"[STOP] {ae}")
                        krok.wyjscie = "WYMAGANE LOGOWANIE"
                        report["wyniki"].append({"job_id": jid, "status": "AUTH_REQUIRED", "error": str(ae)})
                        break
            except Exception as je:
                print(f"[BLAD #{jid}] {je}")
                storage.update_job(jid, {"status": "BLAD_PRZETWARZANIA", "error": str(je)})
                report["wyniki"].append({"job_id": jid, "status": "BLAD_PRZETWARZANIA", "error": str(je)})
                continue

    return report


if __name__ == "__main__":
    print("=== START FREELANCER CORE ENGINE ===")
    wynik = run_pipeline(dry_run=config.DRY_RUN)
    print("=== WYNIKI RUNU ===")
    print(wynik)