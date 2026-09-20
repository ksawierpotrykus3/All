# Tech Stack – co używamy

> Decyzje technologiczne na podstawie rozmowy z seniorem Maksem i własnych ustaleń.

---

## TL;DR (dla nietechnicznego)

- Piszemy w **Pythonie** (język programowania)
- Do otwierania strony używamy **Playwright + Chrome + stealth** (z cookies zalogowanej sesji) – sprawdzone w rundzie 2, że działa najlepiej
- Do wyciągania danych z HTML używamy **BeautifulSoup** (biblioteka do parsowania stron)
- AI to **DeepSeek V4 Pro** – działa lokalnie na Twoim komputerze
- Na razie wszystko lokalnie na Windows, bez Dockera

---

## Szczegóły

### Język: Python
- Wersja: 3.10+ (najlepiej 3.12)
- Dlaczego: senior polecił, łatwy do scrapingu i AI

### Przeglądarka / stealth: Playwright + Camoufox + Firefox

**Czego używać według seniora Maksa:**
- **Playwright** – narzędzie do automatyzacji przeglądarki (otwiera stronę, klika, czyta)
- **Camoufox** – dodatek do Playwright, który pomaga ukryć, że to bot (anty-detekcja)
- **Firefox** – silnik przeglądarki (nie Chrome!) – Firefox jest trudniejszy do wykrycia przez Cloudflare niż Chrome

Dlaczego nie Chrome: senior mówi "chrome to za mało" – Cloudflare lepiej wykrywa automatyzację na Chromie.

### Parsowanie HTML: BeautifulSoup
- Biblioteka do wyciągania danych ze struktury strony
- Alternatywy: parsel, lxml (można użyć zamiennie)
- Działa na surowym HTML pobranym przez Playwright

### AI: DeepSeek V4 Pro (lokalny)

**Endpoint:** `http://localhost:4570/v1`
- Model działa lokalnie na Twoim komputerze
- Jest darmowy (przeglądarkowy)
- **Lokalizacja paczki proxy AI:** `c:\Users\Ksawier\Pictures\Screenshots\deepseek-proxy-clean\proxy_pakiet` (start przez `start.bat`; to NIE jest główne proxy do kodowania). Szczegóły: `AI_INTEGRACJA.md` → sekcja „Lokalizacja gotowej paczki proxy DeepSeek (AI)".
- Kompatybilny z API OpenAI (czyli używamy biblioteki `openai` z Python, tylko wskazujemy na localhost)
- **UWAGA:** DeepSeek V4 Pro to model tekstowy – NIE obsługuje obrazów/wizji
  - Dlatego NIE robimy screenshotów stron
  - Wszystkie dane wyciągamy jako tekst z HTML

### Środowisko: Windows lokalnie
- Na razie **bez Dockera** (nie wiesz jeszcze co to, więc zostajemy na Windows)
- Wszystko działa lokalnie na Twoim komputerze
- W przyszłości można rozważyć Dockera (środowisko izolowane) – senior sugerował Ubuntu + Xvfb do lepszego udawania przeglądarki

---

## Lista bibliotek (do zainstalowania przez `pip`)

```
playwright          # automatyzacja przeglądarki
camoufox            # stealth / anty-detekcja dla Playwright
beautifulsoup4      # parsowanie HTML
lxml                # szybki parser dla BeautifulSoup
openai              # komunikacja z DeepSeek (kompatybilne API)
httpx               # zapytania HTTP (opcjonalnie)
python-dotenv       # zarządzanie zmiennymi środowiskowymi (hasła itp.)
```

---

## Sprawdzone w labie (wyniki testów 01-06, 2026-08-06)

### Co działa ✅
- **Playwright + Camoufox + Firefox (headless)** – strona kategorii ładuje się, Cloudflare czasem przepuszcza (status 200, ~20 elementów ofert na stronie)
- **BeautifulSoup** – parsowanie listy ofert działa w 100%: 10/10 ofert wyciągniętych poprawnie
- **DeepSeek V4 Pro** (`deepseek-v4-pro` na `localhost:4570/v1`) – działa, odpowiada poprawnie
- Dodatkowy model dostępny: `deepseek-vision` (może być przydatny w przyszłości)

