# LAB – Plan testów i eksperymentów

> Folder: `lab/` – tutaj testujemy każdy element osobno, zanim złożymy całość.
> Wyniki testów → `lab/test_results/`. Co się sprawdzi → trafia do `tech/`.

---

## Dlaczego lab?

Zamiast od razu budować cały mechanizm, rozbijamy go na małe, niezależne testy.
Każdy test = jeden folder. Każdy test ma swój cel, oczekiwany wynik i wnioski.

---

## Lista testów (w kolejności)

### Test 01 – Połączenie i dostęp do Useme
**Folder:** `lab/test01_connect/`

**Cel:** Sprawdzić, czy w ogóle możemy wejść na Useme przez Playwright + Camoufox + Firefox.

**Co sprawdzamy:**
- Czy Playwright z Camoufox i Firefoxem odpala się na Windows?
- Czy strona Useme ładuje się bez błędu Cloudflare?
- Czy jesteśmy zalogowani (cookies)?
- Czy widzimy listę ofert (czy nie przekierowuje na login)?

**Oczekiwany wynik:**
- Strona kategorii ładuje się poprawnie
- Nie ma blokady Cloudflare (albo jest do przejścia)
- Widać oferty (jesteśmy zalogowani przez cookies)
- HTML strony jest dostępny do parsowania

**Status:** ✅ zakończony (runda 1)

---

### Test 02 – Parsowanie listy ofert
**Folder:** `lab/test02_parse_list/`

**Cel:** Wyciągnąć dane z listy ofert (krótkie opisy) – tytuł, budżet, kategoria, itd.

**Co sprawdzamy:**
- Czy BeautifulSoup poprawnie znajduje elementy HTML z ofertami?
- Jakie selektory CSS działają?
- Czy dane (tytuł, budżet, kategoria, nazwa, avatar) są poprawnie wyciągane?
- Czy otrzymujemy dokładnie 10 ofert?
- Czy kolejność jest od najnowszej?

**Oczekiwany wynik:**
- Lista 10 słowników JSON z danymi ofert
- Wszystkie pola z `DANE_OFERT.md` sekcja A są wypełnione
- Dane są czyste (bez zbędnych spacji, znaków HTML)

**Status:** ✅ zakończony (runda 1)

---

### Test 03 – Wchodzenie w ofertę i pełny opis
**Folder:** `lab/test03_parse_detail/`

**Cel:** Kliknąć w ofertę, kliknąć "pokaż pełny opis", pobrać wszystkie dane szczegółowe.

**Co sprawdzamy:**
- Czy Playwright klika w tytuł oferty i przechodzi do szczegółów?
- Czy znajduje i klika przycisk "pokaż pełny opis" / "zobacz pełny opis"?
- Czy po kliknięciu ładuje się pełny opis?
- Czy wyciągamy: pełny opis, umiejętności, dane z menu prawego?
- Czy znajduje przycisk "Dodaj ofertę"?

**Oczekiwany wynik:**
- Pełne dane oferty (sekcja B z `DANE_OFERT.md`)
- Przycisk "Dodaj ofertę" znaleziony i gotowy do kliknięcia
- Czas ładowania akceptowalny

**Status:** ✅ zakończony (runda 1)

---

### Test 04 – AI #1: Selekcja ofert
**Folder:** `lab/test04_ai1_select/`

**Cel:** Wysłać listę ofert do DeepSeek V4 Pro i sprawdzić, czy AI poprawnie wybiera pasujące.

**Co sprawdzamy:**
- Czy połączenie z DeepSeek (`localhost:4570/v1`) działa?
- Czy AI dostaje listę ofert i prompt z pliku?
- Czy AI zwraca sensowną selekcję?
- Czy format odpowiedzi jest ustrukturyzowany (JSON)?
- Jak długo trwa odpowiedź?

**Oczekiwany wynik:**
- AI odpowiada w < 30 sekund
- Zwraca listę wybranych ofert z uzasadnieniem
- Format JSON poprawny

**Status:** 🔴 nie rozpoczęty

---

### Test 05 – AI #2: Generowanie propozycji
**Folder:** `lab/test05_ai2_generate/`

