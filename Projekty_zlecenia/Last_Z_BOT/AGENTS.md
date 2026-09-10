# AGENTS.md — lastz-bot

## ℹ️ WAŻNE — Archiwizacja FAZY 1+2+3 KOMPLETNA (2 września 2026)

Workspace czyszczony i archiwizowany - **734+ elementów**, **0 usunięto**, **100% przywracalne**.
- Root zmniejszony: 41+ → 32 elementy (73%)
- Archiwizowane: ~700-1000 MB

Czytaj: README.md, QUICKSTART.md, ARCHIVIZATION_REPORT.txt

---
# AGENTS.md — lastz-bot

## Zarządzanie środowiskiem (uv)

Projekt używa [uv](https://docs.astral.sh/uv/) — lockfile `uv.lock` + venv `.venv`.

```sh
uv sync --extra dev     # zainstaluj zależności (podstawowe + dev)
uv run pytest           # uruchom testy
uv run python main.py   # uruchom aplikację
uv add <pakiet>         # dodaj zależność do pyproject.toml + uv.lock
uv add --dev <pakiet>   # dodaj zależność dev (optional-dependencies "dev")
```

- **Nie używaj `pip install` do dodawania zależności** — rób to przez `uv add`, żeby `uv.lock` pozostał spójny.
- `uv sync --extra dev` po zmianach w `pyproject.toml`.
- Wymagany Python 3.11.
## 🎮 SYMULATOR GRY — SZYBKI START

### Uruchomienie

```bash
uv run python run_simulator.py --variant default        # domyślny scenariusz
uv run python run_simulator.py --variant hard_mode      # trudny scenariusz
uv run python run_simulator.py --variant stress_test    # test obciążeniowy
```

### Sterowanie
- **Space** = Wyzwól alert
- **Click** = Rejestruj klik
- **Q** = Wyjście

### Pliki
- run_simulator.py — jedyny entry point
- mvp/simulator/game.py — GUI gry (GameSimulator + SimulatorUI)
- mvp/simulator/sim_metrics.py — kolektor metryk (celność, latency, detekcja, niezawodność)
- mvp/simulator/bot_bridge.py — most symulator↔bot (step_callback + klatki)
- mvp/simulator/variants.py — warianty testowe (default/hard_mode/stress_test)

Czytaj sekcję "Symulator Gry" w README.md


## Dev-deps

Dostępne przez `uv run`: `ruff`, `pytest`, `pytest-cov`, `pytest-timeout`, `bandit`, `vulture`, `scalene`, `debugpy`.
Wywołuj przez `uv run <tool>`, nie bezpośrednio — skrypty nie są w PATH.

## Testy

```sh
uv run pytest                          # cała suita
uv run pytest -m "not slow"            # bez wolnych
uv run pytest --cov=src --cov-report=term-missing
```

Maksymalny czas wykonania suity: ~15s (1382 testów). Równoległość (`pytest-xdist`) nie jest używana — testy piszą do wspólnych plików (`assets/macros`) i mockują `dearpygui` na poziomie modułu.

## Lint i typowanie

```sh
uv run ruff check .                    # lint (konfiguracja w pyproject.toml)
uv run ruff format --check .           # format
uv run bandit -r src                   # bezpieczeństwo
uv run vulture src tests               # martwy kod
uv run scalene <skrypt>                # profilowanie CPU
```

Konfiguracja ruff/mypy/pytest w `pyproject.toml`. `[tool.mypy]` strict = true (mypy nie jest dev-depem — typowanie sprawdzane opcjonalnie).

## Zależności

- Podstawowe: `[project].dependencies` w `pyproject.toml`
- Deweloperskie: `[project.optional-dependencies].dev`

`email-validator` jest wymagany przez `EmailStr` w `mvp/backend/schemas.py` — nie usuwać.

## Struktura projektu

Katalog główny został uporządkowany według następujących kategorii:

- `mvp/` — aktualna wersja MVP: silnik bota (`bot/`), GUI (`gui/`), backend licencyjny (`backend/`), migracje (`alembic/`), testy (`tests/`)
- `tests/` — testy jednostkowe i integracyjne
- `assets/` — zasoby (makra, szablony, czcionki, screenshoty)
- `docs/` — dokumentacja projektu (plany, specyfikacje, instrukcje)
- `scripts/` — skrypty pomocnicze, diagnostyczne, analityczne i narzędziowe
- `data/` — dane testowe i surowe (pcapy, obrazy, pliki JSON, logi)
- `archive/` — zarchiwizowany, nieużywany kod i raporty; nie importować, nie uruchamiać:
  - `archive/legacy-simulator/` — stary silnik headless symulatora (`mvp/simulator`) i jego testy
  - `archive/legacy-reports/` — historyczne raporty faz i artefakty testów

Pliki konfiguracyjne (`config.json`, `debug.toml`) oraz entry point symulatora (`run_simulator.py`) pozostają w katalogu głównym. `alembic.ini` znajduje się w `mvp/`.

Szczegółowy opis struktury znajduje się w [docs/STRUCTURE.md](file:///f:/PROJEKTY/joaxx/docs/STRUCTURE.md).

---

## ⚠️ ŚCIŚLE ARCHITEKTONICZNE ZASADY I OGRANICZENIA SILNIKA GRY (NIE ZMIENIAĆ!)

Poniższe ograniczenia wynikają z **bezpośredniej inżynierii wstecznej silnika gry (`GameAssembly.dll`, `global-metadata.dat`, Unity 60 FPS)**. **ŻADEN AGENT NIE MOŻE ICH ZMIENIAĆ W CELU „PRZYSPIESZENIA” BOTA**, ponieważ spowoduje to natychmiastowe odrzucenie kliknięć przez grę lub ucieczkę kamery!

### 1. Limit Prędkości w Czystej Grze: Max 38.46 CPS ($T_{\text{period}} \ge 26.0\text{ ms}$)
* **Powód w kodzie gry:** Klasa `ClickIntervalMonitor` posiada wewnętrzny próg **$\text{\_threshold} = 25.0\text{ ms}$**.
* **Dlaczego nie 60 CPS w czystej grze:** Wysłanie 60 CPS ($16.6\text{ ms}$) powoduje, że $16.6\text{ ms} < 25.0\text{ ms}$. Gra natychmiast wywołuje **`ReportFastClick()`** i blokuje wysyłanie pakietów `get.treasure.info` dla 59 na 60 kliknięć!
* **Dopuszczalne wartości:** **$38.46\text{ CPS}$** ($T = 26.0\text{ ms}$) lub **$30.0\text{ CPS}$** ($T = 33.3\text{ ms}$). Tryb 60+ CPS jest dozwolony WYŁĄCZNIE na spatchowanym kliencie 200 Hz z iniekcją DLL.

### 2. Ruch Kursora Gaussa Wyłącznie w Środku Przerwy `UP` ($40\% / 60\%$ Split)
* **Powód w kodzie gry:** `BitBenderGames.MobileTouchCamera` posiada próg aktywacji przeciągania terenu **$\approx 1.5\text{ px}$**.
* **Zasada bezwzględna:**
  1. `DOWN` i `UP` muszą odbywać się na **dokładnie tych samych współrzędnych ($\Delta r = 0$)**. W trakcie wciśnięcia ruch myszy jest ZAKAZANY (anuluje flagę `eligibleForClick = false` w Unity!).
  2. Ruch do nowej pozycji Gaussa musi następować ze statusem **`state = 0` (przycisk w 100% zwolniony)** w środku przerwy:
     ```python
     time.sleep(delay * 0.4)  # Bufor ciszy po UP (min. 6-8 ms)
     _g_context.send(mouse_dev, MouseStroke(flags, 0, 0, nx, ny)) # Ruch state=0
     time.sleep(delay * 0.6)  # Bufor stabilizacji przed kolejnym DOWN (min. 10-12 ms)
     ```
  3. **ZAKAZ:** Nigdy nie wysyłaj `MOVE` na samym końcu przerwy (tuż przed `DOWN`), ponieważ Windows scala pakiety (`coalescing`), co Unity widzi jako ruch w trakcie wciśnięcia i odpala przeciąganie kamery.

### 3. Czasy Trzymania `DOWN` (`DIG_HOLD_MS`)
* **Tryb 60 FPS (czysta gra):** **`18.0 ms` stale (BEZ jittera)** — standard per `docs/full_event_analysis_knowledge5.md §5`. Gra nie rejestruje kliknięć krótszych niż ~16 ms; przy 38 CPS (okres 26.3 ms) zostaje ~8.3 ms przerwy UP. **Uniformity w trybie 60 FPS pochodzi z jittera cyklu (`click_jitter_ms`), NIE z hold-u.**
* **Tryb 200 FPS (spatchowany):** `3.0 ms ± 0.3 ms` trzymania `DOWN` (jitter abyClickIntervalMonitor nie flagował stałej 3.0 ms).

### 4. Wyzwalanie Spamu — Wyłącznie OCR + Estymata Monotoniczna $T_0$ (Wyzwalacz Sieciowy USUNIĘTY)
* **STAN AKTUALNY (Wrzesień 2026):** Ścieżka wyzwalacza sieciowego $T_0$ została **celowo usunięta**. Moduł `mvp/bot/packet_filter.py` (wykrywanie sygnatury Protobuf `\x58\x01` w pakietach `push.world.point.update`) już nie istnieje, a parametr `network_t0_triggered` został usunięty z funkcji `should_trigger_spam()` w `mvp/bot/macro_engine.py`. Spam jest teraz wyzwalany **wyłącznie** przez odczyt timera OCR oraz estymatę monotoniczną $T_0$.
* **Mechanizm wyzwalania spamu (`should_trigger_spam`) — dwie ścieżki:**
  1. **Estymata monotoniczna $T_0$ (priorytet 1):** Gdy `estimated_t0_mono` jest ustawione i `time.monotonic() >= estimated_t0_mono - t0_lead_time_s`, spam wyzwala się proaktywnie przed dokładnym $T_0$.
  2. **OCR + histereza (fallback):** Gdy odczyt timera `ocr_timer_value <= spam_threshold` oraz `confirmed_count >= hysteresis_confirmations`.
* **Usunięte koncepcje (były częścią `packet_filter.py`, nie są już implementowane):**
  * Rozróżnienie **marszy i dojazdu armii (`push.world.march.new`)** od **fizycznego spawnu skrzynki (`push.world.point.update`)** — dawniej służyło do odfiltrowania pakietów ruchu wojska od prawdziwego zrzutu; żaden kod nie dokonuje już tej analizy.
  * Wykrywanie pola Protobuf **`tag 0x58 = 1`** (bajty `\x58\x01`, `canOpen = true` / `isDrop = true`) jako autonomicznego, bezwzględnego wyzwalacza niezależnego od stanu OCR.

### 5. Zarządzanie Fokusem i Geometrią Okna Gry (WinAPI)
* **ZASADA BEZWZGLĘDNA:**
  * Do aktywacji okna gry przed klikaniem wolno używać wyłącznie:
    ```python
    if user32.IsIconic(info.hwnd):
        user32.ShowWindow(info.hwnd, 9)  # SW_RESTORE TYLKO gdy okno jest zminimalizowane!
    else:
        user32.ShowWindow(info.hwnd, 5)  # SW_SHOW (nie modyfikuje rozmiaru ani pozycji)
    user32.SetForegroundWindow(info.hwnd)
    ```
  * **ZAKAZ:** Nigdy nie wywołuj `ShowWindow(info.hwnd, 9)` (`SW_RESTORE`) na oknie, które nie jest zminimalizowane (`not IsIconic`), ponieważ w systemie Windows resetuje to geometrię okna i un-maksymalizuje je w trybie okienkowym!

### 6. Architektura Fast OCR i Całkowita Eliminacja EasyOCR/Tesseract (Wrzesień 2026)
* **Całkowita eliminacja ciężkich zależności:**
  * Z projektu bezpowrotnie usunięto biblioteki `torch`, `torchvision`, `easyocr`, `pytesseract` (oszczędność ~2.5 GB na dysku i eliminacja 20-sekundowego blokowania startu bota).
  * Wyczyszczono instalatory `tesseract-setup.exe` i wagi `.pth`/`.zip` (`craft_mlt_25k`, `english_g2`) z katalogów `vendor/`.
  * Zlikwidowano zmienne środowiskowe `EASYOCR_MODULE_PATH` oraz `TESSERACT_CMD` ze skryptów instalatora (`installer.iss`, `installer-dev.iss`, `launch-app.ps1`, `health-check.ps1`).
* **Nowy potok Fast OCR (`mvp/bot/ocr.py`):**
  1. **WinOCR (`Windows.Media.Ocr` przez WinRT):** Wykorzystywany do weryfikacji zakładek czatu i szybkiego skanowania. Osiąga latencję **13–17 ms** (~100x szybciej niż EasyOCR).
  3. **⚠️ Ograniczenie Wątków ONNX Runtime (`intra_op_num_threads=2, inter_op_num_threads=1`):** Domyślnie ONNX Runtime alokuje threadpool równy liczbie wszystkich rdzeni logicznych procesora (-1). Zawsze należy jawnie ograniczać liczbę wątków do 2, zapobiegając blokowaniu rdzeni CPU.
  4. **Architektura Dual-Gate w Detekcji Alertu Helikoptera (`find_helicopter_alert`):**
     * **Problem:** W polskim systemie Windows (`lang='pl'`) stylizowany, kolorowy tekst karty helikoptera w grze (zielony tekst z czarną obwódką na pomarańczowym tle) ulega zniekształceniu przez WinOCR (`xp ore reasure`, `Stałe 7,42 Y,ŕă82`), co gubi literę `X` i uniemożliwia odczytanie koordynatów bezpośrednio z WinOCR.
     * **Rozwiązanie (Dual-Gate):**
       - **Gate 1 (Precyzyjne słowa kluczowe WinOCR):** Sprawdzenie obecności poszlak tekstowych (`Expl`, `xp ore`, `Treas`, `reasure`, `spot`, `troop`, `heli`). Z poszlak bezwzględnie wykluczono ogólne słowo `State`/`Stałe`, ponieważ występuje ono w każdej karcie misji czatu (`Bounty Missions`, `Truck`) oraz w wypowiedziach graczy.
       - **Szybkie Wyjście (Fast Exit):** Jeśli WinOCR odczyta czat i w żadnej linii nie ma poszlak skrzynki/helikoptera, funkcja natychmiast zwraca `None` w **~75 ms** (bez uruchamiania ciężkiego RapidOCR).
       - **Zawężone ROI RapidOCR:** W razie wykrycia poszlaki tekstowej w WinOCR, RapidOCR jest uruchamiany wyłącznie na wąskim wycinku wokół poszlaki ($\pm 140\text{ px}$), redukując czas inferencji ONNX o ponad 50%.
       - **Gate 2 (Pomarańczowy Filtr Koloru HSV w OpenCV < 1 ms):** Karta helikoptera to duży pomarańczowy banner ($\ge 10\,000\text{ px}$ w `cv2.inRange`). Wykorzystywany jako zabezpieczenie wyłącznie w przypadku awarii lub braku natywnego WinOCR.
       - **Zasada:** Jeśli WinOCR nie wykryje pełnego alertu, ciężki RapidOCR jest uruchamiany **WYŁĄCZNIE wtedy**, gdy spełniony jest Gate 1 (z poszlaką tekstową) LUB Gate 2 przy awarii WinOCR. W przeciwnym razie funkcja natychmiast zwraca `None` w 75 ms, redukując obciążenie CPU w stanie bezczynności do ~0-2%.
* **⚠️ KRYTYCZNA REGUŁA DLL WINDOWS (Import Order):**
  * W środowisku Windows moduł `onnxruntime` **MUSI** być zaimportowany przed jakimkolwiek modułem `winrt` (`winrt.windows.media.ocr`). Odwrócenie kolejności powoduje kolizję inicjalizacji wielowątkowej COM/WinRT i krytyczny błąd: `ImportError: DLL load failed while importing onnxruntime_pybind11_state`.
* **Zasady pętli czasu i Countdown Lock w Silniku Makr (`mvp/bot/macro_engine.py`):**
  1. **Minimalny krok czasowy:** Wszelkie operacje `_sleep_with_budget` muszą posuwać czas o minimum `max(0.001, duration)` z tolerancją `0.002s` przy porównaniach float, zapobiegając zamrożeniu symulowanego czasu w nieskończonych pętlach (`continue` busy-loop).
  2. **Countdown Lock ($\le 3.5\text{ s}$):** Gdy do punktu $T_0 - \text{lead\_time}$ pozostaje $\le 3.5\text{ s}$, silnik makra całkowicie blokuje dalsze zapytania OCR i zasypia bezpośrednio do momentu wyzwolenia spamu.
  3. **CPU Pause Window ($< 1.0\text{ s}$):** W oknie CPU pause następuje natychmiastowe uśpienie wątku do `target_mono = estimated_t0_mono - t0_lead_time`.
* **Legalność komercyjna (Commercial-Safe):**
  * Cały nowy potok OCR (`Windows.Media.Ocr`, `winocr` na licencji MIT, `rapidocr-onnxruntime` na licencji Apache 2.0, wagi modeli Baidu PP-OCR na licencji Apache 2.0, `onnxruntime` na licencji MIT) jest w 100% legalny, darmowy i wolny od tantiem do zastosowań komercyjnych. Wyeliminowano ryzyko restrykcji `CC-BY-NC` występującej w starym modelu CRAFT.

### 7. Eliminacja Scapy, Sniffingu Sieciowego i Sterownika Interception — Przejście na WinInput (Wrzesień 2026)
* **Czyste wejście WinInput (`SendInput`):**
  * Z bota i testów trwale wyeliminowano wszelkie zależności i nawiązania do sterownika jądra `interception` oraz bibliotek przechwytywania ruchu (`scapy`, `windivert`, `pydivert`, `pcapy`).
  * Jedynym aktywnym backendem generowania kliknięć w `mvp/bot/input/` jest natywny `SendInputBackend` oparty o Win32 API (`user32.SendInput`).
  * Metody `spam_down`/`spam_up` wysyłają wyłącznie `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_LEFTDOWN/UP` (**BEZ `MOUSEEVENTF_MOVE`** — zgodnie z Regułą 2, ruch w trakcie wciśnięcia anuluje `eligibleForClick`). Ruch między kolejnymi kliknięciami realizuje osobna metoda `spam_move` wywoływana wyłącznie przy zwolnionym przycisku.
* **Status plików `.pcapng` w `data/pcaps/`:**
  * Pliki `.pcapng` stanowią wyłącznie statyczne dane telemetryczne do analizy inżynierii wstecznej offline (np. Wireshark). Żaden aktywny kod bota ich nie odczytuje ani nie uruchamia bibliotek sniffingowych w pętli wykonawczej.

### 8. Bufor Pre-aiming w Pętli Wejścia Unity i Czas CPU (`direct_first=True`)
* **Koalescencja zdarzeń i PlayerLoop Unity:**
  - Wysłanie `spam_move` i natychmiastowego `spam_down` w czasie $\Delta t = 0\text{ ms}$ powoduje koalescencję zdarzeń w kolejce Windows oraz wewnątrz Unity (`Update` / `EventSystem`), przez co kliknięcie jest kwalifikowane jako ruchome (`eligibleForClick = false`) lub gubione przed raycastem mapy (`GraphicRaycaster`).
  - **Zasada:** Przy pierwszym kliknięciu w punkcie docelowym (`direct_first=True`), po wysłaniu `spam_move(target_x, target_y)` wymagany jest bufor stabilizacji **`time.sleep(0.025)` (25 ms)**.
  - **ZAKAZ:** Nigdy nie używaj `precise_sleep` (busy-loop `perf_counter`) dla bufora pre-aimingu! Użycie `time.sleep` oddaje kwant czasu CPU silnikowi gry (PlayerLoop) na przetworzenie `WM_MOUSEMOVE` i zapobiega zawieszeniu w środowiskach testowych z zamrożonym zegarem `perf_counter`.
  - Czas trwania spamu (`t_spam_start = time.perf_counter()`) jest mierzony dopiero PO zakończeniu bufora pre-aiming.

### 9. Spójność Częstotliwości Klikania z Konfiguracją GUI (`spam_clicks_per_sec`)
* **Brak sztucznego nadpisywania CPS:**
  - Silnik bota (`MacroEngine`) oraz pętla wykonawcza (`BotRunner`) pobierają docelową częstotliwość klikania z obiektu konfiguracji: `self._config.spam_clicks_per_sec`.
  - Domyślna wartość w konfiguracji GUI to 30 CPS (lub inna wybrana przez użytkownika). Fallback 38 CPS stosowany jest wyłącznie wtedy, gdy silnik makra jest uruchamiany w testach headless bez obiektu `BotConfig`.

### 10. Logika Wyzwalania Timera OCR i Ochrona Przed Anomaliami
* **Wczesne wyzwalanie według progu GUI (`spam_threshold_s`):**
  - Jeśli w konfiguracji zdefiniowano próg wyzwalania `spam_threshold_s` (np. 5.0 s), to po potwierdzeniu odczytu $\le \text{spam\_threshold}$ przez histerezę ($N \ge 2$), silnik makra natychmiast przechodzi w fazę spamu. Wyeliminowano uśpienie wątku do $T_0 - \text{lead\_time}$.
* **Wzrost timera (Timer Jump):**
  - Gdy odczyt nagle wzrośnie (`value > last_known_value` lub skok $> \text{\_JUMP\_DETECTION\_THRESHOLD\_S}$), oznacza to np. opuszczenie helikoptera przez gracza lub przełączenie kamery.
  - Bot **NIE MOŻE** interpretować tego jako końca odliczania: resetuje licznik histerez (`confirmed_count = 0`), resetuje estymatę $T_0$ (`estimated_t0_mono = None`), wycofuje stan przygotowania (`spam_prepared = False`) i aktualizuje `last_known_value = value`.
* **Przedwczesne zniknięcie timera:**
  - Zniknięcie timera (`value is None`) wyzwala natychmiastowy spam **WYŁĄCZNIE wtedy**, gdy poprzednia potwierdzona wartość timera znajdowała się w oknie docelowym (`last_known_value <= spam_threshold_s`). Zniknięcie odczytu przy wysokiej wartości timera (np. 40 s) jest ignorowane i nie odpala klikania.

### 11. Rozwiązanie Konfliktu Filtrów Unity (`MobileTouchCamera` vs `ClickDetector` — Podejście B)
* **Zasada działania dwóch filtrów:**
  1. `BitBenderGames.MobileTouchCamera` posiada próg przeciągania **$\approx 1.5\text{ px}$** w trakcie wciśnięcia (`DOWN` $\rightarrow$ `UP`). Jakikolwiek ruch w tym oknie unieważnia kliknięcie (`eligibleForClick = false`) i ucieka kamerą.
  2. `ClickDetector` posiada próg wielokliku **$5.0\text{ px}$ w oknie $300\text{ ms}$**. Kolejne kliknięcia w odległości $< 5.0\text{ px}$ są sklejane w dwuklik (`ExecuteDoubleClick`), co na mapie terenu wywołuje centrowanie widoku zamiast otwarcia skrzynki (`AllianceArms_OpenBox`).
* **Wymóg Podejścia B (Wdrożony wrzesień 2026):**
  - Kolejne kliknięcia **MUSZĄ** być rozdzielone dystansem euklidesowym **$D \ge 5.0\text{ px}$** (twarda dolna granica $\text{amp} \ge 1.80\text{ px}$ daje dystans $D \ge 5.09\text{ px}$ w `_noise_offset()`), co trwale resetuje licznik wielokliku i eliminuje 1-sekundowy cooldown Double-Click w Unity.
  - Ruch kursora `spam_move` może następować **WYŁĄCZNIE** w przerwaniu `UP` ze statusem `state = 0` według reguły splitu $40\% / 60\%$ (Reguła 2). W trakcie wciśnięcia `DOWN` $\rightarrow$ `UP` kursor pozostaje w $100\%$ nieruchomy ($\Delta r = 0$).

### 12. Optymalizacja Obciążenia CPU i Izolacja Uprawnień UIPI (Win32)
* **Redukcja obciążenia procesora w pętli klikania (`precise_sleep` / `precise_sleep_until`):**
  - Przy aktywnym timerze wysokiej rozdzielczości `timeBeginPeriod(1)`, próg uśpienia wątku wynosi **$1.5\text{ ms}$** (`if rem > 0.0015: time.sleep(rem - 0.001)`).
  - W oknie mikro-oczekiwania ($> 0.4\text{ ms}$) dodano system yield `time.sleep(0)`.
  - Pętla busy-wait spinlocka (`while perf_counter < target: pass`) zostaje ograniczona do $< 0.4\text{ ms}$. Redukuje to zużycie CPU o **ponad 80%**, zapobiegając dławieniu klatkażu gry Unity (`Survival.exe`) poniżej 60 FPS.
* **Ochrona przed desynchronizacją zegara i lawinowym burstingiem w `spam_click`:**
  - W przypadku wystąpienia opóźnień systemowych (np. `_check_focus()`, rendering zrzutu w Unity, alokacje), sztywny wskaźnik czasu `t_curr_down` nie może pozostać w przeszłości.
  - Przed każdym `DOWN` pętla weryfikuje `if t_curr_down < perf_counter(): t_curr_down = perf_counter()`, co gwarantuje nienaruszalność minimalnego czasu wciśnięcia `hold_s = 18.0 ms` i eliminuje generowanie zerowych kliknięć (<1 ms) ignorowanych przez Unity.
  - Przed kolejnym `DOWN` faza `UP` wymusza bufor minimum $8.0\text{ ms}$ (`min_up_time`), zapobiegając wyzwoleniu blokady `ReportFastClick` ($\Delta t < 25.0\text{ ms}$) oraz koalescencji zdarzeń myszy i ucieczce kamery.
* **Weryfikacja PID w `is_foreground` i eliminacja fałszywych refocusów:**
  - Metoda `is_foreground` weryfikuje nie tylko główne HWND, lecz także PID procesu aktywnego okna (`GetWindowThreadProcessId`). Zapobiega to fałszywemu wykrywaniu utraty fokusu na oknach potomnych i tooltipach Unity, co eliminuję niepotrzebne wywołania `SetForegroundWindow` i zamrażanie pętli wejściowej Unity (`Input.ResetInputAxes()`).
* **Weryfikacja UIPI (User Interface Privilege Isolation) / Błąd 5 (`ERROR_ACCESS_DENIED`):**
  - Zgodnie z zabezpieczeniami Windows UIPI, proces bota o poziomie uprawnień *Medium* nie może wysyłać zdarzeń `SendInput` do okna gry działającego jako Administrator (*High Integrity Level*).
  - Klasa `Clicker.initialize()` automatycznie sprawdza uprawnienia (`IsUserAnAdmin`). W przypadku uruchomienia gry jako Administrator, bot również **musi** zostać uruchomiony z uprawnieniami Administratora.

### 13. Architektura Wydajności GUI i Silnika Makr (Optymalizacje Wrzesień 2026)
* **Stały Rozmiar Tekstury Podglądu DPG (`PREVIEW_WIDTH` 960 × `PREVIEW_HEIGHT` 540):**
  - Tekstura podglądu DearPyGui nie może być alokowana w natywnej rozdzielczości gry (np. 1440p/4K). Stały bufor 960×540 zmniejsza narzut pamięci bufora float32 RGBA o **ponad 75%** (z ~59 MB do ~8 MB per klatka).
  - Przy wyłączonym podglądzie (`preview_enabled = False`) kolejka `frame_queue` jest natychmiast opróżniana, zapobiegając wyciekom pamięci RAM.
* **Throttling Logów i Dirty Checking Kontrolek DearPyGui:**
  - Historia logów w pamięci widżetu GUI jest ograniczona do 500 wpisów (zamiast 1500), a aktualizacja tekstu logów jest buforowana do maksymalnie **4 Hz (interwał 250 ms)**. Eliminuje to alokacje ~750 KB stringów i rekalkulacje glifów ImGui co 16 ms.
  - Wprowadzono wzorzec *Dirty Checking* w `set_game_status`, `_update_status_bar` i `_update_dashboard` — wywołania C-API DPG są wykonywane wyłącznie przy faktycznej zmianie wartości, eliminując ~1000 zbędnych wywołań C-API/s.
* **Asynchroniczne Zatrzymywanie Bota i Zapis Zdarzeń:**
  - `bot_runner.stop()` jest wywoływany w asynchronicznym wątku tła (`_stop_worker`), co zapobiega 2.5-sekundowemu blokowaniu pętli renderowania GUI przez `join()` i likwiduje problem zamrażania okna aplikacji ("Brak odpowiedzi").
  - Zrzut logów zdarzeń do pliku CSV (`_event_logger.flush()`) odbywa się w dedykowanym wątku tła (`daemon=True`), eliminując mikro-przycięcia (stutter) co 5 sekund.
* **Buforowanie PID w Pętli Window Watchdog:**
  - W `_find_process_pids` wprowadzono pamięć podręczną z czasem życia **TTL = 3.0 s** oraz szybką weryfikację przez `psutil.pid_exists(pid)`. Likwiduje to przeszukiwanie wszystkich procesów systemu przez `psutil.process_iter` co 5 kliknięć (co 130 ms).
* **Optymalizacja Pamięci OCR i Czyszczenie Zasobów:**
  - W `TimerOCR.read_timer` wyeliminowano kopiowanie pełnego bufora bajtów `image.tobytes()`, zastępując je próbkowanym hashowaniem numpy widoku tablicy.
  - Metoda `BotRunner.shutdown()` deterministycznie zatrzymuje wątek `anti_detect.stop()`, a `GlobalHotkey.stop()` zwalnia rejestrację klawiszy przez awaryjne `UnregisterHotKey`.

### 14. Inżynieria Wsteczna Pętli Wejścia Unity i Adresy Il2Cpp (Frida Telemetria Wrzesień 2026)
* **Pętla wejścia silnika Unity w `Survival.exe`:**
  - Silnik Unity **całkowicie pomija** pętlę komunikatów Unicode `DispatchMessageW` oraz `PeekMessageW` (0 wywołań).
  - Pętla wejścia Unity opiera się na:
    - **`user32.dll!PeekMessageA` (60 Hz):** pobieranie komunikatów okna w pętli renderowania klatek.
    - **`user32.dll!GetCursorPos` (60 Hz):** odpytywanie pozycji kursora 1:1 z każdą klatką Unity.
    - **`user32.dll!GetAsyncKeyState(VK_LBUTTON = 0x01)` (1082 Hz):** próbkowanie fizycznego stanu wciśnięcia przycisku myszy ponad 1000 razy na sekundę.
* **Wewnętrzne adresy Il2Cpp w `GameAssembly.dll`:**
  - **`0x7ff849ddefe0`:** wewnętrzna funkcja `UnityEngine.Input.GetMouseButtonDown(0)` sprawdzana w każdej klatce. Zwraca `1` w klatce, w której nastąpiło wciśnięcie przycisku.
  - **`0x7ff8451b22b0`:** metoda `ClickIntervalMonitor.Update()`. Sprawdza stan `GetMouseButtonDown(0)`, pobiera `Time.unscaledTime` (`0x7ff849d88850`) i oblicza $\Delta t = \text{currentTime} - \text{lastClickTime}$.
  - **`0x7ff8451b2270`:** metoda `ClickIntervalMonitor.ReportFastClick()`. Wywoływana gdy $\Delta t \le \text{\_threshold}$ ($25.0\text{ ms}$), blokuje pakiet zrzutu skrzynki.
* **Potwierdzenie telemetryczne:**
  - W sesji Frida zarejestrowano 180/180 kliknięć bota w `0x7ff849ddefe0`. Przy konfiguracji 30 CPS (średni okres $\approx 32.5\text{ ms}$) liczba wywołań blokady `ReportFastClick` wyniosła **0**.

### 15. Koordynaty Uderzenia w Skrzynkę (`click_x = 50%, click_y = 50%`)
* **Wybór punktu uderzenia:**
  - Standardowy punkt centralny zrzutu wynosi **`click_x = 50.0%, click_y = 50.0%`**.
  - W przypadku wystąpienia przeszkód (np. modele czołgów sojuszu na $Y = 52\%$), w analizie graficznej odnotowano opcjonalną alternatywę $Y = 57.0\%$ (dolna krawędź budynku), jednak domyślnym i preferowanym celem makra pozostaje geometryczny środek: **`50%, 50%`**.

### 16. Domyślne Interwały OCR i Eliminacja Narzutu CPU
* **Optymalne wartości domyślne w GUI (`config.json` i `MVPConfig`):**
  - **`idle_check_interval_s = 3.0s`:** faza normalna (idle) sprawdza timer co 3 sekundy, redukując obciążenie procesora do 0% i likwidując zwalnianie gry podczas wielominutowego lotu helikoptera.
  - **`fast_check_interval_s = 0.2s`:** faza szybka (fast) sprawdza timer 5 razy na sekundę (co 200 ms).
  - **`fast_threshold_s = 60s`:** wejście w fazę szybką następuje dopiero 60 sekund przed zrzutem (zamiast 300s).
* **Zachowanie WinOCR vs RapidOCR dla timera:**
  - W polskim systemie Windows (`lang='pl'`) silnik `Windows.Media.Ocr` nie rozpoznaje stylizowanych cyfr timera na wycinku 25×86 px (`lines: []`).
  - System automatycznie używa Pass 1 (`RapidOCR rec-only`), który wykonuje inferencję ONNX w **25–32 ms** ze 100% poprawnością odczytu.






