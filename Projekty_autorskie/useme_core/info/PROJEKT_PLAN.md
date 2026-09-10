# Projekt: Automatyczna Ofertowarka Useme

> Data ostatniej aktualizacji: 2026-09-08 | Status: **SZKIELET PRODUKCYJNY GOTOWY (PRZETESTOWANY)** | Autor: Ksawier + Antigravity

---

## 1. Aktualny stan systemu (Wrzesień 2026)

Całość została zunifikowana w jeden czysty szkielet produkcyjny z wydzielonym modułem AI.  
Przeprowadzono pełny test deterministyczny na żywej platformie Useme w trybie **DRY-RUN** (potwierdzone wypełnienie pól i dojście do ekranu podsumowania bez wysyłania oferty).

### Główne pliki produkcyjne w katalogu głównym:
* [`engine.py`](../engine.py) – Główny silnik orkiestracji procesu.
* [`browser_driver.py`](../browser_driver.py) – Sterownik Playwright (stealth, sesja, pobieranie list i detali).
* [`form_driver.py`](../form_driver.py) – Wypełniacz formularza Useme z twardym bezpiecznikiem `DRY_RUN`.
* [`ai_pipeline.py`](../ai_pipeline.py) – **Wydzielona warstwa AI** (łatwa do modyfikacji promptów i reguł przez dowolne AI bez dotykania przeglądarki).
* [`storage.py`](../storage.py) – Magazyn zleceń (`magazyn/`), deduplikacja po ID i obsługa markera.
* [`config.py`](../config.py) – Centralna konfiguracja (flagi: `DRY_RUN`, `USE_MOCK_AI`, `HEADLESS`).
* [`cortex_bridge.py`](../cortex_bridge.py) – Mostek raportujący postęp w czasie rzeczywistym do `cortex-app/data/pipelines/useme-oferty/stan.json`.
* [`pobierz_dane_badawcze.py`](../pobierz_dane_badawcze.py) – Skrypt do hurtowego zbierania bazy badawczej konkurencji.

---

## 2. Baza badawcza (Nowe)

W folderze [`dane_badania/`](../dane_badania/) zebrano pełne dane 100 najnowszych ofert:
* `it/` – 50 folderów ze zleceniami Programowanie i IT
* `serwisy/` – 50 folderów ze zleceniami Serwisy internetowe
* Każdy folder zlecenia zawiera:
  1. `zlecenie.txt` – czytelny tekst z pełnym opisem i kompletną listą konkurentów (umowy, profile, tagi).
  2. `zlecenie.json` – struktura danych pod analizę maszynową.
  3. `strona.html` – surowy kod HTML ze wszystkimi ofertami rywali.

---

## 3. Dokumentacja bazowa

| Plik | Co zawiera |
|---|---|
| [LORE_USEME.md](./LORE_USEME.md) | Czym jest Useme, jak działa, URL-e, zabezpieczenia, limity |
| [DANE_OFERT.md](./DANE_OFERT.md) | Co wyciągamy z ofert – dane z listy + pełne po kliknięciu |
| [PRZEPLYW.md](./PRZEPLYW.md) | Szczegółowy przebieg procesu krok po kroku |
| [KONTA.md](./KONTA.md) | Informacje o sesji i autoryzacji cookies |

---

## 4. Kluczowe decyzje architektoniczne

1. **Brak interfejsu CMD:** Wszystkie `input()` w terminalu zostały wycięte. Stan melduje się bezgłowo do aplikacji Cortex (`stan.json`).
2. **Bezpiecznik DRY_RUN:** System domyślnie zatrzymuje się na stronie podsumowania przed kliknięciem ostatecznego „Wyślij” i wykonuje zrzut dowodowy.
3. **Turnstile i Cloudflare:** W trybie widocznym (`headless=False`) lub z poprawnym profilem i ciasteczkami sesyjnymi Turnstile nie blokuje formularza.
4. **Prawa autorskie:** Zaznaczane tylko wtedy, gdy w formularzu widnieje napis „decyzja freelancera”. Jeśli brak – pole nie jest modyfikowane.
