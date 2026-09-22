# 00 — Pełny tok rozumowania (jak zespół naukowców)

Metoda: **obserwacja → inwentaryzacja → pomiar → falsyfikacja → hipotezy → plan eksperymentu**.
Nie zmieniamy kodu. Każde twierdzenie ma dowód (plik:linia) lub jest jawne jako hipoteza.

## Etap 0 — Sformułowanie problemu
Twierdzenie „To co wysyłam NIE DZIAŁA" jest wieloznaczne. Warianty:
- P0-A: oferty nie są wysyłane wcale.
- P0-B: fałszywy sukces (bot myśli że wysłał).
- P0-C: treść/wycena zła.
- P0-D: za mało ofert w bazie.
- P0-E: coś nie startuje (sesja/proxy).
**Decyzja:** badamy wszystkie równolegle (6 subagentów), potem ważymy.

## Etap 1 — Inwentaryzacja architektury
```
START → config → bezpieczenstwo → storage
  → browser_driver (Chromium+stealth+cookies)
  → dla konta: lista zleceń → dedup → detale → AI1 selekcja
     → dla oferty: AI2 (chain_executor→proxy 127.0.0.1:4571)
        → sanity → form_driver "Wyślij" → magazyn + debug/*.png
```
Obserwacja #1: `turnstile_solver.py` (1150+ linii) **leży poza** ścieżką formularza.
Obserwacja #2: dwie warstwy — magazyn (JSON) i pipeline (stan.json); **9 zleceń nigdy nie weszło w pipeline**.

## Etap 2 — Pomiar
| Metryka | Wartość |
|---|---|
| Rekordów w magazynie | 36 |
| WYSLANO | 22 |
| POBRANO_DETALE | 12 |
| PRZYGOTOWANA | 1 (144353) |
| BLAD_FORMULARZA | 1 (144154) |
| Dowody PNG | 11 |
| Pipeline 7/7 | 27 |
Wnioski: „za mało ofert" PRAWDA, ale wąskie gardło = **przetwarzanie** (12 ofert stoi na POBRANO_DETALE). Rozbieżność 22 vs 11 PNG → brak jednego źródła prawdy o wysyłce.

## Etap 3 — Falsyfikacja (co NIE jest przyczyną)
- ❌ Brak limitu dziennego (świadomie usunięty).
- ❌ Walidatory 03-07,20 (wyłączone; 08 nie abortuje).
- ❌ Turnstile na formularzu (test16: brak przy HEADLESS=False).
- ❌ Zły URL formularza (poprawiony: `/pl/jobs/{ID}/offer/start/`).
- ❌ CF blokuje zawsze (zależy od headless/dnia).

## Etap 4 — Drzewo przyczyn
A. fałszywy sukces · B. cichy abort AI · C. gubienie ofert · D. infrastruktura · E. konfiguracja · F. timing.
Dla zawężenia „treść+wycena": obszar **E/treść-wycena** → plik `05`.

## Etap 5 — Plan eksperymentu
Każda hipoteza ma test falsyfikujący (`02`, `05`). Odzyskanie ofert — `03`.

## Etap 6 — Wnioski meta
1. System broni się „po cichu" (dziesiątki `return None`, `except: log`) — trudna diagnoza.
2. Dowody niespójne (22 vs 11) — brak jednego źródła prawdy.
3. Przy treści+wycenie: **treść dobra, wycena krucha** (patrz `05`).