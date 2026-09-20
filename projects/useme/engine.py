# -*- coding: utf-8 -*-
"""Główny silnik (Skeleton) – Ofertowarka Useme.

Koordynuje cały proces od pobrania do przygotowania wysyłki.
Raportuje postęp w czasie rzeczywistym do Cortexa (cortex-app/data/pipelines/useme/stan.json).

Multi-account: silnik iteruje po kontach zwróconych przez config.aktywne_konta().
Jeśli istnieje tylko 1 plik cookies (konto 2 puste), działa dokładnie jak wcześniej.
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
import bezpieczenstwo
from ai_pipeline import ProposalResult, get_ai_pipeline
from browser_driver import BrowserDriver
from cortex_bridge import Chain
from form_driver import AuthenticationRequiredError, FormDriver
from storage import Storage


def czekaj_na_dostepnosc_useme(interval_s: int = 60, max_prob: int = 180) -> bool:
    """Sprawdza co interval_s sekund, czy portal Useme działa (status 200).
    
    W przypadku awarii serwerowej (HTTP 503 'Oops!'), bot samoczynnie odczekuje
    i sprawdza portal co minutę, ruszając natychmiast po jego przywróceniu.
    """
    from curl_cffi import requests as cffi_requests
    print("[USEME MONITOR] Weryfikuję dostępność portalu Useme...", flush=True)
    for proba in range(1, max_prob + 1):
        if bezpieczenstwo.czy_stop():
            print("[STOP] Wykryto plik STOP podczas oczekiwania na Useme.", flush=True)
            return False
        try:
            r = cffi_requests.get("https://useme.com/pl/", impersonate="chrome120", timeout=15)
            if r.status_code == 200 and "error-page" not in r.text.lower() and "oops" not in r.text.lower():
                print(f"[USEME ONLINE] Portal Useme działa poprawnie (status 200). Uruchamiam proces!", flush=True)
                return True
            else:
                print(f"[USEME OFFLINE] Portal Useme niedostępny (HTTP {r.status_code}, 'Oops!'). Czekam {interval_s}s... (próba {proba}/{max_prob})", flush=True)
        except Exception as e:
            print(f"[USEME OFFLINE] Błąd połączenia ({e}). Czekam {interval_s}s... (próba {proba}/{max_prob})", flush=True)
        time.sleep(interval_s)
    return False


def run_pipeline(dry_run: bool = config.DRY_RUN, auto_wait_useme: bool = True) -> Dict[str, Any]:
    if auto_wait_useme:
        if not czekaj_na_dostepnosc_useme(interval_s=60):
            return {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "nowe_zlecenia": 0,
                    "przetworzone": 0, "wyniki": [], "zatrzymano": "USEME_OFFLINE_LUB_STOP"}
    if config.ZBIERACZ_AKTYWNY:
        from zbieracz_danych import uruchom_zbieranie
        uruchom_zbieranie()
    else:
        print("[ZBIERACZ] Wylaczony (config.ZBIERACZ_AKTYWNY=False) - pomijam weryfikacje skrzynki.", flush=True)
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

    # --- KILL SWITCH: jesli istnieje plik STOP, nie startujemy ---
    if bezpieczenstwo.czy_stop():
        print(f"[STOP] Znaleziono plik {config.STOP_FILE}. Bot nie startuje. Usun plik, aby wznowic.", flush=True)
        return {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "nowe_zlecenia": 0,
                "przetworzone": 0, "wyniki": [], "zatrzymano": "STOP_FILE"}

    limiter = bezpieczenstwo.RunLimiter()
    print(f"[LIMITY] Brak limitu dziennego. Max czas runu: {config.MAX_RUN_MINUTES} min.", flush=True)

    # Konta z realnie istniejącym plikiem cookies. Puste miejsce -> tylko konto 1.
    konta = config.aktywne_konta()
    if not konta:
        # Bezpiecznik: brak jakiegokolwiek pliku cookies -> zachowaj konto domyślne
        # (identycznie jak przed multi-kontem; BrowserDriver i tak zgłosi brak sesji).
        konta = [{"id": "konto1", "nazwa": "Ksawier", "cookies_path": config.COOKIES_PATH}]

    print(f"[KONTA] Aktywne konta w tym runie: {[k.get('id') for k in konta]}", flush=True)

    for konto in konta:
        if bezpieczenstwo.czy_stop():
            print("[STOP] Wykryto plik STOP w trakcie runu - zatrzymuje.", flush=True)
            report["zatrzymano"] = "STOP_FILE"
            break
        if limiter.przekroczono():
            print(f"[LIMIT] Przekroczono max czas runu ({config.MAX_RUN_MINUTES} min) - zatrzymuje.", flush=True)
            report["zatrzymano"] = "MAX_CZAS"
            break
        _process_account(konto, chain, storage, ai, report, dry_run, limiter)

    return report


def _process_account(konto: Dict[str, Any], chain, storage, ai, report: Dict[str, Any],
                     dry_run: bool, limiter=None) -> None:
    """Przetwarza jeden pełny cykl dla pojedynczego konta (własna sesja cookies)."""
    konto_id = konto.get("id", "konto1")
    cookies_path = konto.get("cookies_path")

    with BrowserDriver(cookies_path=cookies_path, headless=config.HEADLESS) as driver:
        # Krok 1: Weryfikacja sesji
        with chain.step(f"Weryfikacja sesji i połączenia ({konto_id})", typ="kod",
                        opis="Otwiera Useme i sprawdza, czy jesteś zalogowany oraz czy strona działa poprawnie.") as krok:
            krok.log(f"Sprawdzam dostępność Useme i status sesji dla {konto_id}...")
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
        with chain.step(f"Pobranie zleceń z kategorii IT i Serwisy ({konto_id})", typ="kod",
                        opis="Przegląda listy zleceń w kategoriach IT i Serwisy i zbiera wszystkie dostępne ogłoszenia.") as krok:
            for cat_key in config.CATEGORY_URLS.keys():
                krok.log(f"Pobieranie zleceń z kategorii: {cat_key}...")
                jobs = driver.fetch_category_jobs(cat_key, should_stop_fn=lambda jid, c=cat_key: storage.exists(jid, c))
                wszystkie_zlecenia.extend(jobs)
                krok.log(f"Znaleziono {len(jobs)} nowych zleceń w {cat_key}")
            krok.wyjscie = f"Łącznie pobrano {len(wszystkie_zlecenia)} ofert z listy"

        # Krok 3: Sprawdzenie nowości w magazynie (Deduplikacja)
        nowe_zlecenia: List[Dict[str, Any]] = []
        with chain.step(f"Deduplikacja w magazynie ({konto_id})", typ="kod",
                        opis="Porównuje pobrane ogłoszenia z zapisanymi wcześniej i wybiera tylko nowe, których jeszcze nie widzieliśmy.") as krok:
            for job in wszystkie_zlecenia:
                if storage.exists(job["id"], job["category"]):
                    krok.log(f"[STOP DEDUPLIKACJA] Trafiono na zlecenie w systemie #{job['id']}. Pomijam to zlecenie i WSZYSTKIE starsze!")
                    break
                job["konto"] = konto_id
                storage.save_new_job(job, job["category"])
                nowe_zlecenia.append(job)

            report["nowe_zlecenia"] += len(nowe_zlecenia)
            krok.wyjscie = f"Wytypowano {len(nowe_zlecenia)} nowych ofert do przetworzenia"

        # Krok 4: Pobranie pełnych detali dla wszystkich nowych zleceń
        with chain.step(f"Pobranie pełnych detali nowych zleceń ({konto_id})", typ="kod",
                        opis="Wchodzi w każde nowe ogłoszenie na Useme i pobiera jego pełny opis przed selekcją.") as krok:
            for job in nowe_zlecenia:
                job_id = job["id"]
                krok.log(f"Pobieranie pełnego opisu dla #{job_id} ({job.get('title', '')[:30]}...)...")
                try:
                    details = driver.fetch_job_details(job["url"])
                    job.update(details)
                    updates = {"full_details": details, "status": "POBRANO_DETALE"}
                    if details.get("author_id"):
                        updates["author_id"] = details["author_id"]
                        updates["author"] = details.get("author", job.get("author", ""))
                    storage.update_job(job_id, updates)
                except Exception as e:
                    krok.log(f"[WARN] Błąd pobierania detali #{job_id}: {e}")
            krok.wyjscie = f"Pobrano pełne opisy dla {len(nowe_zlecenia)} nowych zleceń"

        # Krok 5: Selekcja przez AI
        wybrane_oferty: List[Dict[str, Any]] = []
        with chain.step(f"Selekcja zleceń przez AI ({konto_id})", typ="ai",
                        opis="AI czyta pełne opisy nowych ogłoszeń i decyduje, które pasują do naszych umiejętności — resztę odrzuca.") as krok:
            krok.narzedzie = "AI Pipeline"
            wybrane_oferty = ai.filter_offers(nowe_zlecenia)
            krok.wyjscie = f"AI zakwalifikowało {len(wybrane_oferty)} z {len(nowe_zlecenia)} ofert"
            krok.log(krok.wyjscie)

        # Krok 6 & 7: Przetwarzanie wyselekcjonowanych zleceń
        form_driver = FormDriver(driver.context, dry_run=dry_run)

        # Dołącz zlecenia z magazynu z gotową propozycją AI, których formularz wcześniej nie przeszedł (np. przez headless)
        do_wyslania = list(wybrane_oferty)
        seen_ids = {str(j.get("id")) for j in do_wyslania}
        for kat in config.CATEGORY_URLS.keys():
            slug = storage._get_category_slug(kat)
            for jf in (storage.magazyn_dir / slug).glob("*.json"):
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        jd = json.load(f)
                    jid = str(jd.get("id", "")).strip()
                    fd = jd.get("full_details") or {}
                    is_already = (
                        fd.get("is_already_submitted")
                        or storage.czy_konto_juz_oferowalo(jid, konto_id)
                    )
                    if (jid and jid not in seen_ids 
                            and not is_already
                            and jd.get("status") in ["BLAD_FORMULARZA", "PRZYGOTOWANA", "BLAD_PRZETWARZANIA"]
                            and (jd.get("ai_proposal") or {}).get("opis")):
                        do_wyslania.append(jd)
                        seen_ids.add(jid)
                except Exception:
                    pass

        print(f"[KOLEJKA] Do wysłania w tym runie: {len(do_wyslania)} ofert z magazynu/selekcji", flush=True)
        for job in do_wyslania:
            job_id = job["id"]
            try:
                # --- KILL SWITCH w trakcie przetwarzania ofert ---
                if bezpieczenstwo.czy_stop():
                    print("[STOP] Wykryto plik STOP - przerywam przetwarzanie ofert.", flush=True)
                    report["zatrzymano"] = "STOP_FILE"
                    return
                # --- LIMIT CZASU RUNU ---
                if limiter is not None and limiter.przekroczono():
                    print(f"[LIMIT] Max czas runu przekroczony - przerywam.", flush=True)
                    report["zatrzymano"] = "MAX_CZAS"
                    return

                # Twardy bezpiecznik: to KONKRETNE konto nie moze wyslac oferty dwa razy.
                # Uwaga: nie blokujemy po samym statusie globalnym "WYSLANO", bo wtedy
                # Konto 2 nigdy nie wyslaloby swojej oferty po tym, jak zrobilo to Konto 1.
                if storage.czy_konto_juz_oferowalo(job_id, konto_id):
                    print(f"[BLOKADA] Konto {konto_id} zlozylo juz oferte na #{job_id}. Pomijam.")
                    report["wyniki"].append({"job_id": job_id, "konto": konto_id, "status": "JUZ_KONTO_OFEROWALO"})
                    continue

                # Upewnienie się, że mamy pełne detale zlecenia (tylko dla zleceń bez gotowej propozycji)
                if not job.get("ai_proposal") and not job.get("full_description"):
                    details = driver.fetch_job_details(job["url"])
                    job.update(details)
                    storage.update_job(job_id, {"full_details": details, "status": "POBRANO_DETALE"})

                # Detekcja powtórki: ten sam klient (author_id) dostał już od nas ofertę?
                author_id = str(job.get("author_id", "")).strip()
                previous_offers: List[Dict[str, Any]] = []
                if author_id and author_id.lower() != "anonim":
                    for h in storage.find_by_author(author_id):
                        if str(h.get("id", "")) == str(job_id):
                            continue
                        ai_prop = h.get("ai_proposal", {}) or {}
                        # Liczymy TYLKO oferty, które faktycznie napisaliśmy.
                        # Inaczej do "poprzednich" wpadłyby zlecenia tego klienta
                        # zapisane w magazynie, do których jeszcze nie wysłaliśmy oferty.
                        if not (ai_prop.get("opis") or "").strip():
                            continue
                        previous_offers.append({
                            "job_id": h.get("id"),
                            "title": h.get("title", ""),
                            "opis": (ai_prop.get("opis") or "")[:600],
                            "wycena": ai_prop.get("wycena"),
                            "dni": ai_prop.get("dni"),
                        })
                job["previous_offers"] = previous_offers
                job["variation_seed"] = (abs(hash(f"{author_id}_{konto_id}")) % 5) if author_id else (abs(hash(f"{job_id}_{konto_id}")) % 5)
                # Seed stawki PER OFERTA: każde konto (oferta) losuje stawkę oddzielnie.
                job["stawka_seed"] = f"{job_id}-{konto_id}"
                # Tryb oferty: tryb meta całkowicie wyłączony, zawsze konserwatywny
                tryb = getattr(config, "DOMYSLNY_TRYB", "konserwatywny")
                job["tryb"] = tryb
                if previous_offers:
                    print(f"[ANTY-POWTÓRKA] Klient {author_id} ma już {len(previous_offers)} ofert – wymuszam inny styl (seed={job['variation_seed']}).")

                # Generowanie propozycji przez AI (1 czat = 1 oferta)
                with chain.step(f"Generowanie wyceny i oferty #{job_id} ({konto_id}, {tryb})", typ="ai",
                                opis="AI przygotowuje gotową treść oferty oraz proponuje stawkę i liczbę dni pracy dla tego zlecenia.") as krok:
                    saved_prop = job.get("ai_proposal") or (storage.load_job(job_id) or {}).get("ai_proposal")
                    if saved_prop and saved_prop.get("opis"):
                        krok.log(f"Wczytano gotową propozycję z bazy dla #{job_id} ({saved_prop.get('wycena')} zł / {saved_prop.get('dni')} dni).")
                        proposal = ProposalResult(
                            opis=saved_prop["opis"],
                            wycena=saved_prop.get("wycena", 1500),
                            dni=saved_prop.get("dni", 7),
                            powod_wyboru=saved_prop.get("powod", "Zapisana w magazynie"),
                            metadata=saved_prop.get("metadata")
                        )
                    else:
                        if previous_offers:
                            krok.log(f"Uwaga: klient {author_id} ma już {len(previous_offers)} ofert – AI ma napisać INACZEJ.")
                        proposal = ai.generate_proposal(job)

                    # BEZPIECZEŃSTWO: cap długości opisu (ochrona przed gigantycznym tekstem).
                    if proposal.opis and len(proposal.opis) > config.MAX_OPIS_DLUGOSC:
                        print(f"[CAP] Oferta #{job_id}: opis {len(proposal.opis)} znakow > "
                              f"{config.MAX_OPIS_DLUGOSC} - obcinam.", flush=True)
                        proposal.opis = proposal.opis[:config.MAX_OPIS_DLUGOSC].rstrip()

                    # SANITY-CHECK wyceny: jesli kalkulator oznaczył wycene jako podejrzanie
                    # niska, NIE wysylamy w trybie live - tylko oznaczamy do przegladu.
                    sanity_ok = True
                    if isinstance(proposal.metadata, dict):
                        sanity_ok = proposal.metadata.get("sanity_ok", True)
                    if (not dry_run) and (not sanity_ok):
                        print(f"[SANITY-BLOK] Oferta #{job_id}: wycena podejrzanie niska - pomijam wysylke.", flush=True)
                        storage.update_job(job_id, {"status": "SANITY_BLOK"})
                        report["wyniki"].append({"job_id": job_id, "konto": konto_id, "status": "SANITY_BLOK"})
                        continue

                    storage.update_job(job_id, {
                        "ai_proposal": {
                            "opis": proposal.opis,
                            "wycena": proposal.wycena,
                            "dni": proposal.dni,
                            "powod": proposal.powod_wyboru
                        },
                        "konto": konto_id,
                        "status": "PRZYGOTOWANA"
                    })

                    # ZAPIS OFERTY per konto: pelny kontekst eksperymentu.
                    stawka_z_rozbicia = None
                    try:
                        meta = (proposal.metadata or {})
                        stawka_z_rozbicia = meta.get("stawka")
                    except Exception:
                        pass
                    storage.zapisz_oferte(job_id, {
                        "job_id": str(job_id),
                        "konto": konto_id,
                        "tryb": tryb,
                        "wycena": proposal.wycena,
                        "dni": proposal.dni,
                        "stawka": stawka_z_rozbicia,
                        "stawka_seed": job.get("stawka_seed"),
                        "variation_seed": job.get("variation_seed"),
                        "dlugosc_opisu": len(proposal.opis or ""),
                        "opis": proposal.opis,
                    })
                    krok.log(f"[ZAPIS] Oferta ({konto_id}, {tryb}): {proposal.wycena} zl / {proposal.dni} dni, "
                             f"{len(proposal.opis or '')} znakow.")

                    # GLOBALNY wykrywacz duplikatow: czy nie piszemy wszystkich ofert tak samo?
                    try:
                        from ai_pipeline import sprawdz_globalne_duplikaty
                        dups = sprawdz_globalne_duplikaty(proposal.opis, storage, wlasne_job_id=str(job_id))
                        if dups:
                            krok.log(f"[GLOBAL-DUP] Oferta podobna do: {dups[:3]}")
                            print(f"[GLOBAL-DUP] #{job_id} ({konto_id}): zbyt podobna do {dups[:3]}", flush=True)
                    except Exception as e:
                        print(f"[GLOBAL-DUP] blad sprawdzania: {e}", flush=True)
                    krok.wyjscie = f"Wycena: {proposal.wycena} PLN, Dni: {proposal.dni}"
                    krok.log(f"Treść oferty:\n{proposal.opis[:200]}...")

                # Wypełnienie formularza (DRY-RUN)
                with chain.step(f"Formularz Useme #{job_id} ({konto_id}, {'DRY-RUN' if dry_run else 'WYSYŁKA'})", typ="kod",
                                opis="Wypełnia formularz odpowiedzi na ogłoszenie gotową treścią oferty i wyceną (w trybie DRY-RUN tylko przygotowuje, nie wysyła).") as krok:
                    # Inicjalizacja przed try: bez tego wyjątek w fill_and_prepare_offer
                    # powodował UnboundLocalError przy odwołaniu do `res` w except.
                    res = None
                    try:
                        res = form_driver.fill_and_prepare_offer(job_id, proposal)
                        res["konto"] = konto_id
                        updates = {"submission_result": res, "status": res["status"], "konto": konto_id}
                        # data_wyslania jest wymagane przez zbieracz (zbieracz_danych.py) do
                        # liczenia wieku oferty. Bez niego zbieracz zawsze zwracal "brak daty".
                        if res.get("status") == "WYSLANO":
                            updates["data_wyslania"] = datetime.now().isoformat()
                        storage.update_job(job_id, updates)
                        krok.wyjscie = f"{res['status']}: {res['message']}"
                        report["wyniki"].append(res)
                        report["przetworzone"] += 1
                        # LICZNIK DZIENNY: tylko realna wysylka (nie DRY_RUN) sie liczy.
                        if not dry_run:
                            ile = bezpieczenstwo.zapisz_wyslana_oferte()
                            krok.log(f"[STATS] Wyslano dzisiaj lacznie: {ile}")
                            # Odstep miedzy ofertami na tym samym koncie (naturalne tempo).
                            delay_s = getattr(config, "MIN_DELAY_BETWEEN_OFFERS_S", 0)
                            if delay_s > 0:
                                time.sleep(delay_s)
                    except AuthenticationRequiredError as auth_err:
                        krok.log(f"[STOP] {auth_err}")
                        krok.wyjscie = "Wymagane logowanie (cookies wygasły)"
                        report["wyniki"].append({"job_id": job_id, "konto": konto_id, "status": "AUTH_REQUIRED", "error": str(auth_err)})
                        break  # Brak sesji uniemożliwia dalsze formularze
                    except Exception as form_err:
                        krok.log(f"[BŁĄD FORMULARZA] {form_err}")
                        krok.wyjscie = f"BŁĄD: {form_err}"
                        if res is None or res.get("status") != "WYSLANO":
                            storage.update_job(job_id, {"status": "BLAD_FORMULARZA", "error": str(form_err)})
                            report["wyniki"].append({"job_id": job_id, "konto": konto_id, "status": "BLAD_FORMULARZA", "error": str(form_err)})

            except Exception as job_err:
                print(f"[BŁĄD OFERTY #{job_id}] {job_err}", flush=True)
                storage.update_job(job_id, {"status": "BLAD_PRZETWARZANIA", "error": str(job_err)})
                report["wyniki"].append({"job_id": job_id, "konto": konto_id, "status": "BLAD_PRZETWARZANIA", "error": str(job_err)})
                continue
            finally:
                job_delay = random.uniform(*getattr(config, "INTER_JOB_DELAY_RANGE", (6.0, 12.0)))
                print(f"[PACING] Odstep przed nastepnym zleceniem: {job_delay:.1f}s...", flush=True)
                time.sleep(job_delay)


if __name__ == "__main__":
    print("=== START USEME CORE ENGINE ===")
    dry = config.DRY_RUN
    if "--dry-run" in sys.argv or "-d" in sys.argv:
        dry = True
        print("[TRYB] Wymuszono tryb DRY-RUN z flagi CLI (bezpieczny test bez ostatecznego kliknięcia Wyślij).", flush=True)
    elif "--live" in sys.argv:
        dry = False
        print("[TRYB] Wymuszono tryb LIVE z flagi CLI (rzeczywista wysyłka ofert).", flush=True)
    else:
        print(f"[TRYB] Używam domyślnego trybu z config.py: {'DRY-RUN' if dry else 'LIVE'}", flush=True)
    wyniki = run_pipeline(dry_run=dry)
    print("=== WYNIKI RUNU ===")
    print(wyniki)