# 04 — Aneks: założenia, sprzeczności, pytania

## 1. Założenia
- Kod produkcyjny: `engine.py`, `ai_pipeline.py`, `chain_executor.py`, `form_driver.py`, `browser_driver.py`, `storage.py`, `config.py`, `bezpieczenstwo.py`, `wycena_kalkulator.py`, `cortex_bridge.py`, `login_useme.py`, `zbieracz_danych.py`, `pobierz_dane_badawcze.py`.
- `lab/` = kod historyczny/testowy (źródło wiedzy).
- `.venv/` pominięty.
- Stan na 2026-09-14; `DRY_RUN=False`, `HEADLESS=False`, `USE_MOCK_AI=False`.

## 2. Sprzeczności w dokumentacji
| # | Sprzeczność | Strony |
|---|---|---|
| S1 | evaluate+fetch działa (test15) vs ZAWSZE 403 (test13) | [test15](file:///c:/Users/buchh/projects/useme/lab/test_results/test15_result_tura3.md), [test13](file:///c:/Users/buchh/projects/useme/lab/test_results/test13_result_tura3.md) |
| S2 | Formularz za Turnstile (test14) vs bez (test16) | [test14](file:///c:/Users/buchh/projects/useme/lab/test_results/test14_result_tura3.md), [test16](file:///c:/Users/buchh/projects/useme/lab/test_results/test16_result.md) |
| S3 | headless 3/3 (test12) vs 100% blokad (test15) | [test12](file:///c:/Users/buchh/projects/useme/lab/test_results/test12_result_tura3.md), [test15](file:///c:/Users/buchh/projects/useme/lab/test_results/test15_result_tura3.md) |
| S4 | URL `/offer/start/` vs `/pl/jobs/{ID}/offer/start/` | rozstrzygnięte: drugi |
| S5 | TurnstileSolver potrzebny vs backup | [TECH_STACK.md:161](file:///c:/Users/buchh/projects/useme/tech/TECH_STACK.md) |
| S6 | ID kategorii 34/35 vs stare 10 | [LORE_USEME.md:37-39](file:///c:/Users/buchh/projects/useme/info/LORE_USEME.md) |
| S7 | Limit długości 35 linii vs „ile trzeba" | [jak_pisac_oferty.md:228](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md) vs [:175](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md) |
| S8 | Nawiasy dozwolone vs zakazane | [jak_pisac_oferty.md:93](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md) vs [oferty_useme.md:9](file:///c:/Users/buchh/projects/useme/wiedza_biznesowa/notatki_i_teorie/oferty_useme.md) |

## 3. Otwarte pytania
1. Co dokładnie „nie działa" — start, formularz, czy efekt?
2. Czy panel Useme pokazuje oferty oznaczone WYSLANO? (klucz do fałszywego sukcesu)
3. Czy proxy DeepSeek (127.0.0.1:4571) działa?
4. Czy `tech/cookies.json` świeże?
5. Czy istnieje plik `STOP`?
6. Czy są logi z ostatniego runu?
7. (treść+wycena) Czy użytkownik chce, by wyceny były wyższe/niższe niż obecne?

## 4. Luki
- Brak logu zbiorczego per-run.
- Brak lokalnej historii „moje oferty z Useme".
- Nie zbadano wszystkich 27 stan.json.
- Nie zweryfikowano selektorów panelu Useme.
- Brak A/B testu strategii ofert (wszystkie track puste).

## 5. Kluczowe pliki
[engine.py](file:///c:/Users/buchh/projects/useme/engine.py) · [form_driver.py](file:///c:/Users/buchh/projects/useme/form_driver.py) · [chain_executor.py](file:///c:/Users/buchh/projects/useme/chain_executor.py) · [ai_pipeline.py](file:///c:/Users/buchh/projects/useme/ai_pipeline.py) · [wycena_kalkulator.py](file:///c:/Users/buchh/projects/useme/wycena_kalkulator.py) · [chain_config.json](file:///c:/Users/buchh/projects/useme/prompts/chain_config.json) · [jak_pisac_oferty.md](file:///c:/Users/buchh/projects/useme/prompts/kontekst/jak_pisac_oferty.md)

## 6. Zgodność z poleceniem
- ✅ Nie zmieniono kodu produkcyjnego.
- ✅ Dokumentacja w `/trae` (README, 00–05).
- ✅ 100 hipotez mechaniki (02) + 100 hipotez treść/wycena (05).
- ✅ Plan odzyskania ofert (03).
- ✅ Praca przez subagentów, wyniki zsyntetyzowane.