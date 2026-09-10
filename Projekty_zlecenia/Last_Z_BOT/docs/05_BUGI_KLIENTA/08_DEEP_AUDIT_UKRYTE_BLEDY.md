> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# DEEP AUDIT — rzeczy, których wcześniej nie widzieliśmy

Śledztwa w 4 obszarach: build/dystrybucja, grafika/input, ukryte zależności kodu, backend/wdrożenie. Poniżej NAJWAŻNIEJSZE nieoczywiste ustalenia, które wyjdą przy sprzedaży wielu klientom na różnych Windowsach.

## A. BACKEND / WDROŻENIE (krytyczne — złamie WSZYSTKICH płacących)

### A1. `/license/validate` w Dockerze ZAWSZE zwróci 503
- `deploy/docker-compose.yml` nie przekazuje `LICENSE_PRIVATE_KEY_PEM` do kontenera
- `mvp/backend/main.py:67-70` — przy braku klucza rzuca 503
- Efekt: nikt nie uruchomi bota, mimo poprawnej płatności

### A2. Klucz publiczny klienta zahardkodowany, prywatnego NIE MA w repo
- `mvp/license.py:32` — publiczny klucz Ed25519 w kodzie
- `.env.example` każe WYGENEROWAĆ nową parę kluczy, ale to da podpis niepasujący do zahardkodowanego publicznego
- Efekt: po wdrożeniu `License response signature invalid` dla każdego

### A3. Brak `cryptography` w `deploy/requirements.txt`
- `deploy/Dockerfile` instaluje tylko ten plik
- `mvp/backend/license_signing.py:4-6` importuje `cryptography`
- Efekt: backend NIE STARTUJE w kontenerze (`ModuleNotFoundError`)

### A4. Brak bootstrapu admina
- `mvp/backend/models.py:21` — `is_admin=False` domyślnie, nigdzie nie ma seeda pierwszego admina
- Efekt: `/admin/licenses` i `/admin/reset-hwid` bezużyteczne — klient nie zarządza licencjami

### A5. Brak frontendu zakupowego
- Backend ma `/checkout/session`, ale nie ma ŻADNEJ strony, gdzie klient końcowy kupi licencję
- Efekt: proces zakupu niemożliwy bez ręcznego wywoływania API

### A6. Brak HTTPS/reverse proxy w docker-compose
- Stripe WYMAGA publicznego HTTPS dla webhooków
- Efekt: płatność przechodzi, ale licencja NIE aktywuje się (webhook nie dociera)

### A7. Webhook ignoruje `metadata.user_id`, szuka po emailu
- `mvp/backend/main.py:337-341` — gdy `customer_email` jest None, event cicho ignorowany
- Efekt: cicha utrata aktywacji, trudna do zdiagnozowania

### A8. SQLite sync w async, brak WAL/busy_timeout
- `mvp/backend/database.py:7-13` — przy równoległych requestach `database is locked`

---

## B. BUILD / DYSTRYBUCJA (krytyczne — bot nie ruszy na czystym Windowsie)

### B1. Skróty nie wymuszają admina → UIPI blokuje kliknięcia
- `installer.iss:52-54` — skróty do `LastZBot.exe` bez flagi elewacji
- Gra jako admin + bot jako user = SendInput cicho blokowany
- Efekt: bot "klika" ale w grze nic się nie dzieje

### B2. Zmienne HKLM działają tylko przy PIERWSZYM uruchomieniu
- `installer.iss:64-73` — `EASYOCR_MODULE_PATH` w HKLM widoczne dopiero po restarcie
- Przy drugim uruchomieniu ze skrótu EasyOCR próbuje POBIERAĆ modele z internetu (freeze)
- Efekt: bot zamiera na starcie przy kolejnych uruchomieniach

### B3. Brak VC++ redist w instalatorze
- `dist/main.dist/*.dll` nie zawiera `msvcp140_2.dll` ani `concrt140.dll`
- Efekt: `ImportError: DLL load failed` na czystym Windowsie

### B4. `BUILD_MODE='dev'` w repo i w dist
- `mvp/build_mode.py:4` — `BUILD_MODE = 'dev'` (gitignored, nie resetowany)
- Ryzyko wysłania DEV builda do klienta (licencja pominięta)

### B5. `_compiled_verify_response` NIGDY nie używany
- `license.py:17-23` — sprawdza `__compiled__` / `builtins.__compiled__`, których Nuitka nie ustawia
- Efekt: obfuskacja klucza przez Cython NIESKUTECZNA — klucz publiczny jest w jawnej postaci w exe

