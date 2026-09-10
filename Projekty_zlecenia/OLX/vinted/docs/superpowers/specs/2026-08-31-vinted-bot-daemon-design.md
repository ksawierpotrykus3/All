# Vinted Bot — Daemon auto-zakupu z podtrzymywaniem sesji

> Data: 2026-08-31 · Status: spec do zatwierdzenia

## 1. Cel

Dodać do `bot/` długo żyjący proces (daemon), który:
1. **podtrzymuje sesję** tak, by bot był „zawsze gotowy" do zakupu (Camoufox, trwały profil),
2. **monitoruje katalog** po filtrach i **automatycznie rezerwuje** pasujące oferty (czysty curl_cffi),
3. **zna i raportuje swój stan** (gotowość sesji, licznik rezerwacji, błędy).

Płatność wykonywana **tylko przy fladze `--payment`**; domyślnie zatrzymuje się na rezerwacji.

## 2. Kluczowe fakty (udowodnione w tym projekcie)

1. **Monitoring i zakup = 100% curl_cffi** (`impersonate="firefox135"`), już zaimplementowane
   w `detection.py` (`monitoruj`, `pobierz_oferty`) i `checkout.py` (`zrealizuj_zakup`).
2. **Podtrzymywanie sesji = Camoufox** (frontend Vinted sam odświeża `refresh_token_web` przy
   załadowaniu strony na trwałym profilu `profil_firefox_135`). Wzorzec działa:
   `testy_camoufox/tools/export_cookies_json.py` (headless → „Zalogowano: maksks0, 97 cookies").
3. **`odswiez_token()` (curl_cffi)** działa tylko dopóki `refresh_token_web` ważny; przy pełnym
   wygaśnięciu zwraca 401. Dno sesji = **ręczne logowanie człowieka** (udokumentowane: sekcja
   10.5b „pierwsze logowanie = człowiek").
4. Sesja zwalidowana przez `GET /api/v2/users/current` (200 + `user.login` = zalogowana).

## 3. Architektura — jeden proces, dwie pętle + maszyna stanów

                     ┌───────────────────────────────────────────┐
                     │             Daemon (jeden proces)          │
profil_firefox_135 ──► [Pętla refresh: Camoufox]                 │
                     │   co N min: ładuje stronę (frontend        │
                     │   odświeża token) → eksport cookies        │
                     │                                            │
                     │  [Pętla zakup: curl_cffi]                  │
                     │   monitoruje katalog (firefox135),         │
                     │   dopasowanie → rezerwacja (+payment)      │
                     └──────────────┬─────────────────────────────┘
                                    │ cookies + stan (pamięć/wątek)
                                    ▼
                          Maszyna stanów sesji
Obie pętle w osobnych wątkach (`threading`). Stan sesji i cookies współdzielone przez
słownik chroniony lockiem.

## 4. Maszyna stanów sesji

| Stan | Znaczenie | Wejście |
|---|---|---|
| `UNKNOWN` | nie sprawdzono jeszcze | start |
| `READY` | sesja zalogowana, gotowa do zakupu | `/users/current` = 200 + login |
| `REFRESHING` | trwa odświeżanie (Camoufox) | cykl refresh / 401 podczas zakupu |
| `NEEDS_LOGIN` | pełne wygaśnięcie, wymaga człowieka | Camoufox nie potrafi odświeżyć |

Przejścia:
- `UNKNOWN`/`READY` → `REFRESHING` co N minut (profilaktycznie przed wygaśnięciem).
- `REFRESHING` → `READY` gdy świeże cookies dadzą `/users/current` 200.
- `REFRESHING` → `NEEDS_LOGIN` gdy Camoufox też nie zaloguje (sesja martwa).
- `NEEDS_LOGIN` → `READY` tylko po ręcznym logowaniu.

Zakup dozwolony wyłącznie w stanie `READY`.

## 5. Pętla zakupowa (gating)

- Wykonuje iterację monitoringu tylko gdy stan `READY`.
- `monitoruj` (istniejące) wykrywa nowe oferty → `callback` → `zrealizuj_zakup(item_id, seller_id, konto, proba_payment=flaga)`.
- Kupuje **każdą** nową ofertę pasującą do filtrów (decyzja właściciela).
- Po 401 w trakcie zakupu → stan `REFRESHING`, czeka na pętlę refresh.
- Licznik rezerwacji i błędy zapisywane w stanie (raportowane).

## 6. Komponenty (nowe pliki w `bot/src/vintedbot/`)

session_state.py   # NOWY: SessionState — stany + walidacja /users/current (curl_cffi)
refresh.py         # NOWY: pętla Camoufox — ładuje stronę, eksport cookies → stan
daemon.py          # NOWY: spina pętle (wątki, signal, graceful shutdown)
cli.py             # ZMIANA: dodać komendę `daemon`
Istniejące `detection.py`, `checkout.py`, `models.py`, `config.py`, `incognia.py` — bez zmian.

### 6.1 `session_state.py`

```python
from enum import Enum

class SessionStatus(Enum):
    UNKNOWN = "unknown"
    READY = "ready"
    REFRESHING = "refreshing"
    NEEDS_LOGIN = "needs_login"

class SessionState:
    def __init__(self):
        self._lock = threading.Lock()
        self.status = SessionStatus.UNKNOWN
        self.cookies = {}
        self.login = None
        self.last_refresh_ts = 0.0
        self.reservations = 0
        self.errors = []

    # metody: set_status, get_snapshot, record_reservation, record_error
Walidacja `is_ready()`: `GET /users/current` z cookies → 200 + `user.login`.

### 6.2 `refresh.py`

Pętla Camoufox (headless, `profil_firefox_135`):
1. ładuje `https://www.vinted.pl/` (domcontentloaded),
2. czeka na `GET /users/current` 200 (frontend auto-refresh tokenu),
3. eksportuje cookies (`ctx.cookies()`) do `SessionState.cookies` + ustawia `READY`,
4. jeśli nie zaloguje w TIMEOUT → ustawia `NEEDS_LOGIN`.

Wzorzec 1:1 z `testy_camoufox/tools/export_cookies_json.py`.

### 6.3 `daemon.py`

- startuje wątek refresh (interwał N min, domyślnie 4),
- startuje wątek zakupowy (pętla `monitoruj` gated stanem `READY`),
- przechwytuje `SIGINT`/`SIGTERM` → graceful shutdown,
- loguje przejścia stanów i licznik rezerwacji.

### 6.4 `cli.py` — komenda `daemon`

```python
@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--cookies", required=True, type=click.Path(exists=True))
@click.option("--profil", required=True, type=click.Path(exists=False))  # profil Camoufox
@click.option("--interval", default=4, type=int, help="Interwał refresh (min)")
@click.option("--payment", is_flag=True, help="Próbuj dojść do kroku payment po rezerwacji")
def daemon(brand, search, cookies, profil, interval, payment): ...
## 7. Obsługa błędów i lifecycle

- Daemon toleruje chwilowe błędy HTTP (backoff), nie kończy procesu.
- `NEEDS_LOGIN` → pętla zakupowa zatrzymuje się (nie rezerwuje), loguje alert, czeka.
- Każde przejście stanu logowane ze znacznikiem czasu.

## 8. Testowanie

Mockować wyłącznie HTTP (`creq.get/post/put`) i subprocess/Camoufox; nigdy wewnętrzne klasy.

- `test_session_state.py` — przejścia stanów, walidacja `users/current` (mock HTTP).
- `test_refresh.py` — pętla Camoufox ustawia `READY`/`NEEDS_LOGIN` (mock Camoufox).
- `test_daemon.py` — gating: zakup nie startuje gdy `!= READY`; graceful shutdown sygnałem.
- `test_cli_e2e.py` — komenda `daemon` rejestruje się i parsuje flagi (CliRunner).

## 8a. Zależność `camoufox` (korekta względem poprzedniej przebudowy)

Poprzednia przebudowa usunęła `camoufox` z `pyproject.toml`, bo **ścieżka zakupowa** jest
teraz w 100% na curl_cffi. Ten daemon **przywraca `camoufox` jako zależność**, ale wyłącznie
dla pętli refresh (podtrzymywanie sesji przez frontend). Podział pozostaje czysty:
- **monitoring + zakup** = curl_cffi (bez przeglądarki),
- **podtrzymywanie sesji** = Camoufox (frontend-driven token refresh).

`pyproject.toml` musi ponownie zawierać `camoufox>=0.4`.

## 9. Zakres wykluczony

- Multikonto/proxy (1 konto).
- Filtr kategorii SSR.
- Rejestracja Adyen/3DS (payment tylko do `POST payment`).
- Humanizacja opóźnień.
- Pełne samoodświeżanie bez człowieka przy całkowitym wygaśnięciu (fizycznie niemożliwe —
  pierwsze logowanie wymaga ręki).

## 10. Definicja sukcesu

- `daemon` trzyma stan `READY` przez cały czas działania (dopóki sesja nie wygaśnie całkowicie).
- Monitoruje i rezerwuje pasujące oferty automatycznie (curl_cffi).
- Przy 401 przechodzi w `REFRESHING` i sam odzyskuje `READY` bez restartu.
- `SIGINT`/`SIGTERM` kończy proces czysto.
- Testy przechodzą bez mockowania wewnętrznych klas.