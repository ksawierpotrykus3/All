# Research — Windows locale, kodowanie i separatory dziesiętne w Pythonie

## Kontekst (co wiemy, bez wnioskowania)
- Aplikacja przetwarza tekst z OCR (współrzędne, licznik czasu) — parsowanie liczb z tekstu.
- Logi zapisywane są przez RotatingFileHandler z jawnie ustawionym `encoding="utf-8"` (logging_setup.py:38).
- Użytkownicy końcowi będą na różnych wersjach językowych Windowsa (polski, niemiecki, inne).

## Pytanie badawcze (otwarte)
Jak ustawienia regionalne Windowsa (separator dziesiętny, kodowanie domyślne konsoli/strumieni, ścieżki z niestandardowymi znakami) wpływają na aplikacje Python, które parsują liczby z tekstu i zapisują pliki, i jakie są sprawdzone sposoby, żeby aplikacja działała niezależnie od locale?

## Czego szukać (bez zakładania odpowiedzi)
- Jak separator dziesiętny zależny od locale wpływa na parsowanie float i jak to uniezależnić (np. czy `locale.setlocale(LC_ALL, 'C')` jest właściwe, czy są lepsze podejścia).
- Czy jawne `encoding="utf-8"` na handlerach plików wystarcza, czy trzeba też ustawiać kodowanie strumieni stdout/stderr.
- Jak obsłużyć ścieżki z polskimi/niemieckimi znakami w aplikacji budowanej Nuitka.

## Uwaga metodologiczna
Zbierz konkretne przypadki awarii i rozwiązania, nie zakładaj że jedna linijka `PYTHONUTF8=1` załatwia wszystko. Podaj które biblioteki (cv2, torch, dearpygui) wymagają szczególnej uwagi.