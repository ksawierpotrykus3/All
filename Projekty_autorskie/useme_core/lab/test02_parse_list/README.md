# Test 02 – Parsowanie listy ofert

## Status: 🔴 nie rozpoczęty
## Data: -

## Cel
Wyciągnąć krótkie dane z listy 10 ofert – tytuł, budżet, kategoria, nazwa, avatar, opis.

## Kroki
1. Pobrać HTML strony kategorii (z testu 01)
2. Znaleźć selektory CSS dla każdego pola
3. Sparsować 10 ofert do JSON
4. Zweryfikować poprawność danych

## Oczekiwany wynik
```json
[
  {
    "title": "Stworzenie narzędzia do...",
    "author": "RADI",
    "avatar": false,
    "offers_count": 15,
    "expires": "Znika za 30 dni",
    "category": "Oprogramowanie",
    "budget": "500,00 PLN",
    "short_desc": "Szukam programisty...",
    "link": "https://useme.com/pl/jobs/..."
  },
  ...
]
```

## Wyniki
*(do uzupełnienia po teście)*