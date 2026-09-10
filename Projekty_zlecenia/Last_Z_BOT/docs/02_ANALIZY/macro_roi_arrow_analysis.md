# Analiza i Debugowanie ROI Makra oraz Detekcji Strzałki Czatu

**Data:** 2026-09-04  
**Plik testowy:** `data/macro_testing/1_scan_chat_with_arrow.png` (rozmiar: $1923 \times 1075\text{ px}$)  
**Komponenty:** [`mvp/macro_def.py`](file:///f:/PROJEKTY/joaxx/mvp/macro_def.py), [`mvp/bot/arrow_detector.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/arrow_detector.py), [`mvp/bot/coordinates.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/coordinates.py), [`mvp/bot/ocr.py`](file:///f:/PROJEKTY/joaxx/mvp/bot/ocr.py)

---

## 1. Analiza ROI dla Strzałki Czatu (`_ROI_CHAT_ARROW`)

### Parametry Definicji
- **Procenty:** `left = 58.0%`, `top = 81.5%`, `right = 63.5%`, `bottom = 92.0%`, `anchor = "center"`
- **Rozdzielczość testowa:** $1923 \times 1075\text{ px}$

### Przeliczenie Współrzędnych na Piksele Klatki
1. **Z uwzględnieniem `WindowContext.roi_to_frame_pixels` (z korektą kalibracyjną `calib_y_to_client_fraction`):**
   - $X_{\text{left}} = 1114\text{ px}$
   - $Y_{\text{top}} = 870\text{ px}$
   - $X_{\text{right}} = 1220\text{ px}$
   - $Y_{\text{bottom}} = 986\text{ px}$
   - **Wymiary ROI:** $106 \times 116\text{ px}$

2. **Pozycja Ground Truth wykrytej strzałki w `1_scan_chat_with_arrow.png`:**
   - Środek: **$(X = 1176, Y = 937)$**
   - Marginesy od krawędzi ROI:
     - Od lewej ($1114$): $+62\text{ px}$
     - Do prawej ($1220$): $-44\text{ px}$
     - Od góry ($870$): $+67\text{ px}$
     - Do dołu ($986$): $-49\text{ px}$
   - Strzałka znajduje się **niemal idealnie w centrum wyznaczonego okna ROI**.
   - Wskaźnik dopasowania szablonu (`TM_SQDIFF_NORMED` z maską alfa): **$\text{score} = 0.9725$** (znacznie powyżej domyślnego progu $0.88 - 0.92$).

3. **Weryfikacja Negatywna (`1_scan_chat_without_arrow.png`):**
   - Po przewinięciu czatu na dół (brak nowej nieprzeczytanej wiadomości ze strzałką) detektor zwraca **`None`**.
   - Brak fałszywych detekcji ($0\text{ false positives}$).

---

## 2. Analiza Pozostałych ROI Makra Helikoptera

| Krok / Nazwa ROI | Definicja (%) | Wycinek klatki ($1923 \times 1075$) | Skuteczność detekcji |
|---|---|---|---|
| `_ROI_SCROLL_LISTEN` | L: 38.2, T: 20.2, R: 61.7, B: 91.0 (center) | `[733, 193, 1185, 980]` ($452 \times 787\text{ px}$) | **Wykryto alert:** `[Stałe 751 X:474 Y:50]`, punkt kliknięcia: $(116.0, 198.5)$ |
| `_ROI_ALLIANCE_TAB` (stary) | L: 48.0, T: 7.9, R: 51.8, B: 11.9 (center) | `[923, 56, 996, 100]` ($73 \times 44\text{ px}$) | Obcinał prawą krawędź napisu (R: 996 vs litera 'e': 997), score: $0.946$ |
| `_ROI_ALLIANCE_TAB` (nowy) | L: 47.6, T: 8.2, R: 52.4, B: 12.2 (center) | `[916, 59, 1007, 104]` ($91 \times 45\text{ px}$) | **Idealne wycentrowanie:** marginesy $+14\text{ px}$ / $+10\text{ px}$ / $+17\text{ px}$ / $+9\text{ px}$, score: **$0.959$**, `is_alliance_chat_open = True` |
| `_ROI_CHAT_ARROW` | L: 58.0, T: 81.5, R: 63.5, B: 92.0 (center) | `[1114, 870, 1220, 986]` ($106 \times 116\text{ px}$) | **Wykryto strzałkę:** $(1176, 937)$, score: $0.9725$ |
| `_ROI_DETAILS_HEADER` | L: 44.0, T: 16.0, R: 56.0, B: 21.5 (center) | Na `details.png`: `[850, 138, 1068, 196]` | **Wykryto dialog:** `is_details_dialog_open = True` |
| `_ROI_TIMER` | L: 45.0, T: 16.5, R: 55.0, B: 22.5 | Na `timer_debug.png`: RapidOCR poprawnie czyta czas $5\text{s}$ | **Timer OCR OK** |

---

## 3. Kluczowe Wnioski Architektoniczne
- Wycinek `WindowContext.roi_to_frame_pixels` z `calib_y_to_client_fraction` jest **wymagany** dla `_ROI_ALLIANCE_TAB`, ponieważ nagłówek czatu znajduje się w samej górnej części okna i bez kompensacji paska tytułowego wycinek przesunąłby się o 28 px poniżej tekstu `Alliance` / `Sojusz`.
- Dla `_ROI_CHAT_ARROW` obie metody (`to_pixels` oraz `WindowContext.roi_to_frame_pixels`) prawidłowo obejmują strzałkę (różnica wynosi jedynie 6 px w osi Y: $870-986$ vs $876-989$).
