# Plan Implementacji: Naprawa Narzutu CPU w `watch_timer` oraz Niezawodności Spam Clicka w Grze Unity

Naprawa problemu 100% obciążenia CPU w fazie `watch_timer` oraz wyeliminowanie przyczyn gubienia kliknięć przez silnik gry Unity (`Survival.exe` — Last Z / Last War) w oparciu o inżynierię wsteczną silnika i wzorce z publicznych botów (*LastWarBot*, *BoostBot*).

---

## User Review Required

> [!IMPORTANT]
> **Domyślna częstotliwość klikania pod Unity 60 FPS:**  
> W toku badań potwierdzono, że częstotliwość **30.0 CPS** (cykl 33.3 ms = dokładnie 16.6 ms DOWN + 16.7 ms UP) zapewnia **100% niezawodności** w rejestracji kliknięć w czystej grze Unity 60 FPS (każda kolejna klatka silnika to zmiana stanu przycisku). Dotychczasowy tryb 38 CPS powodował aliasing stanu zwolnienia (UP trwający zaledwie 8 ms wypadał pomiędzy próbkowaniami Unity i był traktowany jako ciągły drag). Utrzymujemy 30 CPS jako podstawową konfigurację spamu.

> [!NOTE]
> **Fast WinOCR w Timerze:**  
> Dodanie natywnej ścieżki `Windows.Media.Ocr` do `TimerOCR` obniży czas rozpoznawania cyfr timera z ~45–80 ms do **8–12 ms**, redukując zużycie CPU w fazie oczekiwania o ponad **90%** bez utraty dokładności (RapidOCR ONNX pozostanie niezawodnym fallbackiem).

---

## Proponowane Zmiany

### Komponent: Silnik OCR ([`mvp/bot/ocr.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/ocr.py))

#### [MODIFY] [ocr.py](file:///f:/PROJEKTY/joaxx/mvp/bot/ocr.py)
- Rozszerzenie klasy [`TimerOCR`](file:///f:/PROJEKTY/joaxx/mvp/bot/ocr.py#L507) o obsługę szybkiej ścieżki **WinOCR** (`winocr.recognize_cv2_sync`):
  1. Sprawdzenie dostępności natywnego silnika WinOCR (identycznie jak w `ChatOCR`).
  2. W `_read_timer_uncached`: najpierw szybki odczyt WinOCR (~8–12 ms). Jeśli odczytano format czasu (`\d{1,2}:\d{2}` lub `\d+s`), natychmiast zwraca wynik.
  3. W przypadku braku rozpoznania w WinOCR: łagodne przejście do istniejącej ścieżki RapidOCR (Pass 1 rec-only -> Pass 2).
  4. Likwidacja niepotrzebnych ciężkich inferencji DBNet w pętli timera.

---

### Komponent: Silnik Makra ([`mvp/bot/macro_engine.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/macro_engine.py))

#### [MODIFY] [macro_engine.py](file:///f:/PROJEKTY/joaxx/mvp/bot/macro_engine.py)
- W metodzie [`_handle_watch_timer`](file:///f:/PROJEKTY/joaxx/mvp/bot/macro_engine.py#L1146):
  1. **Likwidacja busy-loop w fazie `fast`:**
     - Zapisywanie `ocr_interval_state["last_query_time"]` na podstawie czasu **zakończenia** zapytania OCR (`grab_time` / czas po powrocie z OCR), a nie starego znacznika czasowego sprzed wykonania OCR.
     - Obliczanie uśpienia z gwarantowaną podłogą `min_sleep`:
       ```python
       min_sleep_floor = 0.05 if (time_remaining is not None and time_remaining <= 3.0) else 0.10
       self._sleep_with_budget(max(min_sleep_floor, remaining), now, min_sleep=min_sleep_floor)
       ```
     - Wyeliminowanie pętli z uśpieniem 1 ms (`0.001s`), która generowała 100% zużycia CPU.
  2. **Bezpieczne wywołanie `spam_click`:**
     - Otoczenie wywołania `self.clicker.spam_click(...)` blokiem `try ... except ClickerError as exc` z zalogowaniem ostrzeżenia, zapobiegając przerwaniu makra w razie chwilowej odmowy Win32 SendInput.

---

### Komponent: Obsługa Klikania i Wejścia ([`mvp/bot/clicker.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/clicker.py))

#### [MODIFY] [clicker.py](file:///f:/PROJEKTY/joaxx/mvp/bot/clicker.py)
- W metodzie [`spam_click`](file:///f:/PROJEKTY/joaxx/mvp/bot/clicker.py#L236):
  1. **Stabilizacja fokusu okna Unity:**
     - Przed wysłaniem pierwszego kliknięcia sprawdzenie czy okno gry jest na pierwszym planie (`is_foreground(self.process_name)`).
     - Jeśli nie — wywołanie `force_foreground(self.process_name)` oraz odczekanie **`time.sleep(0.035)`** (35 ms), aby silnik Unity przetworzył `WM_ACTIVATEAPP` / `WM_SETFOCUS` i przywrócił pełny klatkaż 60 FPS przed rozpoczęciem spamu.
  2. **Tolerancja na pojedyncze błędy wejścia:**
     - W pętli `for i in range(count)`: w razie wystąpienia `ClickerError` (np. odmowa SendInput), zalogowanie ostrzeżenia i kontynuacja pętli zamiast załamania całego procesu.

---

### Komponent: Backend Win32 ([`mvp/bot/input/sendinput_backend.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/input/sendinput_backend.py))

#### [MODIFY] [sendinput_backend.py](file:///f:/PROJEKTY/joaxx/mvp/bot/input/sendinput_backend.py)
- W metodzie [`_send_fast`](file:///f:/PROJEKTY/joaxx/mvp/bot/input/sendinput_backend.py#L151):
  - Przy `sent != 1` sprawdzenie kodu błędu `GetLastError()`. Jeśli błąd to `ERROR_ACCESS_DENIED` (5) w trakcie działania bota, wyczyszczenie błędu i zalogowanie precyzyjnego komunikatu diagnostycznego (np. brak fokusu / UIPI) z opcją łagodnego retry.

---

## Plan Weryfikacji

### Testy Automatyczne
1. **Testy jednostkowe szybkiej ścieżki WinOCR w `TimerOCR`:**
   - Sprawdzenie poprawnego odczytu `00:05`, `02:30`, `15s` przy użyciu WinOCR i fallbacku do RapidOCR.
   - Uruchomienie: `uv run pytest mvp/tests/test_ocr.py -v`
2. **Testy eliminacji busy-loop w `_handle_watch_timer`:**
   - Weryfikacja czy pętla w fazie `fast` zawsze zachowuje minimalne uśpienie i nie wykonuje zapytań z 1 ms przerwą.
   - Uruchomienie: `uv run pytest mvp/tests/test_macro_engine.py -k "watch_timer" -v`
3. **Testy stabilizacji fokusu w `spam_click`:**
   - Weryfikacja czy `spam_click` sprawdza `force_foreground` i poprawnie wykonuje 30 CPS.
   - Uruchomienie: `uv run pytest mvp/tests/test_clicker.py -v`
4. **Pełna suita regresyjna projektu:**
   - Uruchomienie: `uv run pytest -m "not slow"`

### Weryfikacja Wydajnościowa (Benchmark)
- Uruchomienie benchmarku `scratch/diag_benchmark.py`:
  - Pomiar latencji `TimerOCR` (oczekiwany spadek z ~45 ms do ~10 ms).
  - Pomiar zużycia procesora podczas pętli timera.
