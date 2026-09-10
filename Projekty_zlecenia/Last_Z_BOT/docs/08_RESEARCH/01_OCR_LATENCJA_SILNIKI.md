> UWAGA: Sekcje 1–6 opisują stan SPRZED migracji (EasyOCR/Tesseract). Sekcja 7 dokumentuje aktualne wdrożenie WinOCR + RapidOCR.

# Research — silniki OCR i latencja w aplikacji desktop real-time (Last Z Bot)

## 1. Stan faktyczny w kodzie `@mvp`

- **Architektura OCR w MVP**:
  - `ChatOCR` (`mvp/bot/ocr.py`): Wykrywanie komunikatów o zrzutach z helikoptera ("Explore", "State XXX X:YYY Y:ZZZ") oraz weryfikacja otwarcia zakładek czatu ("Allia", "Sojusz", "Details").
  - `TimerOCR` (`mvp/bot/ocr.py`): Odczyt timera spadku skrzynki (`HH:MM:SS` lub `MM:SS`) z wycinka klatki.
  - Implementacja oparta na **EasyOCR** w trybie CPU:
    ```python
    torch.set_num_threads(1)
    _shared_reader = easyocr.Reader(["en"], gpu=False)
    ```
  - `TimerOCR` wykonuje kaskadowy fallback (do 4 przejść: maska HSV white-mask 3x upscale -> EasyOCR 2x upscale -> Tesseract -> EasyOCR 4x upscale).
  - `runner.py` posiada dedykowany mechanizm prewarm z timeoutem aż do **35 sekund** (`ocr_prewarm.join(timeout=35)`), blokujący start pętli głównej bota na czas ładowania modeli PyTorch.

## 2. Pomiary wydajności EasyOCR na maszynie lokalnej (Benchmark 2026-09-03)

Test wykonany bezpośrednio w środowisku projektu (`uv run python`) na cropie `helka3`:
- **Czas inicjalizacji modeli (PyTorch CRAFT + CRNN)**: **19 636.9 ms (~19.6 s)**
- **Czas pojedynczego odczytu (mały crop timera, 1 udane przejście)**: **1 092.3 ms (~1.1 s)**
- **Przy nieudanym pierwszym podejściu**: do 3-4 przejść EasyOCR = **2.5 – 4.0 sekundy** całkowitego zablokowania wątku makra!

## 3. Dlaczego EasyOCR NIE jest optymalny dla bota gry

1. **Drastyczne opóźnienie w czasie rzeczywistym**:
   Gra działa w 60 FPS (klatka trwa 16.6 ms). Czas odczytu 1100 ms to pominięcie ponad 66 klatek gry. W fazie krytycznej przed zrzutem skrzynki ($T_0$) spóźnienie o 1 sekundę oznacza przegraną walkę o skrzynkę z innymi graczami.
2. **Narzut pamięciowy i rozmiarowy**:
   - PyTorch (`torch` + `torchvision`) to **~2.5 GB** na dysku w środowisku deweloperskim i ogromny narzut na instalator (InnoSetup / Nuitka).
   - Wagi modeli CRAFT (`craft_mlt_25k.zip`) i CRNN (`english_g2.zip`) to kolejne dziesiątki megabajtów wymagające zewnętrznego pobierania skryptem `fetch-vendor.ps1`.
   - Ładowanie PyTorcha pochłania 600–1200 MB pamięci RAM.
3. **Single-thread bottleneck**:
   `torch.set_num_threads(1)` zabezpiecza przed zjadaniem 100% wszystkich rdzeni CPU, ale powoduje, że pojedynczy rdzeń jest obciążony w 100% przez ponad sekundę na każdy odczyt.

---

## 4. Zbadane alternatywy (Porównanie technologiczne)

| Silnik | Architektura | Czas Inicjalizacji | Latencja na CPU (crop timera) | Latencja (tekst czatu) | Waga zależności | Modele / Wagi |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EasyOCR** (obecny) | PyTorch (CRAFT + CRNN) | **~19 600 ms** | **~1 090 ms** | **~1 400 - 2 200 ms** | **~2 500 MB** (PyTorch) | ~120 MB |
| **RapidOCR** (PP-OCR v4) | ONNX Runtime (C++) | **~150 - 300 ms** | **~15 - 35 ms** | **~50 - 90 ms** | **~25 MB** (onnxruntime) | ~12 MB |
| **Windows.Media.Ocr** (WinRT) | Natywne WinRT / Windows 10/11 | **~50 - 100 ms** | **~10 - 25 ms** | **~40 - 80 ms** | **0 MB** (wbudowane w OS) | 0 MB (w systemie) |
| **OpenCV Template Matching** | `cv2.matchTemplate` (cyfry) | **< 1 ms** | **~0.5 - 2.0 ms** | *Nie dotyczy* (tylko cyfry) | **0 MB** (OpenCV już w projekcie) | Kilka PNG (szablony) |

