# Przepływ – pełny proces od linku do wysyłki

> Ostatnia aktualizacja: 2026-08-06 (po rundzie 2 testów)
> Opisuje cały proces: od wejścia na link kategorii, przez AI, aż do wysłania oferty.

---

## Założenia

- **1 konto** – użytkownik jest zalogowany na stałe (cookies w przeglądarce)
- **Bez logowania** – Playwright używa istniejącej sesji (cookies.json)
- **2 kategorie** – Programowanie i IT (ID:35), Serwisy i strony (ID:34)
- **Lokalizacja paczki proxy AI (DeepSeek):** `c:\Users\Ksawier\Pictures\Screenshots\deepseek-proxy-clean\proxy_pakiet` — start przez `start.bat`, endpoint `http://localhost:4570/v1`. To NIE jest główne proxy do kodowania (tamten ma długi prompt „jak kodować", tutaj zbędny). Szczegóły: `tech/AI_INTEGRACJA.md`.
- **Półautomat** – punkty kontrolne przed wysyłką (do decyzji)
- **Docelowo automat:** interwały ustawiane w kodzie (np. od godziny startu do godziny, do której pracują admini, co ~10 min sprawdza nowe). **Na teraz wystarczy manualne uruchomienie** – automat później, gdy mechanizm zadziała

---

## Aktualizacja po rundzie 2 (CO DZIAŁA, A CO NIE)

| Element | Wynik rundy 2 |
|---|---|
| Przeglądarka | **Chrome + playwright-stealth + cookies.json** – wygrywa (0 realnych blokad CF). Firefox jako fallback |
| JSON API | ❌ Nie istnieje – Cloudflare 403 na wszystko z Accept: application/json. **Zostajemy przy HTML + BeautifulSoup** |
| Lista kategorii | `page.goto` (evaluate+fetch tuż po goto zawodzi – przekierowanie /en/ niszczy kontekst). Uwaga: `networkidle` robi timeouty → `domcontentloaded` + timeout 3s |
| Detale ofert | `page.evaluate` + fetch działa (0/5 blokad), ale zwraca **surowy HTML server-side** – selektory do dostosowania |
| Formularz /offer/start/ | URL ✅ potwierdzony, ale formularz **za Turnstile** – wymaga zalogowanej sesji (cookies). Selektory pól niezweryfikowane *(stan historyczny z rundy 2 – patrz tabela poniżej: ROZWIĄZANE testem 16)* |
| AI #2 pojedynczo | ✅ Nie myli kontekstu (błąd z rundy 1 rozwiązany) |

## Aktualizacja po TURZE 3 (OSTETECZNE – test 15 autorytatywny)

| Element | Wynik tury 3 |
|---|---|
| Przeglądarka | **Chromium + playwright-stealth + cookies.json + headless=False** (widoczna). Auto-fallback headless→widoczna. Cloudflare niestabilny w czasie |
| Lista | `page.goto(domcontentloaded)` + wait 3s + BeautifulSoup `article.job` → 12 ofert |
| evaluate na liście | Działa PO zakończeniu nawigacji (identyczne z goto) – test 10 był błędny (redirect /en/) |
| Marker | `last_offer.txt` = URL ostatniej oferty → nowe = oferty POWYŻEJ markera (potwierdzone: 11 nowych) |
| Detale | `page.evaluate`+fetch → **parser JSON-LD JobPosting + CSS `.jobs-summary__item`** → 3/3 kompletne |
| AI #2 | Pojedynczo + **watchdog 150s** (DeepSeek potrafi zawisnąć >6 min) → konkretne propozycje z wycenami |
| Formularz | ✅ **ROZWIĄZANY testem 16 (2026-08-06):** prawdziwy URL to `/pl/jobs/{ID}/offer/start/` (z linku "Dodaj ofertę"; root `/offer/start/` = 404). W **widocznej przeglądarce (headless=False) + cookies** formularz otwiera się w pełni – **Turnstile w ogóle się nie pojawia**. Pola: `#id_description`, `#id_payment`, `#id_work_days` (min 7), `#id_currency`, radio `copyright_transfer`, przycisk "Przejdź do podsumowania". Szczegóły: `lab/test_results/test16_result.md`. **Solver Turnstile od Bartka NIE jest potrzebny i NIE wymaga przerobienia – zostaje tylko jako awaryjny backup** (patrz `KONTA.md`). |
| Baner cookies | Pojawia się w widocznej przeglądarce → kliknąć `#cookiescript_accept` |

---

## Krok 1: Wejście na linki kategorii

Playwright (Chrome + stealth, z cookies.json) wchodzi na dwa URLe:

```
https://useme.com/pl/jobs/category/programowanie-i-it,35/
https://useme.com/pl/jobs/category/serwisy-internetowe,34/
```

Dla każdej kategorii pobiera HTML z listą ofert (10 najnowszych z góry strony).
**Uwaga:** używać `page.goto` z `wait_until="domcontentloaded"` + `wait_for_timeout(3000)`
– `networkidle` powoduje timeouty (WebSocket/SSE na stronie).

**Co pobieramy z listy (krótkie opisy):**
- Tytuł oferty
- Nazwa zleceniodawcy
- Avatar (tak/nie)
- Liczba już wysłanych ofert
- Czas do wygaśnięcia (np. "Znika za 30 dni")
- Kategoria szczegółowa (np. "Oprogramowanie")
- Budżet (kwota lub "Do negocjacji")
- Krótki opis (pierwsze ~200 znaków)

---

## Krok 2: Marker + Magazyn – sprawdzanie nowości

Porównanie pobranych ofert z **magazynem** (`useme_core/magazyn/`) po URL:

- Nowa = oferta, której URL nie ma jeszcze w magazynie
- Stara = oferta, której URL już jest w magazynie → pomijamy (nie duplikujemy)
- Może być 1 nowa oferta, może być 10 – cokolwiek jest nowe, idzie dalej

**WSZYSTKIE** pobrane oferty zapisujemy do magazynu (każda w osobnym pliku `<ID>.json`).
Stare oferty NIGDY nie są usuwane – dopisujemy tylko nowe pliki.

**Marker** (`marker.json`) trzyma tylko najnowszy rekord z magazynu (do podglądu/logów).
Decyzję o nowości podejmuje magazyn (czy URL już istnieje), nie marker.

**Magazyn ofert:** **wszystkie** oferty z obu kategorii (nie tylko nowe, nie tylko wybrane przez AI)
trafiają do magazynu. Magazyn to **folder** z podfolderami per kategoria, np.:
```
useme_core/magazyn/programowanie-i-it/142303.json
useme_core/magazyn/serwisy-internetowe/142250.json
```
Dwa poziomy zapisu w TYM SAMYM pliku oferty:
- **nie wysłaliśmy oferty** → zapis krótki: ID, URL, autor, tytuł, opis z listy, kategorie, budżet, status NOWA
- **wysłaliśmy ofertę** → dopisujemy pełne zlecenie + naszą ofertę (propozycja AI #2), status WYSŁANO OFERTĘ

Oferty zapisują się też po to, żeby przechodzić dalej w procesie. Szczegóły: `tech/LOGIKA_ITERACJI.md`.

---

## Krok 3: AI #1 – Selekcja ofert

**AI #1 dostaje:**
- Listę nowych ofert (tylko krótkie opisy z listy)
- Plik(i) z wytycznymi – jakie oferty pasują, jakie nie
- Prompt ustalony przez użytkownika (łatwy do edycji, osobny plik)

**AI #1 robi:**
- Analizuje każdą ofertę
- Wybiera, które pasują (np. 2 z 5, albo 7 z 10)
- Zwraca listę wybranych ofert (tytuł + powód wyboru)

**Przykład:**
```
Wejście: 5 nowych ofert
AI #1 wybiera: 2 pasują (Python/web scraping, AI/automatyzacja)
Odrzucone: 3 (niepasujące technologie, budżet za niski)
```

---

## Krok 4: Playwright – wchodzenie w oferty i pobieranie pełnych danych

Dla każdej oferty wybranej przez AI #1:

1. Playwright klika w tytuł oferty na liście → przechodzi do strony szczegółów
2. Na stronie szczegółów klika **"pokaż pełny opis"** (inaczej opis jest ucięty)
3. Pobiera pełne dane:

**Pełny opis po kliknięciu "pokaż pełny opis" – struktura:**

| Element | Przykład |
|---|---|
| Tytuł | "Stworzenie narzędzia do drukowania w pdf zestawów z Płatnika" |
| Zleceniodawca | RADI (no avatar) |
| Opis krótki | "Szukam programisty/freelancera, który stworzy prostą aplikację..." |
| Opis pełny (po kliknięciu) | "Wymagane funkcje: integracje z marketplace'ami, integracje z kurierami, integracja z KSeF, zarządzanie zamówieniami, obsługa magazynu, raportowanie i analityka" |
| Umiejętności | "javascript PHP" |
| Opublikowano | "2 godziny temu" |
| Kategoria | "Oprogramowanie" |
| Prawa autorskie | "Przeniesienie praw autorskich" |

**Menu po prawej stronie (ważne):**

| Element | Przykład |
|---|---|
| Budżet | "500,00 PLN" |
| Prawa autorskie | "Przeniesienie praw autorskich" |
| Ważne przez | "30 dni" |
| **Przycisk** | **"Dodaj ofertę"** ← najważniejszy |

---

## Krok 5: Łańcuch AI – generowanie treści oferty

> **UWAGA:** Ten krok został rozbudowany. Stary "AI #2" został zastąpiony systemem slotów.  
> Szczegóły techniczne: [`tech/AI_LANCUCH.md`](../tech/AI_LANCUCH.md)

Dla każdej wybranej oferty osobno uruchamiany jest **łańcuch AI** (do 20 slotów). Każdy slot ma własny plik prompta `.md` i można go włączać/wyłączać w `chain_config.json`.

### Slot 01 – Research sieciowy (zawsze aktywny, przed wyceną)

**Dostaje:** pełne dane oferty. Używa modelu z dostępem do internetu (`deepseek-v4-pro-search`).

**Generuje:** raport z faktami, ryzykami i amunicją do oferty, z wymogiem podawania źródeł (URL/cytat). Jeśli search zwróci pustkę, system podstawia `BRAK_ISTOTNYCH_FAKTOW`, więc łańcuch nigdy nie utknie na pustym researchu.

**Kolejność:** `01 research -> 02b wycena -> 02a treść -> walidatory`.

### Dopytywanie researchu przez 02b i 02a

Wycena (02b) i treść (02a) mogą same zadać dodatkowe pytanie researchowe. Jeśli w raporcie brakuje im faktu, który realnie zmienia wynik, zamiast zgadywać zwracają blok `[RESEARCH_QUERY] ... [/RESEARCH_QUERY]`. System przechwytuje go, odpala search i wstrzykuje wynik, po czym model dokańcza w tej samej turze.

**Wniosek z testu A/B (2026-09-09):** dodatkowy research realnie podnosi jakość. Na zleceniu Shopify VAT/IOSS wycena bez dopytywania (grupa 1) zakładała jedną sesję konsultacyjną, a z dopytywaniem (grupa 2) wykryła, że numer IOSS jest wymagany do finalizacji, więc poprawnie rozbiła pracę na dwie sesje. Na prostych zleceniach (landing page) agenty słusznie nie dopytywały, bo research 01 wystarczył.

### Slot 02b – AI #2b: Wycena + dni pracy (zawsze aktywny)

**Dostaje:**
- Pełne dane jednej oferty (opis, umiejętności, budżet, kategoria)
- Plik `prompts/agent_02b_wycena_dni.md` – wytyczne jak wyceniać
- Wspólny plik `prompts/lore.md` (umiejętności, portfolio)

**Generuje:** Propozycję stawki + liczbę dni pracy (min. 7).

### Slot 02a – AI #2a: Treść oferty (zawsze aktywny)

**Dostaje:**
- Pełne dane jednej oferty + output z 02b (kwota + dni)
- Plik `prompts/agent_02a_opis_oferty.md` – wytyczne jak pisać treść
- Wspólny plik `prompts/lore.md` (umiejętności, portfolio)

**Generuje:** Treść propozycji do wysłania zleceniodawcy.

> **Dlaczego 02b przed 02a:** wycena liczy się wyłącznie z danych zlecenia (zakres → moduły → godziny → kwota) — nie potrzebuje treści. Natomiast treść oferty musi znać kwotę i dni, żeby wpisać je naturalnie w sekcji wyceny ("Za [co] liczymy [kwota] zł"). Dlatego wycena idzie pierwsza, a generator treści dostaje gotową kwotę jako input i nie może jej zmieniać.

### Sloty 03-20 – Walidatory (opcjonalne, domyślnie wyłączone)

Po 02a i 02b można dodać dowolną liczbę walidatorów. Każdy sprawdza wybrane aspekty i daje **PASS** lub **FAIL**.

Przykładowe walidatory:
| Slot | Nazwa | Co sprawdza |
|---|---|---|
| 03 | Walidator opisu | Czy treść pasuje do zlecenia |
| 04 | Spójność | Czy wycena pasuje do zakresu prac |
| 05 | Ton i styl | Czy ton pasuje do zleceniodawcy |
| 06 | Błędy językowe | Ortografia, gramatyka |
| 07 | Kompletność | Czy wszystkie wymagania pokryte |

**FAIL →** wraca do 02a/02b po poprawki (max 3 próby) lub abort (człowiek decyduje).  
**PASS →** łańcuch leci dalej do następnego walidatora.

**Wynik:** dla każdej wybranej oferty powstaje gotowa treść + wycena + dni, zwalidowane przez aktywne sloty.

---
## Krok 6: Weryfikacja (punkt kontrolny)

Zatrzymanie przed wysyłką:

1. Wyświetlenie listy wybranych ofert + wygenerowanych treści
2. **Czekanie na decyzję człowieka:**
   - ✅ Zatwierdź i wyślij
   - ✏️ Edytuj treść i wyślij
   - ❌ Pomiń tę ofertę

Można też dodać opcję "zatwierdź wszystkie" – do ustalenia.

---
## Krok 7: Playwright – wysyłanie ofert

**Przejście (potwierdzone przez użytkownika, 2026-08-06):**

```
klik w post (ofertę) → "Dodaj ofertę" → wpisanie wszystkiego → "Przejdź do podsumowania" → "Wyślij"
```

**Pola do wypełnienia (3):**
1. **Opis** – treść propozycji (od AI #2)
2. **Wycena** – kwota oferty (AI #2 proponuje)
3. **Dni pracy** – liczba dni, **minimum 7**

**Prawa autorskie (ważne):**
- Opcje: **Licencja** / **Przeniesienie praw autorskich** / **Bez przenoszenia praw autorskich**
- **Klikamy tylko wtedy, gdy w formularzu jest napisane "decyzja freelancera"** – wtedy my wybieramy (np. "Bez przenoszenia praw autorskich")
- **Jeśli NIGDZIE nie ma napisu "decyzja freelancera"** → zleceniodawca już wybrał (ustawione z góry) → **NIE klikamy niczego** w prawa autorskie

**Przyciski po kolei:**
1. **"Przejdź do podsumowania"** – po wypełnieniu pól
2. **"Wyślij"** – potwierdzenie wysyłki
3. Potwierdzenie sukcesu: tekst "Oferta wysłana do zleceniodawcy"
4. Po wysłaniu oferta w magazynie dostaje status **"wysłano ofertę"**; później **ręcznie** odznaczamy
   **"odpowiedzieli" / "nie odpowiedzieli"** (do badań)

**Uwaga (protokół bezpieczeństwa ze starego programu):** jeśli zlecenie jest młodsze niż ~5 minut od publikacji – poczekać, aż minie, zanim wysyłać ofertę.

---

## Schemat całego procesu

```
START
  │
  ▼
[Krok 1] Wejście na 2 linki kategorii → pobranie HTML z listą ofert
  │
  ▼
[Krok 2] Marker → sprawdzenie które oferty są nowe (1-10 sztuk)
  │
  ▼
[Krok 3] AI #1 → selekcja: które oferty pasują? → lista wybranych
  │
  ▼
[Krok 4] Playwright → dla każdej wybranej: wejdź, kliknij "pokaż pełny opis", pobierz pełne dane
  │
  ▼
[Krok 5] ŁAŃCUCH AI (do 20 slotów) → dla każdej oferty:
  ├── 02b: wycena + dni
  ├── 02a: treść oferty
  └── 03-20: walidatory (opcjonalne)
  │
  ▼
[Krok 6] WERYFIKACJA (człowiek) → zatwierdź / edytuj / odrzuć
  │
  ▼
[Krok 7] Playwright → kliknij "Dodaj ofertę", wypełnij formularz, wyślij
  │
  ▼
KONIEC
```

---

## Pliki konfiguracyjne (do edycji przez użytkownika)

| Plik | Do czego służy |
|---|---|
| `prompts/prompt_ai1.md` | Wytyczne dla AI #1 – jakie oferty wybierać |
| `prompts/agent_02a_opis_oferty.md` | AI #2a – jak pisać treść propozycji |
| `prompts/agent_02b_wycena_dni.md` | AI #2b – jak wyceniać i ustalać dni |
| `prompts/agent_XX_*.md` | Slot XX (03-20) – własne walidatory (opcjonalne) |
| `prompts/lore.md` | Dodatkowy kontekst dla AI (umiejętności, portfolio) |
| `chain_config.json` | Konfiguracja slotów – które aktywne, kolejność, retry |

Te pliki mają być **łatwe do edycji** – użytkownik może je zmieniać w każdej chwili bez grzebania w kodzie.