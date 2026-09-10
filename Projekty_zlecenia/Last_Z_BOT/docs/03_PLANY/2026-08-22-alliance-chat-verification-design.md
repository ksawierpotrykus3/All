> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Weryfikacja czatu Alliance i obsluga retry w makrze helikoptera (MVP)

Data: 2026-08-22
Moduly: mvp/ (mvp/bot/ocr.py, mvp/bot/macro_engine.py, mvp/macro_def.py, mvp/tests/*)

## 1. Cel i kontekst

W makrze helikoptera wystepuja dwa kluczowe momenty przejscia interfejsu (UI transitions):
1. Wejscie do czatu sojuszu (Krok 1: SCROLL_LISTEN_CHAT): klik dolnego paska i zakladki Alliance -> weryfikacja OCR obecnosci napisu Alliance i ewentualny retry.
2. Wyjscie z czatu po kliknieciu alertu (Krok 2: CLICK na koordynaty helikoptera): weryfikacja czy napis Alliance zniknal -> jesli nie, powrot do Kroku 1 i ponowne skanowanie.

## 2. Architektura i komponenty

### A. Rozpoznawanie OCR (mvp/bot/ocr.py)
- Metoda is_alliance_chat_open(self, image: np.ndarray, min_confidence: float = 0.3) -> bool
- Wykorzystuje EasyOCR do sprawdzenia slowa kluczowego Alliance w ROI zakladki.

### B. Silnik makra (mvp/bot/macro_engine.py)
- Petla wejscia w _handle_scroll_listen_chat z max_open_retries (domyslnie 3).
- Weryfikacja wyjscia z czatu w petli MacroEngine.run po Kroku 2; powrot do Kroku 1 w razie nieudanego wyjscia.

### C. Definicja makra (mvp/macro_def.py)
- Flagi verify_alliance_open oraz verify_chat_exit i alliance_tab_roi w krokach makra.

## 3. Plan testow (TDD)
- Testy jednostkowe w mvp/tests/test_ocr.py oraz mvp/tests/test_macro_engine.py.