**Cel:** Wysłać pełne dane JEDNEJ oferty do DeepSeek i sprawdzić, czy generuje sensowną propozycję.

**Co sprawdzamy:**
- Czy AI dostaje pełne dane oferty + prompt z pliku?
- Czy generowana treść jest odpowiednia (długość, styl, personalizacja)?
- Czy proponuje stawkę jeśli budżet "Do negocjacji"?
- Czy format odpowiedzi jest gotowy do wklejenia w formularz?

**Oczekiwany wynik:**
- Gotowa treść propozycji (3-8 zdań)
- Propozycja stawki (jeśli potrzebna)
- Brak halucynacji (AI nie zmyśla danych z oferty)

**Status:** 🔴 nie rozpoczęty

---

### Test 06 – Pełny flow (integracja)
**Folder:** `lab/test06_full_flow/`

**Cel:** Przeprowadzić cały proces od A do Z (bez wysyłki) na prawdziwych danych.

**Co sprawdzamy:**
- Czy wszystkie kroki działają razem?
- Czy marker poprawnie odfiltrowuje nowe oferty?
- Czy AI #1 → Playwright → AI #2 działa bez błędów?
- Czy całość kończy się w rozsądnym czasie?

**Status:** ✅ zakończony (runda 1) – pełny flow działa, Cloudflare problematyczny

---

## Folder na notatki

**`lab/notes/`** – luźne obserwacje, problemy, pomysły w trakcie testowania.

---

## Folder na wyniki

**`lab/test_results/`** – tutaj zapisujemy wyniki każdego testu:
- `test01_result.md` – czy połączenie działa, jakie problemy
- `test02_result.md` – przykładowe dane, selektory które działają
- `test03_result.md` – pełne dane przykładowej oferty
- `test04_result.md` – odpowiedź AI #1, format, czas
- `test05_result.md` – wygenerowana propozycja, ocena jakości
- `test06_result.md` – podsumowanie pełnego flow

---

## Co trafia z lab/ do tech/?

Kiedy test się powiedzie:
- **Działające selektory CSS** → aktualizacja `tech/TECH_STACK.md`
- **Sprawdzony format promptów** → aktualizacja `tech/AI_INTEGRACJA.md`
- **Potwierdzona logika markera** → aktualizacja `tech/LOGIKA_ITERACJI.md`
- **Sprawdzony kod** → trafia do głównego kodu projektu

Lab to piaskownica – eksperymentujemy tu, nie psujemy głównego planu.

---

## Runda 2 – wykonane testy 07-11

Data: 2026-08-06. Wszystkie testy zakończone.

| Test | Status | Kluczowy wniosek |
|------|--------|------------------|
| TEST 07 (warmup+evaluate) | ❌ brak raportu | Raport nie powstał – wynik tylko w podsumowaniu użytkownika |
| TEST 08 (JSON API) | ❌ | Useme NIE zwraca JSON – Cloudflare 403 na wszystkie warianty `Accept: application/json`. Zostajemy przy HTML+BeautifulSoup |
| TEST 09 (stary vs nowy) | ✅ | Chrome + playwright-stealth + cookies.json wygrywa z Firefox headless (0 vs 1 realnych blokad Cloudflare) |
| TEST 10 (flow v2) | ⚠️ | evaluate+fetch działa dla detali (0/5 blokad), ale zwraca surowy HTML server-side – parser nie trafił w pola (wszystkie "?"). Lista przez evaluate NIE działa (execution context destroyed po przekierowaniu). AI #2 pojedynczo nie myli kontekstu. |
| TEST 11 (formularz DRY RUN) | ⚠️ | Formularz `/offer/start/` za Cloudflare Turnstile – bez cookies DOM niedostępny. URL formularza potwierdzony. Selektory NIEZWERYFIKOWANE. |

**Kluczowe odkrycia rundy 2:**
- JSON API nie istnieje → HTML+BeautifulSoup to jedyna droga
- Chrome+stealth+cookies.json to najlepszy stack (lepszy niż Firefox)
- evaluate+fetch działa na detalach ale zwraca inną strukturę HTML (server-side vs client-side)
- Formularz wymaga zalogowanej sesji (cookies.json)

