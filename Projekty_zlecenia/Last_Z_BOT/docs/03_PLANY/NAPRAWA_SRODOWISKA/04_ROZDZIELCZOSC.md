# Fix 4: Rozdzielczość ≠ 1920x1080

## Problem
W wielu miejscach są hardcoded wartości zakładające rozdzielczość 1920x1080:
- `mvp/bot/coordinates.py:54-68` — `_CALIB_CLIENT_H = 1080.0`, `1920.0`
- `mvp/bot/arrow_detector.py:107` — `base_scale = fh / 1075.0`
- `mvp/bot/ocr.py:96-97` — `min_confidence = 0.3` (niższa rozdzielczość → niższe konfidencje)

Przy innej rozdzielczości ROI są przesunięte, a alerty niewykrywane.

## Rozwiązanie
1. Zastąpić hardcoded wymiary dynamicznym rozmiarem okna z faktycznego `GetClientRect`
2. Dostosować próg konfidencji OCR do rozdzielczości (albo przeskalować obraz przed OCR)

## Kroki
- [ ] Znaleźć wszystkie hardcoded 1080/1075/1920
- [ ] Zastąpić dynamicznymi wartościami
- [ ] Test na 1600x900 i 1280x720