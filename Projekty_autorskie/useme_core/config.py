# -*- coding: utf-8 -*-
"""Konfiguracja główna silnika useme_core."""

from pathlib import Path

BASE_DIR = Path(__file__).parent
MAGAZYN_DIR = BASE_DIR / "magazyn"
MARKER_FILE = BASE_DIR / "marker.json"
COOKIES_PATH = BASE_DIR / "tech" / "cookies.json"
DEBUG_DIR = BASE_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# --- Konta (multi-account) ---
# Miejsce na 2 konta. Konto 1 = dotychczasowe (tech/cookies.json).
# Konto 2 = tech/cookies2.json (wystarczy wrzucić plik, wtedy się aktywuje).
# Jeśli plik cookies nie istnieje -> konto jest pomijane i wszystko działa
# dokładnie tak, jak działało do tej pory (1 konto).
ACCOUNTS = [
    {
        "id": "konto1",
        "nazwa": "Ksawier",
        "cookies_path": BASE_DIR / "tech" / "cookies.json",
    },
    {
        "id": "konto2",
        "nazwa": "Konto 2",
        "cookies_path": BASE_DIR / "tech" / "cookies2.json",
    },
]


def aktywne_konta() -> list:
    """Zwraca konta, które mają realnie plik cookies.

    Puste miejsce (brak cookies2.json) -> zwracana jest tylko lista z kontem 1,
    czyli zachowanie identyczne jak przed dodaniem multi-konta.
    """
    return [k for k in ACCOUNTS if Path(k["cookies_path"]).exists()]

# Kategorie monitorowane
CATEGORY_URLS = {
    "programowanie-i-it": "https://useme.com/pl/jobs/category/programowanie-i-it,35/",
    "serwisy-internetowe": "https://useme.com/pl/jobs/category/serwisy-internetowe,34/",
}

# Twarde flagi bezpieczeństwa
TIMEOUT_DNI = 3
DRY_RUN = False         # False: tryb wysyłki na żywo po autoryzacji użytkownika
USE_MOCK_AI = False     # False: uruchamia pełny uodporniony łańcuch AI ze slotami i DeepSeek
HEADLESS = False        # False: tryb z oknem (omija Cloudflare na formularzu ofert)

# Limity i timeouty
NAV_TIMEOUT_MS = 45000
WAIT_AFTER_PAGE_LOAD_S = 3
MAX_OFFERS_PER_CATEGORY = 40
MIN_WORK_DAYS = 7       # Wymóg biznesowy Useme: minimum 7 dni pracy

# --- BEZPIECZEŃSTWO OPERACYJNE ---
# Brak limitu dziennego (MAX_OFFERS_PER_DAY usuniete).
# Zalozenie biznesowe: KAZDE konto ma wyslac oferte na KAZDE zlecenie.
# 10 zlecen x 2 konta = 20 ofert w jednym runie - to jest cel, nie blad.

# Maksymalny czas jednego uruchomienia (minuty). Po przekroczeniu run sie konczy.
MAX_RUN_MINUTES = 180

# Kill switch: jesli ten plik istnieje, pipeline NIE startuje (ani nie wysyla).
# Tworzysz go recznie, zeby natychmiast zatrzymac bota.
STOP_FILE = BASE_DIR / "STOP"

# Naturalny odstęp między ofertami (3s) chroniący przed burst detection.
MIN_DELAY_BETWEEN_OFFERS_S = 3

# Bezpieczne zakresy opóźnień anty-banowych (sekundy z jitterem) - Golden Ratio (18-26s)
INTER_JOB_DELAY_RANGE = (25.0, 40.0)    # Odstęp między kolejnymi zleceniami (regeneracja puli)
INTER_SLOT_DELAY_RANGE = (18.0, 25.0)   # Odstęp między slotami AI w łańcuchu (1.5 req/min)
RESEARCH_COOLDOWN_RANGE = (20.0, 28.0)  # Odstęp po zakończeniu slotu badawczego z searchem

# Maksymalna dlugosc opisu oferty (znaki). Zabezpieczenie przed wypluciem
# gigantycznego tekstu przez model (i przed kosztownym promptem).
MAX_OPIS_DLUGOSC = 6000

# --- ZBIERACZ DANYCH (weryfikacja odpowiedzi klienta) ---
# UWAGA: selektory DOM w BrowserDriver.sprawdz_skrzynke / sprawdz_powiadomienia
# sa NIEPOTWIERDZONE na realnym DOM Useme (patrz komentarze w browser_driver.py).
# Na czas nieobecnosci (wakacje) trzymamy zbieracz WYLACZONY, zeby nie ryzykowac
# awarii i falszywych statusow. Wlacz na True dopiero po recznej weryfikacji
# selektorow na zywym Useme. Wysylanie ofert dziala niezaleznie od tej flagi.
ZBIERACZ_AKTYWNY = False

# Tryb oferty: tryb meta całkowicie wyłączony, zawsze konserwatywny
DOMYSLNY_TRYB = "konserwatywny"

