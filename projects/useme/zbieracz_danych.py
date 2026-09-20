import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from config import TIMEOUT_DNI
from storage import Storage

logger = logging.getLogger(__name__)

def uruchom_zbieranie(magazyn_dir: Optional[Path] = None, dry_run: bool = False) -> None:
    """
    Główna funkcja zbieraczki. Przelatuje po zleceniach ze statusem WYSLANO,
    sprawdza czy minął TIMEOUT_DNI i aktualizuje ich status końcowy.
    """
    storage = Storage(magazyn_dir=magazyn_dir)
    wszystkie = storage.wszystkie_zlecenia()

    # Status oferty po realnej wysylce to "WYSLANO" (z litera O) - patrz form_driver.py.
    # Wczesniej zbieracz szukal "WYSLANA" (z litera A), przez co nie widzial ZADNEJ oferty.
    do_sprawdzenia = [o for o in wszystkie if o.get("status") == "WYSLANO"]

    if not do_sprawdzenia:
        logger.info("[ZBIERACZ] Brak ofert ze statusem WYSLANO do sprawdzenia.")
        return

    logger.info(f"[ZBIERACZ] Znaleziono {len(do_sprawdzenia)} ofert do weryfikacji.")
    
    for oferta in do_sprawdzenia:
        job_id = oferta.get("id")
        data_wyslania_str = oferta.get("data_wyslania")
        
        if not data_wyslania_str:
            logger.warning(f"[ZBIERACZ] Oferta {job_id} nie ma daty wysłania. Pomijam.")
            continue
            
        try:
            data_wyslania = datetime.fromisoformat(data_wyslania_str)
        except ValueError:
            logger.error(f"[ZBIERACZ] Błędny format daty dla {job_id}: {data_wyslania_str}")
            continue
            
        wiek = datetime.now() - data_wyslania
        
        if wiek < timedelta(days=TIMEOUT_DNI):
            logger.info(f"[ZBIERACZ] Oferta {job_id} czeka {wiek.days} dni. Pomijam (min. {TIMEOUT_DNI}).")
            continue
        
        logger.info(f"[ZBIERACZ] Weryfikuję ofertę {job_id} (wiek: {wiek.days} dni).")
        
        # Domyślny status końcowy, jeśli nic nie znajdziemy
        status_koncowy = "PROZNIA"
        
        if not dry_run:
            from browser_driver import BrowserDriver
            # BrowserDriver obsługuje context manager (__enter__/__exit__), więc 'with' jest bezpieczne
            with BrowserDriver() as driver:
                author_id = oferta.get("author_id")
                job_title = oferta.get("title", "")
                wynik_skrzynka = driver.sprawdz_skrzynke(author_id, data_wyslania.isoformat())
                wynik_powiadomienia = driver.sprawdz_powiadomienia(job_id, job_title)

                if wynik_skrzynka:
                    status_koncowy = "ODPOWIEDZ_KLIENTA"
                elif wynik_powiadomienia:
                    status_koncowy = "ZAMKNIETE"
        
        # Aktualizacja w storage
        storage.update_job(job_id, {
            "status_koncowy": status_koncowy,
            "data_weryfikacji": datetime.now().isoformat(),
            "status": status_koncowy
        })
        logger.info(f"[ZBIERACZ] Zaktualizowano {job_id} -> {status_koncowy}")