### Znalezione selektory CSS (działające)
| Element | Selektor |
|---|---|
| Kontener oferty | `article.job` |
| Tytuł + link | `a.job__title-link` |
| Autor | `div.job__headline strong` |
| Avatar | `div.user_avatar` (klasa `user_avatar__default-image` = brak avatara) |
| Liczba ofert | `div.job__header-details--offers span:last-child` |
| Wygaśnięcie | `div.job__header-details--date span:last-child` |
| Kategoria | `div.job__category a p` |
| Budżet | `span.job__budget-value` |
| Opis | `div.job__content p` |
| Tytuł szczegółów | `h1` |
| Przycisk "Dodaj ofertę" | `a:has-text("Dodaj ofertę")`, `button:has-text("Dodaj ofertę")` |

### Problemy / uwagi ⚠️
- **Cloudflare blokuje Playwright headless NIESTABILNIE** – raz blokuje ("Just a moment..."), raz przepuszcza. Test 03 był zablokowany, test 06 za drugim podejściem przeszedł.
- **Rozwiązanie awaryjne:** WebFetch (pobieranie HTML bez przeglądarki) omija Cloudflare, ale zwraca markdown, nie surowy HTML – nie działa z selektorami CSS. Tylko jako referencja.
- **Baner cookies** (`#cookiescript_accept`) blokuje kliknięcia – trzeba go usunąć przez JS. Potwierdzone w turze 3 (test 15, widoczna przeglądarka): baner się pojawia, trzeba kliknąć akceptuj.
- "pokaż pełny opis" nie zawsze istnieje – w teście 03 cały opis był widoczny od razu. Selektor opcjonalny.
- Do dalszej pracy: rozważyć `headless=False` + prawdziwy profil Firefox z cookies (zgodnie z planem KONTA.md), albo Playwright-stealth.

### Instalacja (sprawdzone)
```
python -m pip install playwright camoufox beautifulsoup4 lxml openai
playwright install firefox
```
Uwaga: `openai` trzeba instalować przez `python -m pip`, zwykłe `pip install` nie działało.

---

## Nowa strategia seniora (2026-08-06) – evaluate same-origin + JSON

### Problem
`page.goto()` / `page.navigate()` na każdej ofercie **czasem triggerują anti-bot**,
bo Cloudflare rozpoznaje, że to nie są prawdziwe kliknięcia kursorem.

### Rozwiązanie seniora (do przetestowania)
1. **Warmup:** pokaż pełną przeglądarkę (nie headless), wejdź na stronę główną useme.com
2. Potem **wszystko przez `page.evaluate()`** z kontekstu tej samej przeglądarki (same origin)
3. Lekkie JS – fetch/navigacja w kontekście strony, nie przez `page.goto`
4. Senior potwierdza: na Cardmarket Cloudflare **puszcza to normalnie** i zwiększa
   liczbę stron bez kolejnego challenge

### Wyniki rundy 2 (2026-08-06) – co potwierdzone
1. **Warmup + evaluate+fetch → 0/5 blokad Cloudflare** ✅ (strategia seniora działa, test 07)
2. **JSON API nie istnieje** ❌ – wszystkie 8 wariantów z `Accept: application/json` → HTTP 403 Cloudflare. **Zostajemy przy HTML + BeautifulSoup.** (test 08)
3. **evaluate+fetch NIE działa na liście tuż po `page.goto`** – przekierowanie na `/en/` niszczy execution context. Trzeba poczekać na koniec nawigacji przed evaluate. (test 10, rozwiązane w turze 3: działa PO zakończeniu nawigacji)
4. **Formularz `/offer/start/` za Cloudflare Turnstile** – bez zalogowanej sesji (cookies) DOM formularza jest niedostępny. URL potwierdzony. (test 11)
5. **Stary mechanizm (Chrome + stealth + cookies.json) wygrywa** w porównaniu headless (0 vs 1 realnych blokad CF), ale test porównywał nierówne warunki (stary miał cookies, Firefox nie) – **rozstrzygnięte w turze 3: decyduje stealth, nie cookies**. (test 09 → test 12)
6. **AI #2 wysyłane pojedynczo NIE myli kontekstu** ✅ (problem z rundy 1 rozwiązany) – ale przy braku danych z detali generuje generyczne propozycje.

