# -*- coding: utf-8 -*-
"""Konfiguracja główna silnika freelancer_core."""

from pathlib import Path

BASE_DIR = Path(__file__).parent
MAGAZYN_DIR = BASE_DIR / "magazyn"
MARKER_FILE = BASE_DIR / "marker.json"
COOKIES_PATH = BASE_DIR / "tech" / "cookies.json"
DEBUG_DIR = BASE_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# --- API Freelancera (dziala przez ctx.request z cookies - NIE trzeba scrapowac HTML) ---
API_BASE = "https://www.freelancer.pl/api/projects/0.1"
API_LOCALE = "pl"

# Zasob kategorii: mapowanie czytelnej nazwy -> lista job_id (z /api/projects/0.1/jobs/)
# Uzywamy filtru jobs[]=  w /projects/active/
CATEGORY_JOBS = {
    "programowanie-i-it": [
        3, 9, 13, 68, 500, 613, 1092, 1093, 1239, 1240, 2703, 116, 167, 2299,
    ],
    "web-dev": [
        1031, 2839, 2701, 1827, 335, 323, 1042, 77, 2435, 1595, 1093, 1092,
    ],
    "automation-ai": [
        1977, 913, 2068, 2916, 2917, 2918, 3380, 3381, 3508, 3470, 292, 2607,
        2719, 2946, 2966, 3101, 3300,
    ],
    "sklepy-shopify": [502, 1686, 3535, 371, 69, 2723],
    "scraping-dane": [95, 1040, 1051, 1075, 36, 334, 199],
}

# Limit ofert pobieranych na kategorie z listy
MAX_OFFERS_PER_CATEGORY = 15

# --- Twarde flagi bezpieczeństwa ---
DRY_RUN = True          # True: przygotowuje oferte, NIE wysyla (bezpiecznik)
USE_MOCK_AI = False     # True: deterministyczny mock (test szkieletu bez sieci)
HEADLESS = False        # Widoczna przeglądarka (Cloudflare/QS nie blokuje tak jak headless)

# --- Limity i timeouty ---
NAV_TIMEOUT_MS = 60000
WAIT_AFTER_PAGE_LOAD_S = 3
MIN_WORK_DAYS = 7

# --- Wymogi konta (wykryte reconem) ---
# Bidding jest TWARDZIE zablokowane przy saldzie UJEMNYM (przycisk sie nie renderuje).
# Przy dodatnim saldzie < 20 USD formularz dziala, ale platforma ostrzega o progu 20 USD
# (ryzyko odrzucenia submit). Dlatego rozdzielamy:
#   - CAN_BID_MIN_USD: minimalne saldo by przycisk byl dostepny (0 = dodatnie)
#   - RECOMMENDED_BALANCE_USD: zalecany prog platformy (ostrzezenie)
CAN_BID_MIN_USD = 0.0
RECOMMENDED_BALANCE_USD = 20.0

# Filtr: pomijaj projekty lokalne (local=True) - nie mozemy ich wykonac zdalnie
SKIP_LOCAL_PROJECTS = True