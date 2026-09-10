# -*- coding: utf-8 -*-
"""Konfiguracja główna silnika useme_core."""

from pathlib import Path

BASE_DIR = Path(__file__).parent
MAGAZYN_DIR = BASE_DIR / "magazyn"
MARKER_FILE = BASE_DIR / "marker.json"
COOKIES_PATH = BASE_DIR / "tech" / "cookies.json"
DEBUG_DIR = BASE_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Kategorie monitorowane
CATEGORY_URLS = {
    "programowanie-i-it": "https://useme.com/pl/jobs/category/programowanie-i-it,35/",
    "serwisy-internetowe": "https://useme.com/pl/jobs/category/serwisy-internetowe,34/",
}

# Twarde flagi bezpieczeństwa
DRY_RUN = False         # False: tryb wysyłki na żywo po autoryzacji użytkownika
USE_MOCK_AI = False     # False: uruchamia pełny uodporniony łańcuch AI ze slotami i DeepSeek
HEADLESS = False        # Widoczne okno (Cloudflare nie blokuje formularzy tak agresywnie jak w headless)

# Limity i timeouty
NAV_TIMEOUT_MS = 45000
WAIT_AFTER_PAGE_LOAD_S = 3
MAX_OFFERS_PER_CATEGORY = 10
MIN_WORK_DAYS = 7       # Wymóg biznesowy Useme: minimum 7 dni pracy