### Zalecany stack po rundzie 2 (wstępnie)
- **Chromium + playwright-stealth + cookies.json** (stary mechanizm) jako główny
- **Firefox** jako fallback
- Lista: `page.goto` (lub evaluate po czekaniu na nawigację) + BeautifulSoup
- Detale: `page.evaluate` + fetch + parser dostosowany do surowego HTML
- Formularz: wymaga cookies (zalogowana sesja) – Turnstile
- *(ZASTĄPIONE przez OSTETECZNY MECHANIZM poniżej – wyniki tury 3)*

---

## OSTETECZNY MECHANIZM (tura 3, test 15 – AUTORYTATYWNY, 2026-08-06)

Test 15 potwierdził działający pełny flow (12 ofert → 3 wybrane → 3 detale → 3 propozycje, ~220 s).
To jest ostateczny stack, na którym budujemy mechanizm:

### Stack
- **Chromium + playwright-stealth + cookies.json + headless=False** (widoczna przeglądarka)
- **Auto-fallback:** najpierw próba `headless=True` (3 próby, ~70 s) → jeśli CF blokuje → `headless=False` (widoczna, 100% sukces)
- **WAŻNE:** headless=True przestał działać (test 12: 0/3 blokad → test 15: 100% blokad tego samego dnia!). Cloudflare jest niestabilny w czasie → widoczna przeglądarka to pewnik.
- `wait_until="domcontentloaded"` + `wait_for_timeout(3000)` + czekanie na auto-rozwiązanie CF (≤18 s)

### Kroki (potwierdzone)
1. **Lista:** `page.goto(URL kategorii)` + BeautifulSoup(`article.job`) → 12 ofert (tytuł, URL, autor, kategoria, budżet, opis)
2. **evaluate+fetch na liście:** działa PO zakończeniu nawigacji (identyczne wyniki jak page.goto) – nie działać tuż po goto (redirect /en/)
3. **Marker:** `last_offer.txt` = URL ostatniej oferty → przy kolejnym uruchomieniu bierzemy tylko oferty POWYŻEJ markera (nowsze)
4. **AI #1 (DeepSeek):** selekcja ofert (deepseek-v4-pro na localhost:4570/v1)
5. **Detale:** `page.evaluate` + fetch(URL detalu) → surowy HTML serwerowy (~145-153 KB) → **parser JSON-LD (schema.org JobPosting) + CSS `.jobs-summary__item`** → kompletne 3/3
6. **AI #2:** POJEDYNCZO (osobne wywołanie na ofertę) + **twardy watchdog 150 s** (DeepSeek potrafi zawiesić się >6 min!)
7. **Formularz:** ✅ **ROZWIĄZANY testem 16** – NIE wysłano w testach, ale formularz otwiera się w pełni w widocznym trybie (patrz "Problemy otwarte" poniżej – **Turnstile NIE blokuje**)

### Problemy otwarte (z tury 3)
- ✅ **Formularz `/offer/start/` – ROZWIĄZANY testem 16 (2026-08-06)!** Prawdziwy URL: `https://useme.com/pl/jobs/{ID}/offer/start/` (z linku "Dodaj ofertę"; root `/offer/start/` = 404). W widocznej przeglądarce (headless=False) + cookies otwiera się w pełni – **Turnstile NIE blokuje** (test 14 w headless mylił). Pola potwierdzone: `#id_description`, `#id_payment` (Wycena), `#id_work_days` (Dni pracy, min 7), radio `copyright_transfer` (license/protocol/without), `button[type=submit]` "Przejdź do podsumowania". Schemat: `lab/test_results/test16_result.md` i `lab/test16_formularz_schema/form_schema.json`. **Uwaga: formularz przywraca szkic z konta – nadpisywać pola.**
  - Solver Turnstile od Bartka (`tech/turnstile_solver.py`) NIE jest już potrzebny do otwarcia formularza – może się przydać tylko awaryjnie. Status: notatka, bez zmian.
