# Test 06 – Pełny flow (integracja)

## Status: 🔴 nie rozpoczęty (zależny od testów 01-05)
## Data: -

## Cel
Przeprowadzić cały proces od początku do końca (bez faktycznej wysyłki).

## Kroki
1. Wejść na 2 linki kategorii, pobrać listy ofert
2. Użyć markera do odfiltrowania nowych
3. Puścić AI #1 do selekcji
4. Dla wybranych: Playwright klika w oferty → "pokaż pełny opis" → pobiera dane
5. Puścić AI #2 dla każdej oferty → generuje propozycje
6. Wyświetlić wyniki do weryfikacji (bez wysyłki)

## Oczekiwany wynik
- Cały proces przechodzi bez błędów
- Czas całkowity akceptowalny (< 5 minut dla 2-3 ofert)
- Dane poprawnie przepływają między etapami

## Wyniki
*(do uzupełnienia po teście)*