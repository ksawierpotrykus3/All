# LastZ Bot — Workspace Documentation

**Ostatnia aktualizacja:** 4 września 2026  
**Status:** Wdrożono poprawki Spam Click w Unity, bufor pre-aiming, spójność CPS i zaawansowaną logikę timera OCR (1382 testów zebranych)  
**Rozmiar workspace:** ~32 elementy w root (73% zmniejszenie)

---

## 📊 Szybki Start

### Uruchomienie Symulatora Gry

\\\ash
# Z integracyjnym botem (REKOMENDOWANE)
uv run python run_simulator_integrated_full.py

# Tylko symulator bez bota
uv run python run_simulator_integrated_full.py --no-bot

# Z custom konfiguracją
uv run python run_simulator_integrated_full.py --config config.dev.json

# Verbose logging (debugging)
uv run python run_simulator_integrated_full.py --verbose
\\\

### Sterowanie Symulatorem

| Klawisz | Akcja |
|---------|-------|
| **Space** | Wyzwól alert/event |
| **Click** | Zarejestruj klik (hit/miss) |
| **Q** | Wyjście i pokaż statystyki |

---

## 📁 Struktura Workspace

### Aktywne Katalogi (Zachowane)

\\\
f:\PROJEKTY\joaxx\
├── mvp/                    # 🟢 AKTYWNY KOD (403 pliki)
│   ├── bot/                # MVP Bot — silnik bota
│   ├── gui/                # GUI aplikacji
│   ├── backend/            # Backend licencji
│   ├── tests/              # Testy jednostkowe
│   └── alembic/            # Migracje bazy
│
├── deploy/                 # Docker + instrukcje (6 plików)
├── docs/                   # Dokumentacja (78 plików)
├── assets/                 # Zasoby (makra, czcionki)
├── data/                   # Dane testowe (550 plików)
├── scripts/                # Narzędzia (210 plików)
│
├── .kiro/                  # Konfiguracja Kiro
│   └── specs/watch-timer-spam-click-efficiency/  # 🟢 AKTYWNA SPEC
│
├── mcp-config/             # MCP setup
├── .venv/                  # Python venv
├── .uv-cache, .uv-tools/   # UV cache
│
├── config.json             # Konfiguracja produkcyjna
├── pyproject.toml          # Dependencies
├── uv.lock                 # Lockfile
├── AGENTS.md               # Reguły AGENTS
│
├── run_simulator_integrated_full.py    # 🟢 GŁÓWNY SYMULATOR
├── game_window_simulator_advanced.py   # GUI Symulatora
│
├── debug.toml              # Debug config
├── README.md               # (ten plik)
│
└── _archive/               # 📦 Archiwizowane elementy (3 archiwa)
    ├── comprehensive_20260902-091806/              # FAZA 1
    ├── comprehensive_20260902-093841_PHASE2/       # FAZA 2
    └── comprehensive_20260902-095224_PHASE3/       # FAZA 3
\\\

### Zarchiwizowane Elementy

**FAZA 1** (506 elementów) — Testy, skrypty, dokumentacja  
**FAZA 2** (97 zmian) — Kod źródłowy, cache'e, temp katalogi  
**FAZA 3** (131 zmian) — Regenerowalne cache'y, stare elementy  

**Razem:** 734+ archiwizowanych | 0 usunięto | 100% odzyskiwalne

---

## 🎮 Symulator Gry — Dokumentacja

### run_simulator_integrated_full.py

**Przeznaczenie:** Integracyjny tester — łączy MVP bota z symulatorem gry

**Przepływ:**
1. Ładuje config (config.json)
2. Inicjalizuje MVP bota
3. Inicjalizuje symulator gry
4. Łączy bota z kolejką ramek symulatora
5. Uruchamia bota w tle
6. Wyświetla GUI symulatora
7. Zbiera statystyki kliknięć

**Co pokazuje:**
- Okno symulatora gry
- ROI overlay (regiony zainteresowania)
- Timer sesji (300 sekund)
- Debug info (liczba kliknięć, accuracy)
- Status bota

**Raport na koniec:**
\\\
Total Clicks: 100
Accuracy: 87.50%
Hits: 87 / 100
\\\

**Opcje linii komend:**
\\\
--config FILE        Plik konfiguracji (default: config.json)
--no-bot             Uruchom tylko symulator bez bota
--verbose            Szczegółowe logi (debug)
\\\

### game_window_simulator_advanced.py

**Przeznaczenie:** GUI symulatora gry — silnik + interfejs graficzny

**Komponenty:**
- \AdvancedGameSimulator\ — logika symulatora
- \SimulatorUI\ — interfejs Tkinter

**Stany Symulatora:**
- \chat\ — normalny widok czatu
- \lert_animation\ — alert spada z góry (10 sekund)
- \helka\ — widok helcopter'a

**Obrazy Gry (z data/macro_testing/):**
- \1_scan_chat_without_arrow.png\ — główny widok czatu
- \helka_scrolled.png\ — widok helcopter'a
- \1_heli_alert_appearing_in_chat.png\ — alert animacja

