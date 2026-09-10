> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Fast OCR Migration Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Całkowite usunięcie EasyOCR i PyTorch (2.5 GB) z projektu Last Z Bot i wdrożenie ultraszybkiego potoku OCR (WinOCR 13-17 ms + RapidOCR ONNX 39 ms rec-only), zoptymalizowanego pod minimalną latencję detekcja -> reakcja/kliknięcie.

**Architecture:** Hybrydowy pipeline dwustopniowy: natywny Windows.Media.Ocr (WinOCR) jako błyskawiczny silnik pierwszego wyboru (~13-17 ms) dla czatu i alertów helikoptera, z automatycznym fallbackiem na RapidOCR (ONNX Runtime); dla timera odliczania skrzynki — RapidOCR Recognition-Only (~39 ms) na stałym ROI bez narzutu modeli detekcji.

**Tech Stack:** Python 3.11, ONNX Runtime, RapidOCR, WinOCR (WinRT Windows.Media.Ocr), OpenCV.

---

### Task 1: Aktualizacja zależności projektu (pyproject.toml i lockfile)

**Files:**
- Modify: `pyproject.toml`
- Command: `uv remove easyocr`, `uv add rapidocr-onnxruntime winocr`, `uv sync --extra dev`

**Step 1: Usunięcie easyocr i dodanie rapidocr-onnxruntime oraz winocr**
Zaktualizować `pyproject.toml`, usuwając linię `easyocr>=1.7.2` i dodając `rapidocr-onnxruntime>=1.4.0` oraz `winocr>=0.0.15`.

**Step 2: Uruchomienie synchronizacji uv**
Uruchomić `uv sync --extra dev` i zweryfikować, że pakiety PyTorch nie są już wymagane w drzewie zależności.

---

### Task 2: Przepisanie silnika OCR (mvp/bot/ocr.py)

**Files:**
- Modify: `mvp/bot/ocr.py`
- Test: `mvp/tests/test_ocr.py`

**Step 1: Implementacja FastChatOCR z hybrydą WinOCR + RapidOCR**
- Zaimplementować bezpieczną inicjalizację WinOCR z automatyczną detekcją języka i tolerancją na słowniki systemowe.
- Dodać fallback na RapidOCR w przypadku braku wsparcia Windows.Media.Ocr lub specyficznych znaków.
- Zaimplementować metody: `find_helicopter_alert`, `is_alliance_chat_open`, `is_chat_window_open`, `is_details_dialog_open`.

**Step 2: Implementacja FastTimerOCR z RapidOCR Recognition-Only**
- Zaimplementować wycinanie paska timera z filtrem HSV white-mask.
- Zastosować `RapidOCR(use_det=False, use_cls=False)` bezpośrednio na wycinku cyfr (czas wykonania ~39 ms).
- Zachować `_parse_time` z pełną obsługą `HH:MM:SS` i `MM:SS`.

**Step 3: Uruchomienie testów jednostkowych**
Run: `uv run pytest mvp/tests/test_ocr.py -v`
Expected: PASS

---

### Task 3: Optymalizacja pętli startowej bota (mvp/bot/runner.py)

**Files:**
- Modify: `mvp/bot/runner.py`

**Step 1: Usunięcie blokującego prewarmu PyTorch**
- Usunąć `ocr_prewarm.join(timeout=35)`.
- Zastąpić lekkim, nieblokującym prewarmem modeli ONNX/WinOCR (trwającym poniżej 300 ms).

---

### Task 4: Oczyszczenie instalatorów i skryptów budowania (mvp/build/)

**Files:**
- Modify: `mvp/build/build.ps1`
- Modify: `mvp/build/fetch-vendor.ps1`
- Modify: `mvp/build/health-check.ps1`
- Modify: `mvp/build/installer.iss`

**Step 1: Usunięcie pobierania i pakowania wag EasyOCR**
- Usunąć pobieranie archiwów `craft_mlt_25k.zip` i `english_g2.zip`.
- Usunąć zmienną `EASYOCR_MODULE_PATH` i sekcje kopiowania modeli PyTorch.

---

### Task 5: Weryfikacja całościowa i pomiary latencji

**Files:**
- Test: Cała suita testów bota: `uv run pytest -m "not slow"`
- Benchmark: `uv run python scripts/benchmark_ocr_candidates.py`

**Step 1: Potwierdzenie latencji i poprawności**
- Upewnić się, że czas odczytu czatu wynosi poniżej 20 ms.
- Upewnić się, że czas odczytu timera wynosi poniżej 45 ms.
- Potwierdzić brak regresji w zachowaniu makra.
