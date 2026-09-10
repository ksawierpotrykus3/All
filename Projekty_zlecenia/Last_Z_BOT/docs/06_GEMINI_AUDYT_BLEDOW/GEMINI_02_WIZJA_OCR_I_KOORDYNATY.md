> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# GEMINI AUDYT CZĘŚĆ 2: SYSTEM WIZJI, OCR I PRZELICZANIE KOORDYNATÓW (v2.0)
**Pliki audytowane:** `mvp/bot/coordinates.py`, `mvp/bot/capture.py`, `mvp/bot/ocr.py`, `mvp/bot/arrow_detector.py`  
**Wersja:** 2.0 (Po rewizji i doprecyzowaniu szczegółów)

---

## 1. BŁĄD KRYTYCZNY: Sztywna kalibracja Y i podwójna korekta 32 px w cropie OCR

### Dowód w kodzie
Plik: `mvp/bot/coordinates.py:4-23, 81-118`

```python
_CALIB_FULL_H: float = 1111.0
_CALIB_TB_PX: float = 31.0
_CALIB_CLIENT_H: float = 1080.0

_CALIB_TB_FRACTION: float = _CALIB_TB_PX / _CALIB_FULL_H        # = 31 / 1111 = 0.02790279
_CALIB_CLIENT_FRACTION: float = _CALIB_CLIENT_H / _CALIB_FULL_H  # = 1080 / 1111 = 0.9720972

def calib_y_to_client_fraction(y_calib_pct: float) -> float:
    return max(0.0, min(1.0, (y_calib_pct / 100.0 - _CALIB_TB_FRACTION) / _CALIB_CLIENT_FRACTION))
```

Oraz w metodzie cropu klatki `WindowContext.roi_to_frame_pixels()` (`coordinates.py:98-118`):
```python
    def roi_to_frame_pixels(
        self, roi: GameROI, frame_width: int, frame_height: int
    ) -> tuple[int, int, int, int]:
        ...
        top_frac = calib_y_to_client_fraction(roi.top)
        bottom_frac = calib_y_to_client_fraction(roi.bottom)
        top = max(0, min(frame_height, int(frame_height * top_frac)))
        bottom = max(0, min(frame_height, int(frame_height * bottom_frac)))
        return (left, top, right, bottom)
```

### [STAN POPRAWIONY / DOPRECYZOWANIE]: Rozbicie ścieżki OCR vs Kliknięć
1. **Wycinek klatki OCR (`roi_to_frame_pixels`) — 100% TWARDY BUG:**
   - Klatka pobierana z DXCam (`capture.py:77`) obejmuje **wyłącznie obszar klienta gry** (`client_rect` o wymiarach $1920 \times 1080$). W klatce obrazu **nie ma paska tytułu**.
   - Nałożenie `calib_y_to_client_fraction` na klatkę DXCam odejmuje nieistniejący pasek 31 px po raz drugi.
   - Dla timera `_ROI_TIMER` (`top = 16.5%`, `bottom = 22.5%`):
     $y_{\text{top\_calc}} = \frac{0.165 - 0.0279}{0.9721} \times 1080 = 152.3\text{ px}$ (zamiast prawidłowych $178.2\text{ px}$).
   - **Crop OCR jest przesunięty o 26–32 px w górę**, co obcina górną połowę cyfr timera. EasyOCR zwraca `None` lub gubi sekundy.
2. **Przeliczanie kliknięć na ekran (`to_screen`):**
   - Jeśli współrzędne w `macro_def.py` były rejestrowane na oknie z paskiem tytułu, korekta w `to_screen` jest zasadna pod warunkiem pracy w oknie ze standardowym paskiem 31 px. Jeśli gra działa w trybie bezramkowym / fullscreen, przesunięcie występuje również przy kliknięciach.

---

## 2. BŁĄD KRYTYCZNY: Serwowanie przestarzałych klatek z cache przez 5 sekund (`capture.py`)

### Dowód w kodzie
Plik: `mvp/bot/capture.py:20, 90-109`

```python
_MAX_FRAME_AGE_SECONDS = 5.0
...
    def grab(self) -> np.ndarray | None:
        try:
            frame = camera.grab(region=region)
        except Exception:
            ...
        if frame is not None:
            with self._lock:
                self._latest_frame = frame
                self._latest_frame_ts = time.monotonic()
            return frame
        with self._lock:
            if (
                self._latest_frame is not None
                and (time.monotonic() - self._latest_frame_ts) < _MAX_FRAME_AGE_SECONDS
            ):
                return self._latest_frame # <--- Zwraca stary kadr do 5 sekund!
            return None
```

### Mechanizm awarii
- Gdy DWM nie przekaże nowej klatki (np. statyczny fragment obrazu gry), `camera.grab()` zwraca `None`.
- Kod bota pobiera wówczas z pamięci kadr sprzed 4–5 sekund.
- W pętli `watch_timer` bot widzi zamrożony licznik (np. 6s), mimo że w grze licznik dobiegł już do 0s ($T_0$). Bot spóźnia rozpoczęcie spamu, a serwer odrzuca zgłoszenie z błędem `5560006`.

---

## 3. BŁĄD POWAŻNY: Obciążenie CPU i kaskadowa inferencja EasyOCR

### Dowód w kodzie
Plik: `mvp/bot/ocr.py:49-51, 363-411` oraz `mvp/bot/macro_engine.py:1017-1023`

```python
# macro_engine.py:
max_passes = 2 if phase == "fast" else 4
raw_res = self._read_timer_value(step, window, max_passes=max_passes)
```

```python
# ocr.py:
torch.set_num_threads(1)
...
# Pass 1: white mask EasyOCR
results_white = self._reader.readtext(white_up, allowlist="0123456789:", detail=1)
...
# Pass 2: upscaled 2x EasyOCR
results = self._reader.readtext(upscaled, allowlist="0123456789:", detail=1)
...
# Pass 3 (gdy max_passes >= 3): Tesseract z pętlą 4x PSM
# Pass 4 (gdy max_passes >= 4): upscaled 4x EasyOCR
```

### [STAN POPRAWIONY / DOPRECYZOWANIE]:
- W fazie `fast` wykonywane są **2 przejścia EasyOCR** (Pass 1 i Pass 2).
- W fazie `idle` (oraz przy nieudanym odczycie) wykonywane są **do 4 przejść (3x EasyOCR + 1x Tesseract)**.
- Wykonywanie inferencji na 1 wątku (`torch.set_num_threads(1)`) powoduje zużycie 100% rdzenia i narzut 400–800 ms w fazie `fast`, co dławi pętlę i opóźnia wykrycie zrzutu skrzynki.

---

## 4. BŁĄD POWAŻNY: Brak odporności na zmiany skali w `ChatArrowDetector`

### Dowód w kodzie
Plik: `mvp/bot/arrow_detector.py:107-137`

- `base_scale = fh / 1075.0 if fh > 50 else 1.0` — sztywne założenie bazowej rozdzielczości 1075 px.
- Przy progu `threshold = 0.92` (lub `0.88`), w niższych rozdzielczościach (np. 1600x900, 1280x720) dopasowanie wzorca `arrow.png` spada poniżej progu $\to$ bot nie klika strzałki i wisi na nasłuchu czatu (Step 1).
