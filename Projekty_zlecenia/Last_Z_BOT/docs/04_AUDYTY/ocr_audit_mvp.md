> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Audyt wydajności modułu OCR (MVP) — timer i czat

Data pomiaru: 2026-08-22
Środowisko: Windows, CPU-only PyTorch 2.13.0+cpu, EasyOCR 1.7.2, OpenCV 4.x,
8 rdzeni CPU, `torch.get_num_threads()=4`.

---

## 1. Zakres

Pomiar objął moduł [`mvp/bot/ocr.py`](../../mvp/bot/ocr.py) w dwóch scenariuszach
użycia przez silnik makra [`mvp/bot/macro_engine.py`](../../mvp/bot/macro_engine.py):

- **Czat** — `ChatOCR.find_helicopter_alert()` (krok `SCROLL_LISTEN_CHAT`,
  pętla nasłuchu z auto-strzałką) oraz `ChatOCR.is_alliance_chat_open()`.
- **Timer** — `TimerOCR.read_timer()` (krok `WATCH_TIMER`, faza `idle`/`fast`).

Obrazy testowe:

| Plik | Rozmiar | Rola |
|---|---|---|
| `data/images/analysis/chat.png` | 1923×1075 | czat (pełna klatka) |
| `data/images/analysis/helka_scrolled.png` | 1920×1080 | timer po zoomie (crop 66×192) |
| `data/images/analysis/helka3.png` | 1921×1080 | timer z nakładką nazw graczy (crop 66×192) |

ROI użyte do cropów pochodzą z [`mvp/macro_def.py`](../../mvp/macro_def.py):
`_ROI_SCROLL_LISTEN` (38.2–61.7% × 20.2–91.0%), `_ROI_TIMER` (45.0–55.0% × 16.5–22.5%),
`_ROI_ALLIANCE_TAB` (48.0–51.8% × 7.9–11.9%).

---

## 2. Oryginalne czasy wykonania

Każdy wiersz = czas jednego wywołania OCR (mediana z 2–3 prób; `min`/`max`
obok). Inicjalizacja readera EasyOCR zmierzona raz.

| Operacja | Median | Min | Max |
|---|---|---|---|
| **Inicjalizacja readera EasyOCR (lazy, jednorazowo)** | **9 082 ms** | 9 082 | 9 082 |
| `find_helicopter_alert` — PEŁNA klatka 1923×1075 | 16 389 ms | 15 877 | 16 901 |
| `find_helicopter_alert` — crop SCROLL_LISTEN 783×452 | 4 598 ms | 4 573 | 4 714 |
| `is_alliance_chat_open` — crop ALLIANCE_TAB 44×73 | 112 ms | 109 | 118 |
| `read_timer` scrolled (66×192), upscale=8, max_passes=2 | 1 381 ms | 1 369 | 1 398 |
| `read_timer` scrolled (66×192), upscale=8, max_passes=4 | 1 373 ms | 1 361 | 1 385 |
| `read_timer` **helka3** (66×192), upscale=8, max_passes=2 | **6 469 ms** | 6 401 | 6 537 |
| `read_timer` scrolled, upscale=2, max_passes=2 | 1 583 ms | 1 416 | 1 750 |
| `read_timer` helka3, upscale=2, max_passes=2 | 1 728 ms | 1 721 | 1 735 |

Mikro-pomiary pojedynczych przebiegów wewnątrz `read_timer` (crop 66×192):

| Przebieg | Median |
|---|---|
| Pass 1 white-mask (maska HSV + upscale **4x** + readtext) | 1 394 ms |
| Sam `readtext` po upscale **8x** (=64x pikseli) | 4 973 ms |
| Sam `readtext` po upscale 4x (=16x pikseli) | 1 418 ms |
| Sam `readtext` po upscale 2x (=4x pikseli) | 560 ms |
| Tesseract `_tesseract_read` (wszystkie PSM, 7 wywołań) | 756 ms (max **8 961**) |

Mikro-pomiary czatu (crop 783×452):

| Wariant | Czas |
|---|---|
| EasyOCR domyślnie (`mag_ratio=1.5`) | 7 899 ms |
| `mag_ratio=1.0` | 5 832 ms |
| `mag_ratio=1.0` + `canvas_size=1600` | 5 173 ms |
| downscale 0.5x + domyślne | 3 825 ms |
| downscale 0.5x + `mag_ratio=1.0` | 4 005 ms |

