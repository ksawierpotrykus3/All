# Test 04 – AI #1: Selekcja ofert

## Status: 🔴 nie rozpoczęty
## Data: -

## Cel
Wysłać listę ofert do DeepSeek V4 Pro i sprawdzić selekcję.

## Kroki
1. Sprawdzić połączenie z `http://localhost:4570/v1`
2. Załadować prompt z pliku `prompt_ai1.md` (lub użyć testowego)
3. Wysłać listę ofert (z testu 02) + prompt
4. Odebrać i sprawdzić odpowiedź

## Oczekiwany wynik
```json
{
  "selected": [
    {"title": "...", "reason": "pasuje - Python, web scraping"},
    {"title": "...", "reason": "pasuje - AI, automatyzacja"}
  ],
  "rejected": [
    {"title": "...", "reason": "nie pasuje - technologie, budżet"}
  ],
  "total_time_ms": 5000
}
```

## Wyniki
*(do uzupełnienia po teście)*