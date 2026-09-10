# Problem 7: Nie wiadomo, czy bot działa u kogokolwiek — podejrzenia środowiskowe

## Status: NIEPOTWIERDZONE — lista podejrzeń, nie diagnoza

## Ważne zastrzeżenie (aktualizacja)
Wcześniej zakładano, że „bot działa u wspólnika, a nie u klienta". **To założenie upadło** — wspólnik nie jest w stanie potwierdzić, czy bot u niego działa. Oznacza to, że:

- Nie mamy żadnego potwierdzonego środowiska, w którym bot działa poprawnie.
- Poniższe punkty to **hipotezy oparte na analizie kodu**, nie potwierdzone różnice sprzętowe.
- Klient nie odpowiedział na prośbę o dane środowiskowe ani LOGS.txt.

Dopóki nie dostaniemy twardego dowodu (LOGS.txt, nagranie), nie wiemy, czy problem to środowisko, logika, czy jedno i drugie.

## Podejrzenia środowiskowe (do weryfikacji, w kolejności hipotetycznego prawdopodobieństwa)

### 1. DPI / skalowanie Windows (125%/150%)
Plik: `mvp/main.py:37` + `mvp/bot/capture.py:23-24`
- `SetProcessDpiAwareness` może nie zadziałać w skompilowanym .exe (Nuitka) przed inicjalizacją GUI
- Skutek (hipoteza): rozjazd współrzędnych logicznych vs fizycznych pikseli

### 2. Multi-monitor / ujemne współrzędne
Plik: `mvp/bot/monitor_mapper.py:41-60, 100-104`
- `GetMonitorInfoW` bez `argtypes`/`restype` → możliwe obcięcie HMONITOR na 64-bit
- Monitor wtórny po lewej: `left = max(window_left - ml, 0)` może dać zły region

### 3. UIPI / uprawnienia (gra jako Administrator)
Plik: `mvp/bot/runner.py:189-201` — tylko `logger.warning`, brak elewacji
- Gra jako admin + bot jako user → Windows może blokować SendInput

### 4. Rozdzielczość okna gry ≠ 1920x1080 (hardcoded)
- `mvp/bot/coordinates.py` — `_CALIB_CLIENT_H = 1080.0`, `1920.0` hardcoded
- `mvp/bot/arrow_detector.py:107` — `base_scale = fh / 1075.0`

### 5. Wolniejszy CPU
- `mvp/bot/clicker.py` — spin-wait
- `mvp/bot/macro_engine.py:1043-1045` — `grab_time` przed `grab()`

## Dodatkowe podejrzenia z audytu Gemini (nieoczywiste)

### G-02: Brak kroku odbioru nagrody
`mvp/macro_def.py:173-189` — makro kończy się na WATCH_TIMER, nie ma kroku "otwórz skrzynkę".

### G-02 cz.2: Szum pozycyjny 2.5–3.0 px > próg 1.5 px
`mvp/bot/clicker.py:440-444` — dystans euklidesowy do ~4.2 px, kamera może uciekać.

### G-03: MOUSEEVENTF_MOVE w spam_down/spam_up
`mvp/bot/input/sendinput_backend.py:187-199`

### G-04: Podwójna korekta 31px w ROI OCR
`mvp/bot/coordinates.py:97-116`

### G-05: Cache DXCam 5s
`mvp/bot/capture.py:19, 97-108` — `_MAX_FRAME_AGE_SECONDS = 5.0`

### G-06: dpg.set_value z wątku tła
`mvp/gui/main_window.py:813-830` — możliwy crash 0xC0000005

### G-07: Stripe webhook ignoruje metadata.user_id
`mvp/backend/main.py:336-341`

### G-08: Wyścig wątków hotkeyi
`mvp/gui/global_hotkey.py`

### G-12: Brak elewacji admina w instalatorze
`mvp/build/installer.iss` — brak `PrivilegesRequired=admin`

## Stan na 2026-08-28 — ZWERYFIKOWANE FAKTY (twarde dane)

- **GUI odpala się z kodu źródłowego** u programisty (`python -m mvp.main`) — potwierdzone własnoręcznie.
- **GUI odpala się z exe** (`dist\LastZBot-Dev.exe`) u programisty — potwierdzone własnoręcznie. To ten sam typ pliku, który dostał klient.
- **GUI odpala się u wspólnika (Maksa)** — po zwolnieniu miejsca w `%TEMP%`. Potwierdzone empirycznie.
- **Automatyka (makro) NIE jest potwierdzona** — nie wiemy, czy pełny cykl (wykrycie → teleport → licznik → spam → nagroda) działa. GUI startuje, ale makro nie było testowane end-to-end.

## POTWIERDZONA PRZYCZYNA „pustej konsoli"

Nuitka **onefile** rozpakowuje cały program do `%TEMP%` przy każdym uruchomieniu. Gdy na dysku/temp brakuje miejsca, exe pokazuje puste okno konsoli i umiera bez komunikatu — dokładnie to, co opisał klient.

Wniosek: to jest realny bug dystrybucyjny (zadanie #7 w planie: przejście z onefile na standalone). „Pusta konsola" u klienta najprawdopodobniej to ten sam mechanizm albo podobny problem środowiskowy (pełny temp, blokada antywirusa na temp, ścieżka Unicode). Nie jest to wina kodu ani logiki.

## Następny krok — uzyskać twarde dane
Bez LOGS.txt od klienta lub realnego testu nie jesteśmy w stanie powiedzieć, czy problem to środowisko, logika, czy oba. Klient odmówił dalszego testowania obecnej wersji — możliwa kontynuacja jako nowe zlecenie.