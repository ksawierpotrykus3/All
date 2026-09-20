# Test 03 – Wchodzenie w ofertę i pełny opis

## Status: 🔴 nie rozpoczęty
## Data: -

## Cel
Kliknąć w ofertę z listy, kliknąć "pokaż pełny opis", pobrać pełne dane szczegółowe + dane z menu prawego.

## Kroki
1. Z listy ofert kliknąć w pierwszą (Playwright)
2. Poczekać na załadowanie strony szczegółów
3. Znaleźć i kliknąć przycisk "pokaż pełny opis" / "zobacz pełny opis"
4. Poczekać na załadowanie pełnego opisu
5. Pobrać wszystkie dane: pełny opis, umiejętności, dane z prawego menu
6. Znaleźć przycisk "Dodaj ofertę"

## Oczekiwany wynik
```json
{
  "title": "...",
  "author": "RADI",
  "published": "2 godziny temu",
  "category": "Oprogramowanie",
  "copyright": "Przeniesienie praw autorskich",
  "short_desc": "...",
  "full_desc": "Wymagane funkcje: ...",
  "skills": "javascript PHP",
  "budget": "500,00 PLN",
  "expires": "30 dni",
  "add_offer_button_found": true
}
```

## Wyniki
*(do uzupełnienia po teście)*