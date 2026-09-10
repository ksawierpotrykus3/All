# Research — przechwytywanie ekranu DXGI na różnym sprzęcie

## Kontekst (co wiemy, bez wnioskowania)
- Aplikacja używa DXCam (DXGI Desktop Duplication) do przechwytywania obszaru ekranu (bot/capture.py:9,64; log wewnętrznego komponentu dxgi_duplicator w linii 15).
- Format kolorów jest ustawiony na BGR przy tworzeniu kamery (capture.py:64) i zakładany w przetwarzaniu: cv2.COLOR_BGR2HSV (bot/ocr.py:367) oraz detekcja strzałki zakłada kolejność BGR (bot/arrow_detector.py:66,141).
- Wywołanie grab() przyjmuje tylko parametr region, bez timeoutu (capture.py:77).
- W kodzie nie ma obsługi HDR ani wyboru adaptera GPU; jest jedynie wybór wyjścia/monitora przez output_idx (capture.py:36,62,203-207).

## Pytanie badawcze (otwarte)
Jakie są realne przyczyny czarnego ekranu, zamiany kanałów kolorów lub zawieszenia przy DXGI Desktop Duplication na różnych konfiguracjach (zintegrowane+dedykowane GPU, HDR, różne tryby okna), i jakie są sprawdzone sposoby radzenia sobie z tym (fallback na inne API, wykrywanie formatu kolorów, wybór adaptera)?

## Czego szukać (bez zakładania odpowiedzi)
- Czy DXGI Duplication zawsze zwraca konkretny format kolorów, czy zależy od sterownika; jak to wykryć w kodzie.
- Jak Hardware-Accelerated GPU Scheduling (HAGS) i multi-GPU wpływają na DuplicateOutput; jak wymusić konkretny adapter.
- Fallback: Windows.Graphics.Capture vs GDI BitBlt — kiedy które ma sens, wady i zalety.
- Jak bezpiecznie robić grab() z timeoutem, żeby uniknąć zawieszenia wątku.

## Uwaga metodologiczna
Zbierz przyczyny i rozwiązania dla kilku konfiguracji, nie zakładaj że jedna kaskada fallback jest jedyną drogą. Podaj też, co jest realnie testowalne bez fizycznego dostępu do sprzętu.