# Test 02 – Wynik

**Status:** ✅
**Data:** 2026-08-06

## Znalezione selektory CSS

| Element | Selektor CSS |
|---|---|
| Kontener oferty | `article.job` |
| Tytuł + link | `a.job__title-link` |
| Autor (zleceniodawca) | `div.job__headline strong` |
| Avatar | `div.user_avatar` (sprawdzanie obecności klasy `user_avatar__default-image`) |
| Liczba wysłanych ofert | `div.job__header-details--offers span:last-child` |
| Czas do wygaśnięcia | `div.job__header-details--date span:last-child` |
| Kategoria szczegółowa | `div.job__category a p` |
| Budżet | `span.job__budget-value` |
| Opis | `div.job__content p` |

## Przykładowy JSON (pierwsza oferta)
```json
{
  "title": "Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika",
  "url": "https://useme.com/pl/jobs/stworzenie-narzedzia-do-drukowania-w-pdf-zestawow-z-platnika,142281/",
  "author": "RADI",
  "has_avatar": false,
  "offers_count": 17,
  "expiry": "Znika za 30 dni",
  "category": "Oprogramowanie",
  "budget": "500,00 PLN",
  "description": "Szukam programisty/freelancera, który stworzy prostą aplikację desktopową do generowani wydruków w pdf zestawów stworzonych w Płatniku"
}
```

## Liczba znalezionych ofert: 10/10

## Podsumowanie ofert

| # | Tytuł | Autor | Avatar | Oferty | Wygasa | Kategoria | Budżet |
|---|---|---|---|---|---|---|---|
| 1 | Stworzenie narzędzia do drukowania w pdf... | RADI | NIE | 17 | 30 dni | Oprogramowanie | 500,00 PLN |
| 2 | Automatyzacja Make/n8n/Python... | user042005 | TAK | 25 | 30 dni | Projekty IT | Do negocjacji |
| 3 | Inteligentna Platforma AI... | Anna | NIE | 27 | 30 dni | Oprogramowanie | Do negocjacji |
| 4 | Oprogramowanie ecommerce PHP + React/Vue... | Software House | NIE | 21 | 60 dni | Oprogramowanie | Do negocjacji |
| 5 | Konfigurator personalizacji Shoper Storefront | Klaudia | NIE | 22 | 30 dni | Aplikacje webowe | Do negocjacji |
| 6 | API Allegro, Shopper | Jacek Ulman | TAK | 37 | 29 dni | Oprogramowanie | Do negocjacji |
| 7 | Aplikacja po przeniesieniu na produkcję... | michal.lubisz@... | NIE | 24 | 6 dni | Administracja serwerami | Do negocjacji |
| 8 | Integrator Optima ↔ Base.com | michal.lubisz@... | NIE | 26 | 6 dni | Oprogramowanie | Do negocjacji |
| 9 | Aplikacja webowa – zarządzanie siecią sprzedaży | Adam889 | NIE | 72 | 13 dni | Aplikacje webowe | Do negocjacji |
| 10 | Automatyzacja procesów i AI... | thybalt002 | NIE | 45 | 29 dni | Projekty IT | Do negocjacji |

## Pliki wyjściowe
- Skrypt: `lab/test02_parse_list/test02_parse.py`
- JSON: `lab/test02_parse_list/offers.json` (10 ofert)

## Problemy
- Brak. Wszystkie 10 ofert zostało poprawnie sparsowanych.
- Avatar wykrywany przez sprawdzenie, czy `div.user_avatar` NIE zawiera klasy `user_avatar__default-image`. Działa poprawnie: 2 oferty mają własne avatary (user042005, Jacek Ulman).
- Uwaga: większość budżetów to "Do negocjacji" – tylko jedna oferta ma konkretną kwotę (500 PLN).