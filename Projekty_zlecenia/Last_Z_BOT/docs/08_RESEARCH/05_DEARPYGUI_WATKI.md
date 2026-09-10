# Research — DearPyGui i bezpieczeństwo wątkowe

## Kontekst (co wiemy, bez wnioskowania)
- Aplikacja używa DearPyGui (DPG) jako GUI.
- Kod wywołuje `dpg.set_value()` z wątku bota (nie z wątku GUI).
- Zgłaszane są zawieszenia aplikacji.

## Pytanie badawcze (otwarte)
Jak bezpiecznie aktualizować widżety DearPyGui z wątków roboczych, i jakie są realne konsekwencje wywoływania funkcji DPG spoza głównego wątku (crash, wyścig, undefined behavior)?

## Czego szukać (bez zakładania odpowiedzi)
- Czy DearPyGui jest udokumentowane jako thread-safe, czy wymaga zewnętrznej synchronizacji.
- Jakie są polecane wzorce: kolejka komunikatów + timer w pętli GUI, lock, czy coś innego.
- Czy są znane crash'e (np. konkretny kod błędu) związane z wywołaniem z innego wątku.
- Jak inni rozwiązują to w aplikacjach DPG o podobnej architekturze.

## Uwaga metodologiczna
Zbierz fakty o bezpieczeństwie wątkowym DPG, nie zakładaj że jedna kolejka jest jedynym rozwiązaniem. Podaj co jest oficjalnie wspierane, a co to tylko community workaround.