# PROMPT: PORZĄDEK w projekcie po teście 16 (formularz wysyłki)

> Wklej ten prompt na nowy czat. Agent wykonuje porządki w folderze lab + kopiuje cookies.json,
> aktualizuje LAB_PLAN.md i raportuje. **NIE uruchamia przeglądarki i NIE odpała żadnych skryptów.**

---

## Kontekst projektu

Projekt: **Automatyczna Ofertowarka Useme** – półautomat wyszukujący zlecenia na useme.com,
wybiera je AI (DeepSeek lokalny), generuje propozycje, a po akceptacji człowieka wypełnia formularz wysyłki.
Ścieżka projektu: `c:\Users\Ksawier\Pictures\Screenshots\useme`

Struktura: `info/` (dokumentacja, plany), `tech/` (decyzje techniczne, stack), `lab/` (testy),
`useme-ai-automation/` (STARY program TypeScript – ma zostać usunięty przez użytkownika, nie przez Ciebie).

**AUTORYTATYWNY stack (test 15):** Chromium + playwright-stealth + cookies.json + **headless=False**
(widoczna przeglądarka) + `domcontentloaded` + wait 3 s (NIE networkidle).
**Test 16 (2026-08-06):** formularz wysyłki otwiera się w pełni w widocznej przeglądarce z cookies
(prawdziwy URL: `/pl/jobs/{ID}/offer/start/`; root `/offer/start/` = 404). Schemat pól potwierdzony.
Dokumenty `info/` i `tech/` są już NA BIEŻĄCO – nie zmieniaj ich treści poza wskazanymi notkami.

---

## Zadania (wykonaj po kolei)

### 1. USUŃ przestarzałe foldery i pliki testów (wnioski nadpisane)

Usuń CAŁE foldery:
- `c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test14_formularz_z_cookies\` — wnioski BŁĘDNE
  (headless zablokowany; w widocznej przeglądarce formularz DZIAŁA – test 16 nadpisuje)
- `c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test12_cookies_czy_chrome\` — przestarzały
  (headless okazał się niestabilny w teście 15; wynik już w `lab/test_results/test12_result_tura3.md`)

Wyczyść `lab/test13_parser_surowe_html\` – usuń WSZYSTKIE skrypty prób i zrzuty:
`test13_probe*.py`, `test13_fetch_*.py`, `test13_fetch_final.py`, `analyze_real_html*.py`,
`raw_detail*.html`, `rendered*.html`, `probe*.html`, `fetch_meta.json`, `probe_report.json`.
**ZOSTAW TYLKO:** `test13_parser.py` (działający parser JSON-LD) i `parsed_details_v3.json` (wynik).

Usuń stare prompty (ich zadania są zakończone):
- `lab\MASTER_PROMPT.md` (porządki po rundzie 2 – zrobione)
- `lab\TESTY_RUNDA3.md` (prompt tury 3 – zrobiona, wyniki w `lab/test_results/`)

### 2. SKOPIUJ cookies.json do kanonicznej lokalizacji

- Źródło: `c:\Users\Ksawier\Pictures\Screenshots\useme\useme-ai-automation\cookies.json` (oryginał ze starego programu)
- Cel: `c:\Users\Ksawier\Pictures\Screenshots\useme\tech\cookies.json`
- Weryfikacja: sprawdź że zawiera `sessionid` i `csrftoken`. Porównaj z
  `lab\test15_final_flow\cookies.json` (kopia, która DZIAŁA w testach 15-16). Jeśli się różnią,
  wybierz tę, która jest zalogowana (obecny `sessionid`) – w razie wątpliwości użyj wersji z test15.

Po skopiowaniu DODAJ do `tech\TECH_STACK.md` (sekcja "Instalacja" / na końcu) notkę:
```
### cookies.json (kanoniczny)
- Lokalizacja: `tech/cookies.json` (skopiowany z `useme-ai-automation` po turze 3 + test 16)
- Zawiera sesję zalogowanego konta (sessionid + csrftoken) – NIE udostępniać, NIE commitować.
- Uwaga: sesja wygasa – gdy przestanie działać, trzeba wyeksportować nowe cookies z przeglądarki.
```

### 3. OZNAKUJ nieaktualne raporty (nie usuwaj raportów)

- `lab\test_results\test14_result_tura3.md` – dodaj na samej górze:
  `> ⚠️ WNIOSKI NIEAKTUALNE – patrz TEST 16 (2026-08-06): formularz wysyłki otwiera się w widocznej przeglądarce (headless=False) z cookies.`
- `lab\test_results\test11_result_runda2.md` – dodaj na górze:
  `> ⚠️ URL formularza poprawiony w teście 16: prawidłowy to /pl/jobs/{ID}/offer/start/ (root /offer/start/ = 404).`
- Jeśli w innych raportach widzisz sprzeczność z powyższymi faktami (test 16), dodaj podobną notkę – nie edytuj treści.

### 4. ZAKTUALIZUJ `lab\LAB_PLAN.md`

Dodaj sekcję "PORZĄDKI 2026-08-06 (po teście 16)" z listą:
- usunięto: test14_formularz_z_cookies, test12_cookies_czy_chrome, skrypty prób w test13, MASTER_PROMPT.md, TESTY_RUNDA3.md
- przeniesiono: cookies.json → tech/cookies.json (kanoniczny)
- oznakowano: test14_result_tura3.md i test11_result_runda2.md jako nieaktualne
- zostało (autorytatywne): test15_final_flow (finalny flow), test16_formularz_schema (schemat formularza),
  test13_parser_surowe_html/test13_parser.py (parser JSON-LD), test_results/ (raporty 01-16)
- aktualna lista folderów testów + ich status (1-linijkowy opis każdego)

### 5. RAPORT

Podsumuj w odpowiedzi: co usunięto (z iloma plikami), co skopiowano, co oznakowano.
Krótko – 10-15 linii.

---

## ZAKAZY

- ❌ NIE usuwaj i NIE modyfikuj: `info/` (całe), `tech/` (poza notką o cookies.json), `lab/test15_final_flow/`
  (AUTORYTATYWNY wynik), `lab/test16_formularz_schema/` (schemat formularza), `lab/test_results/` (raporty – tylko notki),
  `lab/test13_parser_surowe_html/test13_parser.py`, `tech/turnstile_solver.py` (solver od seniora – tylko notatka).
- ❌ NIE usuwaj `useme-ai-automation/` (decyzja użytkownika). Skopiuj tylko cookies.json i w raporcie
  zaznacz, że folder można już usunąć.
- ❌ NIE odpalaj przeglądarki, NIE uruchamiaj testów, NIE wysyłaj niczego.
- ❌ NIE zmieniaj treści dokumentów merytorycznych poza wskazanymi notkami.
- ❌ NIE usuwaj plików wynikowych JSON (final_flow_results.json, form_schema.json itd.) ani markerów.
- ❌ NIE twórz nowych plików poza aktualizacją LAB_PLAN.md.