- ⚠️ **JSON-LD `full_desc`** zawiera tagi HTML (`<p>`) – strip przed podaniem do AI/formularza
- ⚠️ **Baner cookies** `#cookiescript_accept` – kliknąć akceptuj przy starcie (potwierdzone w widocznej przeglądarce)
- ⚠️ **Detale:** `page.evaluate`+fetch na detalu = 403 CF w headless; działa tylko w trybie widocznym

### Parser JSON-LD (test 13, gotowy kod w lab/test13)
- Źródło 1: `script[type="application/ld+json"]` @type=JobPosting (title, description, baseSalary, author, datePosted, validThrough)
- Źródło 2: `.jobs-summary__item` (Kategoria, Zleceniodawca, Opublikowano, Prawa autorskie, Ważne przez)
- Umiejętności: NIE MA na detalu zlecenia (tylko w ofertach wykonawców) → celowo puste

### Instalacja (sprawdzone)
```
python -m pip install playwright playwright-stealth beautifulsoup4 lxml
playwright install chromium
```
Uwaga: `openai` trzeba instalować przez `python -m pip`, zwykłe `pip install` nie działało.
Uwaga 2: `wait_until="networkidle"` powoduje timeouty na Useme (WebSocket/SSE) – używać `domcontentloaded` + `wait_for_timeout(3000)`.

---

## Czego NIE używamy (na razie)

- ❌ Docker – za skomplikowane na start
- ❌ Linux/Xvfb – zostajemy na Windows
- ❌ Selenium – Playwright jest nowszy i lepszy
- ❌ **Camoufox/Firefox jako główny stack** – Chromium+stealth wygrywa (tura 3)
- ❌ Screenshoty/OCR – DeepSeek nie obsługuje wizji
- ❌ JSON API Useme – nie istnieje (Cloudflare 403 na wszystko z Accept: application/json)

---

## Narzędzia do czystego kodu (OD PÓŹNIEJ – senior Maks)

> To jest NOTATKA NA PÓŹNIEJ, gdy zaczniemy pisać właściwy mechanizm.
> NIE instalujemy tego teraz – na razie tylko zapisujemy listę, żeby nie zapomnieć.

Senior używa tego zestawu do utrzymania jakości kodu Pythona:
- **ruff** – sprawdza styl kodu + "basepyright" (kontroler typów)
- **radon** – wykrywa zbyt skomplikowane funkcje (kandydaci do refaktoryzacji)
- **vulture** – wykrywa martwy kod (nieużywane funkcje/zmienne)
- **refurb** – podpowiada nowocześniejsze sposoby pisania
- **xenon** – pilnuje progu złożoności (wywala się gdy kod za skomplikowany)
- **scalene** – profiluje szybkość (kiedy coś działa za wolno)
- **mutmut** – testuje, czy nasze testy faktycznie coś łapią (mutacje)
- ~~vcrpy~~ – senior go **odradza** (nagrywa odpowiedzi API do testów – nie chcemy)

**Jak senior tego używa (po ludzku):** podłącza te narzędzia jako "pre-commit hook" –
czyli gdy AI chce zapisać/zatwierdzić kod (commit), narzędzia automatycznie przechodzą
przez kod i "krzyczą" (wyświetlają błędy) zanim kod zostanie zapisany.

**Kiedy to wdrożymy:** po rundzie 2 testów, gdy zaczniemy pisać właściwy mechanizm.
Do tego czasu ta lista jest tylko notatką.

---

### cookies.json (kanoniczny)
- Lokalizacja: `tech/cookies.json` (skopiowany z `useme-ai-automation` po turze 3 + test 16)
- Zawiera sesję zalogowanego konta (sessionid + csrftoken) – NIE udostępniać, NIE commitować.
- Uwaga: sesja wygasa – gdy przestanie działać, trzeba wyeksportować nowe cookies z przeglądarki.