---

## Tura 3 – testy 12-15 (do uruchomienia)

**Cel:** Domknięcie luk z rundy 2 i ustalenie ostatecznego mechanizmu.

| Test | Cel |
|------|-----|
| TEST 12 (cookies czy chrome) | Ustalić, co decyduje o przejściu przez Cloudflare: przeglądarka czy cookies |
| TEST 13 (parser surowe html) | Znaleźć selektory działające na surowym HTML z evaluate+fetch |
| TEST 14 (formularz z cookies) | Zweryfikować selektory formularza z zalogowaną sesją |
| TEST 15 (final flow v3) | Połączyć wszystko w jeden działający flow |

Instrukcje w `lab/TESTY_RUNDA3.md`. Uruchomić PO porządkach (część 1 MASTER_PROMPT.md).

---

## PORZĄDKI 2026-08-06 (po teście 16)

- **Usunięto foldery:** `test14_formularz_z_cookies/` (7 plików, wnioski błędne – headless zablokowany), `test12_cookies_czy_chrome/` (5 plików, przestarzały)
- **Wyczyszczono `test13_parser_surowe_html/`:** usunięto 20 plików (skrypty prób i zrzuty HTML), zostawiono tylko `test13_parser.py` i `parsed_details_v3.json`
- **Usunięto prompty:** `MASTER_PROMPT.md`, `TESTY_RUNDA3.md` (zadania zakończone)
- **Przeniesiono:** `cookies.json` → `tech/cookies.json` (kanoniczna lokalizacja, wersja z test15, identyczna z oryginałem `useme-ai-automation`)
- **Oznakowano jako nieaktualne:** `test14_result_tura3.md`, `test11_result_runda2.md`, `test12_result_tura3.md`
- **Zostało (autorytatywne):**
  - `test15_final_flow/` – finalny flow (headless=False, Chromium+stealth, działa)
  - `test16_formularz_schema/` – schemat formularza wysyłki (pola potwierdzone)
  - `test13_parser_surowe_html/test13_parser.py` + `parsed_details_v3.json` – parser JSON-LD
  - `test_results/` – raporty 01-16
  - `test01_connect/` – `test06_full_flow/` – testy rundy 1 (historyczne, poprawne)
  - `test10_flow_v2/` – flow v2 (runda 2, historyczny)

### Aktualna lista folderów testów + status

| Folder | Status | Opis |
|--------|--------|------|
| `test01_connect/` | ✅ historyczny | Połączenie i dostęp do Useme (runda 1) |
| `test02_parse_list/` | ✅ historyczny | Parsowanie listy ofert (runda 1) |
| `test03_parse_detail/` | ✅ historyczny | Wchodzenie w ofertę i pełny opis (runda 1) |
| `test04_ai1_select/` | ✅ historyczny | AI #1: selekcja ofert (runda 1) |
| `test05_ai2_generate/` | ✅ historyczny | AI #2: generowanie propozycji (runda 1) |
| `test06_full_flow/` | ✅ historyczny | Pełny flow (runda 1) |
| `test10_flow_v2/` | ✅ historyczny | Flow v2 z evaluate+fetch (runda 2) |
| `test13_parser_surowe_html/` | ✅ aktywny | Parser JSON-LD (działa, tylko `test13_parser.py` + `parsed_details_v3.json`) |
| `test15_final_flow/` | ⭐ AUTORYTATYWNY | Finalny flow – headless=False, Chromium+stealth+cookies, działa (tura 3) |
| `test16_formularz_schema/` | ⭐ AUTORYTATYWNY | Schemat formularza wysyłki – pola potwierdzone (test 16) |
| `test_results/` | 📋 raporty | Raporty testów 01-16 |
| `PORZADEK_PROMPT_PO_TEST16.md` | 📋 prompt | Ten prompt (do usunięcia po wykonaniu) |

> **Uwaga:** folder `useme-ai-automation/` (stary program TypeScript) NIE został usunięty – decyzja użytkownika. Skopiowano z niego tylko `cookies.json`.