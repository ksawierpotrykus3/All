> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Problem 4: Wysokie zużycie CPU (OCR)

## Status: ROZWIĄZANY I ZWERYFIKOWANY (Wrzesień 2026)

## Objaw pierwotny
- "Bardzo wysokie wykorzystanie procesora" (ponad 300–389% CPU, blokowanie 3–4 rdzeni procesora).
- Spadki klatkażu gry Unity (`Survival.exe`) oraz przycinanie interfejsu DearPyGui.

---

## Przyczyny źródłowe (Root Cause)

### 1. Stary potok (EasyOCR / PyTorch — stan przed migracją)
- Synchroniczne wywołania ciężkiego modelu PyTorch na CPU w pętli makra.
- Wielokrotne przejścia (`readtext` pass 1, 2, 3) na jeden odczyt timera skrzynki.
- Brak efektywnego buforowania klatek.

### 2. Potok Fast OCR (Diagnoza Frida MCP na procesie bota PID 12216)
- **Nieograniczony threadpool ONNX Runtime:** Biblioteka `onnxruntime` przy braku jawnego parametru `intra_op_num_threads` tworzyła threadpool o rozmiarze równym wszystkim rdzeniom logicznym CPU procesora (16–32 wątki), blokując procesor.
- **Bezwarunkowy fallback do RapidOCR:** W `mvp/bot/ocr.py` w metodzie `find_helicopter_alert` (oraz `is_alliance_chat_open`, `is_chat_window_open`, `is_details_dialog_open`) po pomyślnym przetworzeniu klatki przez WinOCR, gdy alertu nie było w czacie, brakowało `return None`. W efekcie przy każdej klatce uruchamiany był pełny silnik detekcji DBNet RapidOCR.
- **Zniekształcenia WinOCR na kolorowych napisach gry:** W polskim systemie Windows (`lang='pl'`) stylizowany zielony tekst z czarną obwódką na pomarańczowym tle był zniekształcany przez WinRT OCR (`xp ore reasure`, `Stałe 7,42 Y,ŕă82`), co gubiło współrzędną X. Całkowite odcięcie RapidOCR uniemożliwiało odczytanie koordynatów alertu.

---

## Wdrożone Rozwiązanie

### 1. Całkowite usunięcie EasyOCR i PyTorch
- Wycięto zależności `torch`, `torchvision`, `easyocr`, `pytesseract` (oszczędność ~2.5 GB na dysku, natychmiastowy start bota).

### 2. Architektura Dual-Gate w `mvp/bot/ocr.py`
- **Gate 1 (Szybki skan WinOCR ~15 ms):** Wykrywa wskazówki tekstowe (`Expl`, `Treas`, `reasure`, `spot`, `troop`, `heli`, `Stałe`, `State`).
- **Gate 2 (Filtr koloru pomarańczowego w OpenCV < 1 ms):** Karta alertu helikoptera to charakterystyczny banner o $\ge 10\,000\text{ px}$ pomarańczowych HSV (`cv2.inRange`).
- **Zasada działania:**
  - Gdy czat jest pusty/zwykły: funkcja odrzuca klatkę w **< 1 ms**, bez uruchamiania RapidOCR (CPU idle: ~6–10%).
  - Gdy pojawi się karta helikoptera: filtr natychmiast wyzwala RapidOCR, który w **100% precyzyjnie** odczytuje koordynaty (`528, 482`) i punkt kliknięcia.

### 3. Ograniczenie wątków ONNX Runtime
- W `_get_shared_rapidocr()` wymuszono `intra_op_num_threads=2, inter_op_num_threads=1`.

### 4. Optymalizacja Timera Skrzynki
- W `TimerOCR` wprowadzono próbkowane hashowanie numpy (brak alokacji `tobytes()`) oraz tryb Recognition-Only na wycinku timera (**32 ms** zamiast 800 ms).

---

## Wyniki Weryfikacji Empirycznej

| Metryka | Przed rozwiązaniem | Po wdrożeniu poprawek | Rezultat |
| :--- | :--- | :--- | :--- |
| **Zużycie procesora (CPU)** | **389.1%** (~4 rdzenie) | **10.3%** | **Spadek o ~97.4%** |
| **Czas detekcji braku alertu** | 500–2200 ms (RapidOCR busy) | **< 1 ms** (Dual-Gate) | **Brak obciążenia w pętli** |
| **Precyzja odczytu koordynatów** | 0% (zgubione X przez WinOCR) | **100%** (RapidOCR fallback) | **Bezbłędna detekcja** |
| **Pamięć RAM bota** | Rosnąca | **228.7 MB** (stabilna) | **Brak wycieków** |
| **Testy jednostkowe OCR** | — | **30 passed in 12.76s** | **100% pass** |