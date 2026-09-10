# Struktura projektu Last Z Bot

## Katalog główny

Katalog główny zawiera pliki konfiguracyjne, startowe oraz podkatalogi grupujące różne kategorie zasobów.

### Pliki konfiguracyjne i startowe
- `AGENTS.md` — instrukcje dla agentów AI (ten plik)
- `alembic.ini` — konfiguracja Alembic (migracje bazy danych)
- `config.json` — konfiguracja produkcyjna
- `config.dev.json` — konfiguracja deweloperska
- `debug.toml` — konfiguracja debugowania
- `dev.key` — plik włączający tryb DEV (opcjonalny)
- `dev-debug.bat`, `dev-debug.ps1`, `dev.ps1` — skrypty uruchamiające w trybie deweloperskim
- `pyproject.toml`, `uv.lock` — zarządzanie zależnościami (uv)
- `requirements.txt` — lista zależności (zgodność)
- `run.py` — główny punkt wejścia aplikacji
- `Start_Bot.bat` — skrypt startowy dla użytkowników
- `.env`, `.env.example` — zmienne środowiskowe
- `.gitignore`, `.coverage` — pliki narzędziowe

### Podkatalogi

#### `src/` — Kod źródłowy
Główny kod aplikacji podzielony na moduły:
- `backend/` — serwer licencyjny FastAPI
- `bot/` — silnik bota (capture, clicker, detection, OCR, macro_engine, itp.)
- `gui/` — interfejs użytkownika (DearPyGui)
- `shared/` — współdzielone komponenty (config, constants, coordinates, image_utils)
- `debug/` — narzędzia debugowania (session, recorder, replay)

#### `tests/` — Testy
Testy jednostkowe i integracyjne, z podziałem na:
- `backend/` — testy API
- `bot/` — testy silnika bota
- `gui/` — testy GUI
- `debug/` — testy debugowania
- `fixtures/` — dane testowe (obrazy, makra)
- `manual/` — skrypty testowe ręczne

#### `assets/` — Zasoby
- `macros/` — pliki makr (`.macro.json`, `.macro.blob`)
- `templates/` — szablony obrazów do detekcji
- `screenshots/` — zrzuty ekranu
- `fonts/` — czcionki używane w GUI

#### `docs/` — Dokumentacja
Dokumentacja projektu, w tym:
- `superpowers/` — plany i specyfikacje (Superpowers workflow)
- `GAME_MECHANICS.md` — mechaniki gry
- `PLAN_WDROZENIA.md` — plan wdrożenia
- `SNAPSHOT_PROJEKTU_2026-07-31.md` — stan projektu
- `ANALIZA_HELIKOPTER.md` — analiza mechaniki helikoptera
- `Audyt planów technicznych.md` — audyt
- `INSTRUKCJA_KLIENTA.md` — instrukcja dla użytkownika
- `DEPLOY_BACKEND.md` — instrukcja deployu backendu
- `STRUCTURE.md` — ten plik

#### `scripts/` — Skrypty pomocnicze
Skrypty diagnostyczne, analityczne, narzędziowe i testowe (jednorazowe), w tym:
- Analiza PCAP (`_pcap_*.py`, `analyze_*.py`)
- Diagnostyka (`diag_*.py`, `debug_*.py`)
- Automatyczne testy (`auto_*.py`, `test_*.py`)
- Narzędzia (np. `install_interception.ps1`, `export_metrics.py`)
- Telemetry (`LAST_Z_MASTER_TELEMETRY.py`)

#### `data/` — Dane
Dane testowe i surowe, podzielone na:
- `pcaps/` — pliki .pcapng z przechwyconymi pakietami
- `images/` — obrazy testowe (.jpg, .png)
- `images/analysis/` — obrazy analizy helikoptera (cropy, ROIs, stripe'y — wygenerowane, nie version控制owane)
- `json/` — pliki JSON z danymi (layouty, wyniki)
- `output/` — pliki wyjściowe (.txt, .log)
- `scratch/` — pliki tymczasowe (diffy, logi sesji, tymczasowe wyjścia)

#### `tools/` — Narzędzia zewnętrzne
- `Interception/` — sterownik i biblioteka Interception (z katalogiem `Interception_installer/`)
- `MinHook/` — biblioteka MinHook do hookowania API
- `Interception.zip` — archiwum z instalatorem

#### `raporty/` — Raporty
Raporty z audytów, analiz bezpieczeństwa, dokumentacja architektoniczna.

#### `profiles/` — Profile użytkowników
Profile konfiguracyjne (jeśli stosowane).

## Uwagi

- Wszystkie ścieżki w kodzie powinny być aktualizowane po przeniesieniu plików – jeśli jakiś skrypt lub konfiguracja odwołuje się do starej lokalizacji, należy ją poprawić.
- Plik `helikopter12.pcapng` może być zablokowany przez proces – w razie potrzeby zamknąć aplikacje używające go przed przeniesieniem.
- Katalog `scripts/` nie jest automatycznie dodawany do PYTHONPATH – skrypty należy uruchamiać z odpowiednim kontekstem (np. `python scripts/nazwa.py`).