### B6. Brak podpisu cyfrowego + 270 MB onefile
- SmartScreen zablokuje exe pobrany z internetu ("Windows protected your PC")
- Antywirus może skasować plik

---

## C. GRAFIKA / INPUT (krytyczne — inny sprzęt = inne zachowanie)

### C1. `setup_dpi_awareness()` NIGDY nie wywoływana w kodzie produkcyjnym
- `capture.py:23-24` definiuje, ale nikt nie woła
- Efekt: współrzędne logiczne vs fizyczne rozjeżdżają się przy skalowaniu 125%/150%

### C2. dxcam 1.x: HAGS, multi-GPU, exclusive fullscreen
- `capture.py:64,77` — HAGS i multi-GPU (Intel iGPU + NVIDIA) dają czarne klatki bez błędu
- Efekt: bot "działa" ale widzi czarny ekran

### C3. Format kolorów BGR zakładany bez weryfikacji
- `capture.py:64` — `output_color="BGR"`, ale AMD/Intel mogą zwrócić RGB
- `ocr.py:367` + `arrow_detector.py:60` — cicha awaria detekcji (kanały zamienione)
- Efekt: OCR i strzałka czatu nie działają, bez żadnego wyjątku

### C4. Brak trybu FPS dla 30/120/144 Hz
- `clicker.py:19-21` — `INPUT_FPS_MODES = ("60", "200")`, brak 30/120/144
- `runner.py:107-112` — `input_fps_mode` NIE przekazywane z configu
- Efekt: kliki zgubione (30 FPS) lub nienaturalne (120 FPS)

### C5. SendInput dzielnik 65536 zamiast 65535
- `sendinput_backend.py:132-133` — prawy dolny piksel nieosiągalny (1 px obok)

### C6. Kolejność EnumDisplayMonitors ≠ kolejność wyjść DXGI
- `monitor_mapper.py:59` — na laptopie z 2 GPU zły `output_idx`
- Efekt: bot przechwytuje PULPIT zamiast gry

### C7. Interception zainstalowany, ale NIEUŻYWANY
- `backend.py:11-17` — tylko `SendInputBackend` zarejestrowany
- `scripts/install_interception.ps1` instaluje sterownik jądra bez efektu

---

## D. UKRYTE ZALEŻNOŚCI KODU

### D1. Brak encoding w RotatingFileHandler
- `logging_setup.py:35-40` — polski login Windows = polskie znaki w ścieżce = `UnicodeEncodeError` zabija wątek logujący

### D2. GUI min 1600x950 — bezużyteczne na laptopie 1366x768
- `main_window.py:96-97` — okna nie da się zmniejszyć

### D3. EasyOCR pobiera modele do cwd przy pierwszym uruchomieniu
- `ocr.py:21-57` — w Program Files bez praw/internetu = OCR cicho nie działa (bot "chodzi" ale nic nie robi)

### D4. `_get_fresh_window` połyka wyjątki, zwraca stare okno
- `macro_engine.py:1199-1211` — gra się przesunęła, bot klika w starym miejscu

### D5. SleepGuard wyjątek → bot bez ochrony przed snem
- `anti_sleep.py:76` + `runner.py:296` — wyjątek złapany jako warning, Windows uśnie i bot zamiera

### D6. `ScreenCapture.start()` połyka błąd kamery
- `capture.py:58-68` — DXcam nie działa (RDP/stary GPU) → bot startuje "normalnie", ale grab zwraca None

### D7. Config zapis do Program Files może nie działać
- `config.py:73-74` + `main_window.py:993` — w Program Files bez praw = zmiany GUI giną po restarcie

---

## PRIORYTET NAPRAWY (dla produktu "gotowego do sprzedaży wielu ludziom")

1. **A1-A3** (backend nie startuje / licencje nie działają) — to zabija cały model SaaS
2. **B1-B2** (UIPI + EasyOCR modele) — to zabija bota u większości klientów
3. **C1, C3** (DPI + format kolorów) — to zabija detekcję na różnym sprzęcie
4. **C4** (FPS mode) — bot musi działać na 30/60/120/144 Hz
5. **A5** (frontend) — bez tego klient nie sprzeda licencji swoim klientom
6. Reszta wg potrzeb

---

## UWAGA O CHARAKTERZE PRODUKTU

Ten bot jest sprzedawany wielu osobom na świecie. Każda hardcoded wartość (1080p, 60 FPS, BGR, pojedynczy monitor, 100% DPI, admin, polskie znaki) to awaria u części klientów. Produkt "gotowy do sprzedaży" musi to wszystko obsługiwać dynamicznie.