Mikro-pomiary white-mask (crop 66×192) dla różnych faktorów upscale:

| Faktor upscale white-mask | Czas |
|---|---|
| 4x (obecny, stały w kodzie) | 1 613 ms |
| 3x | 924 ms |
| 2x | 550 ms |

> Uwaga: pomiary tej samej operacji w dwóch oddzielnych przebiegach skryptu
> (np. `find_helicopter_alert` crop: 4,6 s vs 7,9 s) różnią się nawet ~1,7x.
> To sygnatura **throttlingu CPU / braku determinizmu** — typowa dla EasyOCR
> na CPU (detektor CRAFT działa wieloskalowo, koszt zależy od zawartości).
> Wnioski opieram na wartościach względnych, a nie bezwzględnych.

---

## 3. Wąskie gardła

### B1. Inicjalizacja EasyOCR — ~9 s blokującego startu
`_get_shared_reader()` w [`ocr.py`](../../mvp/bot/ocr.py#L26-L34) tworzy readera
lazy przy pierwszym użyciu. Mimo współdzielenia obu klas (dobra decyzja — komentarz
w kodzie potwierdza oszczędność ~82 MB RAM) samo ładowanie CRAFT + recognizera
zajmuje ~9 s na CPU i blokuje pierwszy krok makra.

### B2. Czat: detekcja helikoptera — 4,6–7,9 s na iterację nasłuchu
`find_helicopter_alert()` wykonuje **jeden pełny przebieg EasyOCR** na całym
cropie czatu 783×452 px. Pętla nasłuchu w [`macro_engine.py`](../../mvp/bot/macro_engine.py#L738-L774)
ma `check_interval_s=0.7 s`, więc **każde skanowanie czatu trwa ~6–11x dłużej
niż interwał**. Przekłada się to wprost na opóźnienie reakcji na alert.

Źródło kosztu: EasyOCR domyślnie podnosi rozmiar (`mag_ratio=1.5`) wejścia dla
detektora CRAFT, a detektor działa w wielu skalach. Redukcja `mag_ratio` i/lub
downscale daje 1,5–2x przyspieszenia (sekcja 2). Pełna klatka (16,4 s) pokazuje,
czego unikamy dzięki cropowi — ale crop 783×452 to wciąż za dużo.

### B3. Timer: konfiguracyjny upscale=8 jest de facto „pass 2 = 8x”, nie „2x”
W [`runner.py`](../../mvp/bot/runner.py#L132-L138) `TimerOCR` dostaje
`upscale_factor=config.ocr_timer_upscale`, a domyślnie w [`config.py`](../../mvp/config.py#L60)
jest `ocr_timer_upscale=8`. Tymczasem komentarz w `read_timer` nazywa pass 2
„Raw 2x upscale”. Realnie pass 2 przeskalowuje **8x = 64x pikseli** — to
najdroższy pojedynczy przebieg (4,97 s, sekcja 2) i główna przyczyna tego, że
crop helka3 (z nakładką nazw graczy) kosztuje 6,5 s zamiast ~1,4 s jak scrolled.

Wniosek: **8x nie kupuje dokładności na cropie cyfrowego fontu 66×192**, a koszt
rośnie super-liniowo (up2=0,56 s → up4=1,42 s → up8=4,97 s).

### B4. Timer: white-mask pass ma „na sztywno” upscale 4x
Pass 1 w [`ocr.py`](../../mvp/bot/ocr.py#L329-L333) używa `factor=4` niezależnie
od konfiguracji. Faktor 3x daje 924 ms, 2x — 550 ms (44%/66% taniej). Wartości
konfiguracji (`ocr_timer_upscale`, `binarize_block`, `binarize_c`) **nie sterują
tym przebiegiem**.

### B5. Timer w fazie `fast`: budżet 0,1 s jest wielokrotnie przekraczany
W [`macro_engine.py`](../../mvp/bot/macro_engine.py#L1007-L1012) faza `fast`
ustawia `max_passes=2` (white-mask + pass-2). Ale już sam white-mask to ~1,4 s
(14x budżet `fast_check_interval_s=0.1 s`), a pass 2 przy upscale=8 to kolejne
~5 s. `_sleep_with_budget()` (audyt I8) skraca sen do zera, więc pętla faktycznie
mieli z częstotliwością **ograniczoną przez OCR (~1,4–6,5 s/iterację)**, nie przez
konfigurację. Reakcja `fast → spam` jest opóźniona o czas pojedynczego odczytu.

### B6. Timer: tesseract jako fallback ma wysoką wariancję
`_tesseract_read()` w [`ocr.py`](../../mvp/bot/ocr.py#L385-L438) próbuje do
**7 konfiguracji PSM** (whitelist 4 + no-whitelist 3). Median 756 ms, ale max
8,96 s — pojedyncze PSM z tesseractem to zwykle 100–200 ms. To potencjalnie
najtańszy czytnik timera, ale obecnie jest ostatni w kolejce i nadmiernie
rozbudowany (multi-PSM loop).

### B7. Wątek torch = 4 z 8 rdzeni
`torch.get_num_threads()` = 4 przy 8 dostępnych rdzeniach. Na CPU-only
niewykorzystane 4 rdzenie to ~zmarnowany potencjał równoległości inferencji.

---

## 4. Propozycje optymalizacji (plan implementacji)

Priorytet od największego zysku do najmniejszego. Po każdej zmianie **obowiązkowo**
uruchomić `uv run pytest tests/test_ocr.py -q` oraz `uv run pytest -m "not slow" -q`,
bo zmiany faktorów upscale mają wpływ na dokładność (testy `helka3`, `helka_scrolled`,
`helicopter_alert`).

### P1. Timer: zmień `ocr_timer_upscale` 8 → 2–3 i odłącz komentarz od faktów
- **Co:** ustaw domyślnie `ocr_timer_upscale: int = 2` w [`config.py`](../../mvp/config.py#L60)
  (lub 3) i zaktualizuj komentarz pass-2 w `read_timer` na „upscale self._upscale_factor”.
- **Dlaczego:** usuwa najdroższy przebieg 8x (4,97 s → 0,56–0,92 s); dokładność
  na cyfrowym foncie 66×192 nie powinna ucierpieć (white-mask up4 i tak czyta).
- **Szacunek:** `read_timer` scrolled z ~1,38 s → ~0,55–0,65 s (**≈ -55–60%**);
  helka3 z ~6,5 s → ~1,7 s (**≈ -74%**), bo znika patologiczny pass 8x.

### P2. Timer: white-mask pass — zrobić faktor konfigurowalny, domyślnie 3x
- **Co:** dodać parametr `white_mask_factor` do `TimerOCR` (dokładnie tak jak
  istniejące `upscale_factor`), podpiąć pod konfig (`ocr_timer_white_upscale=3`),
  zmienić stałe `factor=4` w [`ocr.py`](../../mvp/bot/ocr.py#L332).
- **Dlaczego:** pass 1 jest zawsze wykonywany jako pierwszy; 4x→3x to 1,39 s → 0,92 s.
- **Szacunek:** **≈ -34%** na każde wywołanie `read_timer` (gdy white-mask jest
  bezskuteczny, oszczędność natychmiastowa).

### P3. Czat: ogranicz `mag_ratio` i dodaj cap `canvas_size` (oraz lżejszy crop)
- **Co:** w `find_helicopter_alert` i `is_alliance_chat_open` wywoływać
  `readtext(..., mag_ratio=1.0, canvas_size=1600)` zamiast domyślnych.
  Dodatkowo w `_handle_scroll_listen_chat` przycinać `_ROI_SCROLL_LISTEN` do
  dolnej części czatu (najnowsze wiadomości, skąd algorytm i tak czyta od dołu)
  — np. `top: 55.0` zamiast `20.2`, i opcjonalnie downscale 0,5x przed OCR.
- **Dlaczego:** `mag_ratio=1.0 + canvas=1600` = 5,17 s vs 7,9 s domyślnie;
  mniejszy crop + downscale → kolejne ~2x. Detekcja skanuje od dołu do góry,
  więc górna część cropu to czysty narzut.
- **Szacunek:** 4,6–7,9 s → **~1,5–2,5 s** na iterację nasłuchu (**≈ -60–70%**).
  Reakcja na alert skraca się z ~5 s do ~1,5–2 s.

### P4. Timer w fazie `fast`: tesseract-first, EasyOCR jako fallback
- **Co:** gdy `phase == "fast"` (już mam `max_passes`), przełączyć kolejność:
  najpierw tani pass tesseract (pojedyncze PSM 7, whitelist `0123456789:`),
  dopiero potem white-mask EasyOCR. Zmienić `_tesseract_read` tak, by w trybie
  szybkim próbował **1 PSM**, nie 7.
- **Dlaczego:** tesseract na cyfrach to 100–200 ms, w granicach budżetu 0,1 s
  (rzędu wielkości), a EasyOCR white-mask to 0,9–1,4 s.
- **Szacunek:** odczyt w fazie fast z ~1,4 s → **~150–250 ms** (**≈ -85%**).

### P5. Wątek torch: jawne ustawienie liczby wątków
- **Co:** w `_get_shared_reader()` ustawić `torch.set_num_threads(os.cpu_count() or 4)`
  przed utworzeniem readera (lub tyle, ile rdzeni fizycznych).
- **Dlaczego:** 4 → 8 rdzeni może dać 1,3–1,8x na inferencji detektora.
- **Szacunek:** **≈ -20–40%** czasu `readtext` (bez zmiany dokładności).

### P6. (Długoterminowe, opcjonalne) Zamiana biblioteki OCR
- **RapidOCR (ONNXRuntime)** zamiast EasyOCR: detektor CRAFT/DB + recognizer
  PP-OCR w ONNX, **bez PyTorch**. Ta sama rola (lokalny OCR CPU), zwykle
  **5–20x szybszy** na CPU i ~10x mniejszy RAM. Ryzyko: zmiana dokładności na
  konkretnych fontach gry — wymaga przepisania obu klas i ponownej kalibracji
  progów conf.
- **Eksport CRAFT/recognizera EasyOCR do ONNX** — kompromis: te same modele,
  ale inferencja przez `onnxruntime` zamiast torch (bez rewolucji w pipeline).
- **Template matching dla timera** — wzorzec cyfr 0–9 (jak w `src/bot/ocr.py`
  `_template_match_digits`) czytający timer w ~1 ms; jako ostateczny fallback,
  ale wymaga kalibracji dokładnej pozycji.

### P7. (Drobne) Zmniejszenie narzutu inicjalizacji
- **Co:** wywoływać `initialize()` obu klas OCR w wątku startowym runnera
  (w tle), zamiast lazy przy pierwszym kroku makra; opcjonalnie równolegle
  ładować tesseract.
- **Dlaczego:** 9 s blokującego startu nie znika, ale przestaje opóźniać krok 1.
- **Szacunek:** UX startu, nie czas OCR (start „robi się ciepły” przed makrem).

---

## 5. Podsumowanie oczekiwanych zysków

| Opt. | Obszar | Stan obecny | Po wdrożeniu | Poprawa |
|---|---|---|---|---|
| P1 | timer pass-2 (8x→2x) | 1,38–6,47 s | 0,55–1,7 s | **-55…-74%** |
| P2 | timer white-mask (4x→3x) | 1,39 s | 0,92 s | **-34%** |
| P3 | czat (mag_ratio+crop) | 4,6–7,9 s | 1,5–2,5 s | **-60…-70%** |
| P4 | timer faza fast (tess-first) | ~1,4 s | 0,15–0,25 s | **-85%** |
| P5 | torch 8 wątków | — | — | **-20…-40%** (readtext) |
| P6 | RapidOCR zamiast EasyOCR | — | — | **-80…-95%** (wszystkie readtext) |

Łącznie P1–P5 redukują krytyczne ścieżki OCR z sekund do **setek milisekund**;
pełna wymiana na RapidOCR (P6) zeszłaby do **dziesiątek milisekund**, ale wymaga
osobnej walidacji dokładności na fontach gry.

## 6. Artefakty pomiaru

- Skrypt pomiarowy: `scripts/ocr_audit_bench.py` (pełny benchmark + eksport CSV)
- Skrypt mikro: `scripts/ocr_audit_bench2.py` (mag_ratio / downscale / white-mask)
- Wyniki: `data/images/analysis/ocr_audit_results.csv`

---

## 7. Status wdrożenia (2026-08-22)

Wdrożono **P1 + P2** (zamiast P4 — patrz uzasadnienie niżej).

| Zmiana | Pliki | Status |
|---|---|---|
| P1: `ocr_timer_upscale` 8→2 | `mvp/config.py`, `mvp/bot/ocr.py` (komentarz pass 2), testy config | ✅ |
| P2: white-mask konfigurowalny, default 3x (było sztywno 4x) | `mvp/config.py` (+walidacja), `mvp/bot/ocr.py`, `mvp/bot/runner.py`, `mvp/gui/main_window.py`, testy | ✅ |

**Dlaczego zamiast P4 (tesseract-first)?** Pomiar skuteczności po wstępnej analizie
obalił założenie P4 (tesseract „~100–200 ms"): `pytesseract` na Windows spawnuje
proces `tesseract.exe` na **każde** wywołanie, więc pojedyncze PSM kosztuje
**1,3–2,3 s** (psm 13 = 1,34 s z poprawnym wynikiem, psm 7/6/10 ≈ 2 s i puste),
a white-mask EasyOCR po optymalizacji P2 (up3) czyta ten sam crop w **0,85 s**.
Tesseract jest zatem **wolniejszy niż EasyOCR** w ścieżce timera — P4 nie daje zysku.

**Zweryfikowana poprawa (po P1+P2, rzeczywiste cropy):**

> `tests/fixtures/timer_crops/helka_scrolled.png` jest binarnie identyczny
> (MD5 `2d2b9702…`) z `data/images/analysis/helka_scrolled.png` i odpowiada
> **aktualnemu ROI timera w grze** — poniższe czasy dotyczą produkcyjnego regionu.

| Crop | Przed (up8/wm4) | Po (up2/wm3) | Zmiana |
|---|---|---|---|
| `helka_scrolled` fast (2 passy) | 1 380 ms | 1 196 ms | **-13%** |
| `helka_scrolled` full (4 passy) | 1 373 ms | 1 018 ms | **-26%** |
| `helka3` (nakładka nazw, fast) | 6 469 ms | 1 556 ms | **-76%** |
| `helka3` (nakładka nazw, full) | ~6 469 ms | 3 053 ms | **-53%** |

Dokładność bez regresji: white-mask up2/up3 czyta **wszystkie 4 fixture'y**
(`helka_crop`, `helka2_crop`, `helka3_00_11_18`, `helka_scrolled`) z poprawnymi
wartościami; crop `_ROI_TIMER` z pełnego `helka3.png` nie czytał się przy żadnym
upscale także przed zmianami (region zasłonięty nazwami graczy — nie-regresja).
Cała suita MVP: **695 passed**.

**Domknięcie po review:** zaktualizowano też produkcyjny `config.json`
(`ocr_timer_upscale` 8→2, dodano `ocr_timer_white_upscale=3`), `apply_config()`
propaguje czynniki upscale do `TimerOCR` na żywo (bez restartu bota) oraz dodano
testy propagacji przez `BotRunner`.

**P5 (wątek torch):** zmierzono realny zysk z `torch.set_num_threads()` na tej
maszynie (8 rdzeni): 4→8 wątków daje **~14%** (czat 10,4 s→8,95 s; white-mask
1,21 s→1,04 s) — mniej niż wstępne szacunki 20–40%. Wdrożone w
`_get_shared_reader()` (`os.cpu_count() or 4`).

**P3 (czat) — weryfikacja bezpieczeństwa:** przycinanie ROI i downscale 0.5x
**odrzucone** (karta alertu może być wyżej po przewinięciu; downscale łamie
detekcję — `state=False`). Bezpieczny wariant `mag_ratio=1.0 + canvas_size=1600`
czyta cały czat bez ubytku treści i daje -45% na fixture alertu (4187→2286 ms)
oraz -33% na pustym czacie (19,2 s→12,9 s) — **do wdrożenia**.

**P7 (pre-warm OCR):** wdrożone. Początkowo pre-warm ruszał dopiero w
`BotRunner.start()` — makro i tak czekało ~9–12 s, bo **pierwszy krok
(`_handle_scroll_listen_chat`) od razu wykonuje `_is_alliance_chat_open()`
(fast-check otwartego czatu), które blokuje na locku `_get_shared_reader()`**,
więc wątek makra czekał na init mimo pre-warmu w tle. Rozwiązanie: pre-warm
przeniesiony na **start aplikacji** — `main.py` woła `BotRunner.prewarm_ocr()`
(daemon) zanim pojawi się okno GUI; do czasu kliknięcia START reader jest
gotowy i makro wchodzi do chatu bez blokady. `start()` nadal wywołuje
idempotentny pre-warm jako pokrycie awaryjne.

Pozostałe rekomendacje do dalszych kroków: P3 (czat — bezpieczny wariant
`mag_ratio=1.0 + canvas_size=1600`, zysk -33…-45%) oraz P6 (RapidOCR/ONNX,
-80…-95%, wymaga re-kalibracji).