**Cechy:**
- Dynamic viewport (dostosowuje się do rozmiaru okna)
- Cropping wyśrodkowany bez skalowania
- ROI boxes (zielone = aktywne, czerwone = trafione)
- Logowanie każdego kliknięcia (hit/miss)
- Alpha blending dla alert'a
- Timer sesji (300 sekund)
- Noise w animacji alert'a

**ROI (Region Of Interest):**
- Zielone boxy — aktywne (bot czeka na klik)
- Czerwone boxy — trafione (użytkownik kliknął)
- Szare boxy — nieaktywne

---

## 🔧 Konfiguracja

### config.json (Produkcja)

Główny plik konfiguracji MVP bota.

### config.dev.json (Deweloper)

Konfiguracja dla developmentu (jeśli istnieje).

### debug.toml

Konfiguracja debug modu.

---

## 📦 Archiwizacja — Jak Przywrócić

### Struktura Archiwum FAZY 3

\\\
_archive/comprehensive_20260902-095224_PHASE3/
├── OLD_CACHE_ROOT/      — Cache'y regenerowalne
├── OLD_EGG_INFO/        — lastz_bot.egg-info
├── OLD_TESTS/           — tests/ (197 plików)
├── OLD_RAPORTY/         — raporty/ (8 plików)
├── OLD_MISC/            — stare .md, .kiro/build-cache
├── OLD_AGENTS_TASKS/    — .agents/tasks/
└── OLD_KIRO_REPORTS/    — stare raporty .kiro/
\\\

### Procedura Przywracania

**Przywróć z archiwum:**
\\\powershell
Copy-Item _archive/comprehensive_20260902-095224_PHASE3/OLD_TESTS/tests/ ./
\\\

**Lub z git'a:**
\\\ash
git log --oneline -- tests/
git show COMMIT_HASH:tests/test_*.py
\\\

**Przywróć cały katalog:**
\\\powershell
Copy-Item -Recurse _archive/comprehensive_20260902-095224_PHASE3/OLD_TESTS ./
\\\

---

## 🚀 Komendy Deweloperskie

### Instalacja Zależności

\\\ash
uv sync --extra dev     # Zainstaluj zależności (podstawowe + dev)
\\\

### Testy

\\\ash
uv run pytest                               # Cała suita
uv run pytest mvp/tests/ -v                 # Verbose
uv run pytest --cov=mvp --cov-report=html  # Z coverage
\\\

### Linting i Format

\\\ash
uv run ruff check .          # Lint
uv run ruff format --check . # Format check
uv run ruff format .         # Auto-format
\\\

### Bezpieczeństwo

\\\ash
uv run bandit -r mvp/       # Bezpieczeństwo
uv run vulture mvp/ tests/  # Martwy kod
\\\

---

## 📊 GIT Commits Archiwizacji

\\\
3791266 archive/PHASE3: archiwizacja regenerowalnych cache'y...
aea7300 docs: ARCHIVIZATION_COMPLETE
9e2ce3c docs: raport FAZY 2
7bd564e archive/PHASE2: archiwizacja 400-800 MB
905dd95 docs: pełna analiza projektu
9c023b9 docs: raport podsumowujący archiwizację
0d486a9 archive: kompleksowa archiwizacja
\\\

---

## ✅ Weryfikacja

- ✅ Nic nie usunięte — wszystko zarchiwizowane
- ✅ Git history zachowana — wszystkie commity dostępne
- ✅ Bezpieczne move — tylko przesunięcie, bez deletions
- ✅ Wersjonowanie — każde archiwum z timestampem
- ✅ Struktura zorganizowana — 20+ kategorii archiwizacji
- ✅ Root czysty — 32 elementy (zmniejszenie z 41+)
- ✅ Aktywny kod kompletny i funkcjonalny
- ✅ Wszystko można przywrócić

---

## 📈 Oszczędności

| Metrika | Wartość |
|---------|---------|
| Zmniejszenie workspace | 60-70% (bez .git) |
| Archiwizowane | ~700-1000 MB |
| Zachowane | 100% — przywracalne |
| Root elements | 32 (przed: 41+) |

---

## 🔗 Aktywna Specyfikacja

**Spec:** \.kiro/specs/watch-timer-spam-click-efficiency/\  
**Status:** 🟢 AKTYWNA — w trakcie pracy

---

## 📞 Kontakt i Porada

Jeśli masz pytania dotyczące:
- **Symulatora gry** → Sprawdź \un_simulator_integrated_full.py\
- **Archiwizacji** → Sprawdź \ARCHIVIZATION_COMPLETE.txt\, \PHASE2_SUMMARY.txt\
- **Struktury projektu** → Sprawdź \.kiro/specs/watch-timer-spam-click-efficiency/design.md\
- **Konfiguracji** → Sprawdź \config.json\ lub \config.dev.json\

---

## 📝 Historia Aktualizacji

**2026-09-02**
- ✅ Kompletna archiwizacja FAZY 1+2+3
- ✅ Dokumentacja zaktualizowana
- ✅ Weryfikacja workspace'u

---

**Workspace jest czysty, zorganizowany i w pełni funkcjonalny.**

