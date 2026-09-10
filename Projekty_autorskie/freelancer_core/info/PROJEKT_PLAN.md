# Projekt: Automatyczna Ofertowarka Freelancer.pl

> Status: **SZKIELET PRODUKCYJNY GOTOWY (przetestowany reconem na żywej platformie)**

---

## 1. Co to jest

Odpowiednik `useme_core` dla platformy **freelancer.pl**. Ten sam wzorzec architektoniczny:
silnik orkiestrujący + sterownik przeglądarki/API + warstwa AI + magazyn + raport do Cortexa.

**Kluczowa różnica względem Useme:** freelancer.pl udostępnia **publiczne API JSON**
(`/api/projects/0.1/...`), które działa przez kontekst Playwrighta z cookies. Dzięki temu
NIE scrapujemy HTML renderowanego client-side — pobieramy czysty JSON. To znacznie
stabilniejsze i szybsze.

---

## 2. Pliki produkcyjne

| Plik | Rola |
|---|---|
| `engine.py` | Główny silnik orkiestracji (6 kroków). |
| `browser_driver.py` | Sterownik Playwright + **klient API freelancera** (lista, detale, konto). |
| `form_driver.py` | Wypełniacz formularza Place Bid z twardym bezpiecznikiem DRY_RUN. |
| `ai_pipeline.py` | Warstwa AI (selekcja + generowanie oferty) — identyczna jak w Useme. |
| `chain_executor.py` | Executor łańcucha slotów AI (reużyty bez zmian). |
| `storage.py` | Magazyn zleceń, deduplikacja po ID, checkpointy. |
| `cortex_bridge.py` | Raport postępu do `cortex-app/data/pipelines/freelancer-bot/stan.json`. |
| `config.py` | Konfiguracja (kategorie = job_id, flagi DRY_RUN/USE_MOCK_AI/HEADLESS). |

---

## 3. Przepływ (6 kroków)

```
START
  │
  ▼
[1] Weryfikacja sesji + salda konta  (cookies + scrape dashboard)
  │
  ▼
[2] Pobranie projektów z kategorii  (API /projects/active/?jobs[]=...)
  │
  ▼
[3] Deduplikacja w magazynie
  │
  ▼
[4] Pełne detale projektów  (API /projects/{id}/)
  │
  ▼
[5] Selekcja AI  ->  [6] Generowanie oferty (łańcuch slotów)
  │
  ▼
[7] Formularz Place Bid  (DRY_RUN: stop przed wysyłką)
  │
KONIEC
```

---

## 4. Kategorie (mapowanie job_id z API)

| Klucz | job_id |
|---|---|
| `programowanie-i-it` | 3 (PHP), 9 (JS), 13 (Python), 68 (SQL), 500 (Node), 613, 1092, 1093, 1239, 1240, 2703, 116, 167, 2299 |
| `web-dev` | 1031, 2839, 2701, 1827, 335, 323, 1042, 77, 2435, 1595 |
| `automation-ai` | 1977, 913, 2068, 2916, 2917, 2918, 3380, 3381, 3508, 3470, 292, 2607, 2719, 2946, 2966, 3101, 3300 |
| `sklepy-shopify` | 502, 1686, 3535, 371, 69, 2723 |
| `scraping-dane` | 95, 1040, 1051, 1075, 36, 334, 199 |

Pełna lista 3482 jobów: `lab/recon6/jobs.json`.

---

## 5. ⚠️ Stan konta i formularz

**Aktualne konto:** `@KsawierP` (id **91504805**), saldo **+$4.00 USD**.

Recon (2 konta) pokazał:
- Stare konto (90851053, -$12.29) → twarda blokada: przycisk "Złóż ofertę" **nie renderuje się**,
  na stronie widnieje *"You are restricted from bidding... maintain a minimum balance of $20 USD"*.
- Nowe konto (91504805, +$4.00) → **przycisk "Złóż ofertę" się pojawia i formularz działa**
  (przetestowane DRY_RUN: kwota/dni/opis wpisane poprawnie).

**Wniosek:** próg $20 blokuje konto przy saldzie UJEMNYM (lub zerowym). Przy saldzie +$4
formularz dał się otworzyć i wypełnić. Realna wysyłka (submit) **nie została przetestowana**
— istnieje ryzyko, że platforma odrzuci submit przy saldzie < $20. Zalecane: wpłata min. $20.

### Selektory formularza (potwierdzone reconem)

| Pole | Selektor |
|---|---|
| Kwota oferty | `#bidAmountInput` |
| Dni | `#periodInput` |
| Treść oferty | `#descriptionTextArea` |
| Przycisk otwarcia/submit | `button:has-text('Złóż ofertę')` / `'Place Bid'` |

Uwaga: przycisk renderuje się dopiero ~6 s po wejściu na stronę (Angular). `form_driver`
czeka jawnie przez `wait_for_selector`.

---

## 6. Bezpieczniki

1. **DRY_RUN** (domyślnie `True`) — przygotowuje ofertę, nie wysyła.
2. **Kontrola salda** — twarda blokada przy ujemnym saldzie.
3. **Deduplikacja + status WYSLANO** — zakaz podwójnej wysyłki.
4. **Filtr `local`** — pomijamy projekty lokalne (nie do wykonania zdalnie).
5. **Limit bidów** — platforma daje 6 bidów na cykl (odświeżane).