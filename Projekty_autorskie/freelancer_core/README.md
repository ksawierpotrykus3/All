# freelancer_core

Automatyczna ofertowarka dla **freelancer.pl** — odpowiednik `useme_core`.

## Kluczowa różnica: API-first

Freelancer.pl udostępnia publiczne API JSON, które działa przez kontekst Playwrighta
z cookies. Dlatego zamiast scrapować HTML renderowany client-side, pobieramy czysty JSON:

- `GET /api/projects/0.1/projects/active/?jobs[]=<id>&...` — lista projektów
- `GET /api/projects/0.1/projects/<id>/` — pełne detale projektu

## Uruchomienie

```bash
python engine.py
```

Flagi w `config.py`:
- `DRY_RUN=True` — przygotowuje ofertę, **nie wysyła** (bezpiecznik)
- `USE_MOCK_AI=True` — deterministyczny mock (test szkieletu bez sieci AI)
- `HEADLESS=False` — widoczna przeglądarka

## ⚠️ Stan konta

Aktualne konto: **@KsawierP** (id 91504805), saldo **+$4.00 USD**.

- Przy saldzie **ujemnym** (poprzednie konto: -$12.29) platforma **twardo blokuje bidding** —
  przycisk "Złóż ofertę" w ogóle się nie renderuje.
- Przy saldzie **dodatnim** formularz działa (potwierdzone DRY_RUN: kwota/dni/opis wpisane).
- Platforma ostrzega o progu **$20 USD** — przy saldzie < $20 istnieje ryzyko odrzucenia submit.
  **Zalecana wpłata min. $20 USD.**

## Struktura

| Plik | Rola |
|---|---|
| `engine.py` | Orkiestracja (6 kroków) |
| `browser_driver.py` | Playwright + klient API freelancera |
| `form_driver.py` | Formularz Place Bid + bezpiecznik DRY_RUN |
| `ai_pipeline.py` | Selekcja + generowanie oferty |
| `chain_executor.py` | Łańcuch slotów AI |
| `storage.py` | Magazyn / deduplikacja |
| `cortex_bridge.py` | Raport do Cortexa |
| `config.py` | Konfiguracja |

Szczegóły: [info/PROJEKT_PLAN.md](info/PROJEKT_PLAN.md)