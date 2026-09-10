"""Konfiguracja bota OLX."""
import os

# --- HTTP ---
IMP = "chrome124"  # impersonation TLS (obejście CloudFront 403)
API = "https://www.olx.pl/api/v1/offers/"

# --- Specjalne kody błędów (kontrakt (code, data) w http_client) ---
ERR_NET = -1        # błąd sieci / wyjątek
ERR_BANNED = -2     # 403 — blokada IP / CloudFront
ERR_RATELIMIT = -3  # 429 — rate limit

# --- Kategorie (twarde, zweryfikowane) ---
IPHONE_CAT_ID = 2298
MACBOOK_CAT_ID = 3102
OTOMOTO_PARTNER = "otomoto_pl_form"

# --- Filtry auta ---
MAX_PRICE_AUTO = 12000
REGION_AUTO = "mazowieck"  # dopasowanie case-insensitive

# --- Detektor ---
BATCH_SIZE = 20
CONCURRENCY = 20
WAIT_NO_NEW = 0.5          # s, czekanie gdy samo 404 (krawedz)
WAIT_NET_ERR = 1.0         # s, czekanie po bledzie sieci
RETRY_COUNT = 2            # ponowienia przy bledzie sieci
RETRY_BACKOFF_BASE = 0.4   # s
TIMEOUT = 10               # s, timeout requestu

# --- Seed (get_max_id) ---
SEED_RETRY_COUNT = 5       # ile prób seedu zanim poddamy
SEED_RETRY_BACKOFF = 2.0   # s, mnożnik backoffu
SEED_RETRY_LONG = 60.0     # s, przerwa przed drugą turą seedu

# --- Bufor wsteczny (Zero-Miss Sweeper) ---
HOLE_RETRY_DELAYS = (3.0, 10.0, 25.0, 50.0)  # harmonogram ponowień dla 404
HOLE_MAX_AGE = 65          # s, po ilu sekundach porzucić pusty ID
HOLE_CONCURRENCY = 15      # równoległość zamiatania dziur
HOLE_BATCH_SIZE = 15       # rozmiar partii sweepu dziur
MAX_PENDING_HOLES = 5000   # twardy sufit kolejki dziur


# --- Komparator ---
COMPARE_INTERVAL = 20      # s, rzadsze odpytywanie wyszukiwarki
COMPARE_OFFSETS = (0, 50, 100)  # 3 strony wynikow
COMPARE_TTL = 900          # s, jak dlugo czekac na wejscie oferty do wyszukiwarki

# --- Powiadomienia Telegram ---
TELEGRAM_TOKEN = os.environ.get("OLX_TG_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("OLX_TG_CHAT", "")

# --- Persystencja ---
HITS_FILE = "logs/hits.json"
HITS_SAVE_INTERVAL = 30    # s, jak często zrzucać trafienia na dysk

# --- Watchdog ---
WATCHDOG_THRESHOLD = 120   # s, alarm gdy brak 200 przez ten czas

# --- Logi ---
LOG_DIR = "logs"
DETECT_LOG = "logs/detect.log"
COMPARE_LOG = "logs/compare.log"
APP_LOG = "logs/app.log"
ERROR_LOG = "logs/errors.log"

# Maksymalny rozmiar pliku logu przed rotacja (bajty)
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3