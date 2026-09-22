# /trae — Analiza dlaczego bot Useme NIE DZIAŁA

**Data:** 2026-09-14 · **Autor:** zespół agentów badawczych · **Cel:** hipotezy + plan, bez zmiany kodu.

## Dokumenty

| Plik | Zawartość |
|---|---|
| README.md | ten indeks |
| [00_REASONING.md](00_REASONING.md) | pełny tok rozumowania zespołu (etapy 0–6) |
| [01_DIAGNOZA.md](01_DIAGNOZA.md) | fakty z dowodami plik:linia (mechanika) |
| [02_HIPOTEZY_100.md](02_HIPOTEZY_100.md) | 100 hipotez czemu wysyłka nie działa (mechanika) |
| [03_PLAN_ODZYSKANIA_OFERT.md](03_PLAN_ODZYSKANIA_OFERT.md) | plan Playwright: odzyskać oferty z Useme |
| [04_ANEKS_ZALOZENIA.md](04_ANEKS_ZALOZENIA.md) | założenia, sprzeczności, pytania |
| [05_TRESC_I_WYCENA_100_HIPOTEZ.md](05_TRESC_I_WYCENA_100_HIPOTEZ.md) | **100 hipotez o TREŚCI OFERT i WYCENACH** (zawężenie użytkownika) |

> Uwaga: użytkownik zawęził zakres do **treści ofert i wycen** → kluczowy jest plik `05`. Pliki `00–04` dotyczą szerszej mechaniki (kontekst).

## Najważniejszy wniosek (treść + wycena)

- **Treść ofert jest DOBRA** (144357, 144275 = poziom ekspercki, konkretny).
- **Główny problem = WYCENA i spójność zakres↔cena↔brief** — AI dorzuca zakres spoza ogłoszenia i zawyża stawkę; poprawność ratuje kalkulator + walidator 08.
- **System kruchу**: działa tylko 1 z 7 walidatorów; brak kontroli kompletności, tonu, spójności.