---

## 5. Wyniki testów bezpośrednich na plikach gry (Benchmark 2026-09-03)

Testy wykonano na rzeczywistych zrzutach z gry z katalogu `data/macro_testing/`:

### A. Detekcja Zakładki Sojuszu / Czatu (`1_scan_chat_with_arrow.png` & `1_scan_chat_without_arrow.png`)
- **WinOCR (Windows.Media.Ocr)**: **13.5 ms – 14.2 ms** (Wykryto poprawnie `Alliance`). Przyspieszenie **~100x** względem EasyOCR!
- **EasyOCR**: **1047 ms – 1804 ms**. Halucynacje: `Jew` zamiast `New`, `(orld` zamiast `World`.
- **RapidOCR**: Bezbłędna jakość tekstu (`New`, `Duel`, `World`, `Alliance`, `Friend Post`), ale wyższa latencja przy pełnej detekcji DBNet.

### B. Alert Helikoptera w Czacie (`1_heli_alert_appearing_in_chat.png`)
- **WinOCR**: **17.1 ms** $\to$ odczytano `'Stałe 742 X:528 Y:482'`. Błyskawiczna ekstrakcja kordów w 17 ms! (W polskim systemie Windows słownik podmienia `State` na `Stałe`, co wymaga tolerancji w regexie `r"Sta[teł]+"`).
- **RapidOCR**: **~180 ms** (w trybie zoptymalizowanym) $\to$ bezbłędny odczyt po angielsku: `Explore`, `Treasure`, `State742X:528`, `BY:482`.
- **EasyOCR**: **1740.1 ms** $\to$ odczytano z błędem litery Y (`'State 742 X528 Vi482'`).

### C. Timer Skrzynki (`helka_scrolled.png` — oczekiwane `00:00:05`)
- **RapidOCR (Recognition-only: `use_det=False, use_cls=False`)**: **39.0 ms**!
  - Wynik: `[['00:00:05', 0.9878]]` (pewność 98.8%).
  - Przyspieszenie: **57x szybciej niż EasyOCR** (z 2216 ms do 39 ms)!
- **EasyOCR**: **2216.4 ms** (ponad 2.2 sekundy zamrożenia bota).

---

---

## 7. Wyniki produkcyjne po wdrożeniu Fast OCR (2026-09-03)

Wdrożenie nowego hybrydowego silnika OCR (WinOCR + RapidOCR ONNX Runtime) zakończyło się pełnym sukcesem. Z projektu **całkowicie usunięto biblioteki PyTorch, Torchvision oraz EasyOCR** (oszczędność ~2.5 GB na dysku i kilkuset MB RAM).

### Twarde pomiary z benchmarku (`scripts/benchmark_ocr_candidates.py`):
- **Weryfikacja zakładki Sojuszu / Czatu**:
  - **FastOCR (WinOCR)**: **14.5 ms** (vs EasyOCR: **1047–1804 ms**) $\to$ **~100x szybciej**.
- **Wykrycie alertu helikoptera w czacie**:
  - **FastOCR (WinOCR/RapidOCR)**: **18.7 ms** (odczytano: `State 742 X:528 Y:482`) $\to$ średnia z 5 wywołań: **43.2 ms** (vs EasyOCR: **1740 ms**) $\to$ **~40–90x szybciej**.
- **Odczyt timera skrzynki (`00:00:05`)**:
  - **FastOCR (RapidOCR Recognition-Only)**: **32.3 ms** (vs EasyOCR: **2216 ms**) $\to$ **~70x szybciej**.
- **Stabilność i testy**:
  - Wszystkie 65 testów silnika makr (`mvp/tests/test_macro_engine.py`) oraz 23 testy OCR (`mvp/tests/test_ocr.py`) przechodzą w 100%.
  - Wyeliminowano błędy zawieszania pętli czasu na granicy floatów (zabezpieczenie `0.001s`) oraz countdown lock w fazie FAST.