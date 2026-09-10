# TEST 15 — FINAL FLOW v3 (TURA 3) — WYNIK

**Data:** 2026-08-06 | **Status: ✅ SUKCES (DRY RUN — NIC NIE WYSŁANO)**
**Skrypt:** `c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test15_final_flow\test15_final_flow.py`
**Wyniki JSON:** `c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test15_final_flow\final_flow_results.json`
**Uruchomienia:** 2 (drugie = pełny sukces + weryfikacja markera)

---

## 1. Tabela kroków — flow działa?

| # | Krok | Metoda | Wynik | Uwagi |
|---|------|--------|-------|-------|
| 0 | Init przeglądarki | Chromium + stealth + cookies, **headless=False** (fallback) | ✅ | headless=True **zablokowany przez Cloudflare** w obu uruchomieniach (3 próby × ~23 s); headless=False przechodzi za 1. próbą (0 CF) |
| 1 | Lista | `page.goto(domcontentloaded)` + wait 3 s + BeautifulSoup `article.job` | ✅ | **12 ofert**, CF=False, 1 próba (tryb widoczny) |
| 2 | L4 — evaluate+fetch na liście | `page.evaluate`+fetch PO zakończeniu nawigacji | ✅ | **status=OK, 12 ofert, IDENTYCZNE z page.goto** (`same_as_page_goto: True`). W test 10 tuż po goto nie działało (przekierowanie na /en/); po zakończonej nawigacji na poprawnym URL działa |
| 3 | Marker `last_offer.txt` | URL ostatniej oferty + porównanie przy 2. uruchomieniu | ✅ | Uruch. 1: `first_run` (12 nowych). Uruch. 2: `found` — marker znaleziony na pozycji 11, **nowych: 11** (oferty powyżej markera). Marker DZIAŁA |
| 4 | AI #1 — selekcja (DeepSeek) | `localhost:4570/v1/chat/completions`, model `deepseek-v4-pro` | ✅ | 3 wybrane / 8 odrzuconych (z 11 nowych). Czas ~63 s |
| 5 | Detale | `page.evaluate`+fetch → surowy HTML (~145–153 KB) → parser **JSON-LD (`JobPosting`) + CSS** | ✅ | **3/3 kompletne**, brak "?" w żadnym polu, zero CF na fetch (tryb widoczny) |
| 6 | AI #2 — propozycje | POJEDYNCZO, osobne wywołanie API na ofertę | ✅ | 3/3 wygenerowane, **konkretne** (patrz pkt 3), każda z `proposed_rate` + 2 `key_points` |
| 7 | Zapis wyników | `final_flow_results.json` + `details_v3/` (raw HTML + JSON per detal) | ✅ | Kompletny zapis, `sent_anything: False` |

**Weryfikacja "nie wysyłania":** w flow nie ma żadnego kroku formularza/submisji — test kończy się na wygenerowaniu propozycji i zapisie do JSON.

---

## 2. Czy detale są kompletne (brak "?" w polach)?

**TAK — 3/3 detali kompletnych (`complete: True`), ZERO pól "?".**

| Detal (index) | Tytuł | Budżet | Kategoria | Autor | Opis |
|---|---|---|---|---|---|
| 0 | MVP - Agregator newsów z analizą AI | Do negocjacji | Programowanie i IT | Adrianna | pełny (~1400 zn.) |
| 3 | Automatyzacja Make/n8n/Python: web scraping, OCR i AI | Do negocjacji | Programowanie i IT | user042005 | pełny |
| 9 | Integrator pomiędzy Optima a Base.com | Do negocjacji | Programowanie i IT | michal.lubisz@strategyforge.pl | pełny |

- Źródło: **schema.org `JobPosting` w JSON-LD** (`script type="application/ld+json"`) obecne na każdym detalu → tytuł (`name`), opis (`description`), kategoria; autor z `hiringOrganization`/CSS; budżet z CSS/regex (na liście Useme budżety są często "Do negocjacji" — stąd wartość).
- Surowe HTML z evaluate+fetch: **pełna treść serwerowa (145–153 KB), bez Cloudflare** — mechanizm z testu 10/13 potwierdzony w trybie widocznym.
- ⚠️ Drobna uwaga produkcyjna: `full_desc` zawiera tagi HTML (`<p>...`) — w produkcji dodać strip tagów (jedno wywołanie BeautifulSoup). Nie blokuje AI.

---

## 3. Czy propozycje AI #2 są konkretne (nie generyczne)?

**TAK — 3/3 KONKRETNE.** Każda odwołuje się do szczegółów swojej oferty i podaje realną wycenę:

1. **MVP - Agregator newsów** → "zastosuję Scrapy/Playwright… dane zostaną znormalizowane i przesłane do infrastruktury chmurowej…", wycena **7 500–9 000 zł netto (130–150 zł/h, 50–60 h)**. Zwraca się do autora po imieniu ("Pani Adrianno").
2. **Automatyzacja Make/n8n/Python** → "Gmail API, Playwright do dynamicznych stron z wielokrotnymi przeklikaniami, Tesseract OCR (lub Google Vision) do skanów PDF/Word oraz Gemini API", wycena **4 500 zł netto (~30 h przy 150 zł/h)** + utrzymanie.
3. **Integrator Optima–Base.com** → "kluczowym wyzwaniem jest zmiana źródła danych z dokumentów **RO na WZ i RW-UB**… typowe dla procesów magazynowych w Optimie", wycena **140 zł/h (20–25 h = 3 000–3 500 zł)**.

Każda ma `proposed_rate` + `key_points` (2 szt.). Żadna nie zawiera ogólników typu "chętnie podejmę się realizacji".

---

## 4. Czas całkowity

- **Pełne uruchomienie (z failed headless + sukces widoczny): 220,9 s (~3,7 min)**
- Sam flow w trybie widocznym: **~150 s** (16:28:34 → 16:31:04)
- Struktura czasu: nawigacja + lista ~4 s | L4 ~0 s | AI#1 ~63 s | detale ~4 s | AI#2 ~79 s (3 × ~20–25 s)
- Czas AI dominuje; przy 3 ofertach to ~2,5 min.

---

## 5. POTWIERDZONY OSTATECZNY MECHANIZM (krok po kroku)

```
[START] Chromium + playwright-stealth + cookies.json
   │
   ├─ PRÓBA headless=True ──> jeśli CF (3 próby, ~70 s) ──> FALLBACK headless=False (widoczna)
   │
1. LISTA   page.goto(https://useme.com/pl/jobs/category/programowanie-i-it,35/, domcontentloaded)
           + wait 3 s (i ewentualne czekanie na auto-rozwiązanie CF ≤18 s)
           + BeautifulSoup(article.job) → tytuł, URL, autor, kategoria, budżet, opis (12 ofert)
   │
2. L4 (opcjonalne, diagnostyczne)
           page.evaluate + fetch(URL listy) PO zakończeniu nawigacji → ta sama lista (12/12 identyczne)
   │
3. MARKER last_offer.txt = URL OSTATNIEJ oferty
           przy następnym uruchomieniu: znajdź pozycję markera → bierzemy tylko oferty POWYŻEJ (nowsze)
           (potwierdzone: uruch. 2 → found@idx 11 → 11 nowych)
   │
4. AI #1 (DeepSeek localhost:4570/v1, deepseek-v4-pro)
           wysyłamy tytuły+budżet+opis+linki nowych ofert → wybiera 2-3 najwartościowsze (+uzasadnienia)
   │
5. DETALE (tylko dla wybranych)
           page.evaluate + fetch(URL detalu) → surowy HTML serwerowy (145-153 KB, bez CF)
           parser JSON-LD (JobPosting) + CSS → tytuł, opis, budżet, kategoria, autor
           zapis: details_v3/detail_{idx}.html + .json
   │
6. AI #2 (POJEDYNCZO — osobne wywołanie API na ofertę)
           prompt z PEŁNYMI danymi detalu → konkretna propozycja + proposed_rate + key_points
           twardy watchdog 150 s na wywołanie AI (daemon-thread) — flow nigdy nie zawiesza się
   │
7. [PRODUKCJA — NIE WYKONANO W TYM TESCIE] FORMULARZ
           otwórz URL detalu → wypełnij formularz oferty (propozycja AI #2) → SUBMIT
           (test 15 to DRY RUN — krok pominięty, nic nie wysłano)
   │
8. MARKER: zapis URL ostatniej przetworzonej oferty do last_offer.txt (przygotowanie pod następny cykl)
   │
[KONIEC] final_flow_results.json — pełny audyt (oferty, selekcja, detale, propozycje, porównanie L4)
```

---

## 6. Kluczowe ustalenia / ryzyka

1. **Cloudflare blokuje headless=True (AKTUALNIE)** — test 12 (headless=True, 3/3 bez CF) nie jest już powtarzalny dziś: headless=True = CF w 100% prób (2×3 próby), headless=False = 100% sukces. **OSTATECZNY STACK: Chromium + stealth + cookies + headless=False** (z auto-fallbackiem headless→widoczna w kodzie). Technika: `domcontentloaded` + 3 s + ewentualne czekanie na auto-rozwiązanie CF (≤18 s) + max 3 ponowienia goto.
2. **L4 potwierdzone**: evaluate+fetch działa na liście PO zakończeniu nawigacji (identyczne wyniki) — wcześniejsza porażka (test 10) była skutkiem redirectu na /en/ zaraz po goto, nie samej metody.
3. **Parser detali v3 (JSON-LD JobPosting + CSS) — działa na surowym HTML z evaluate+fetch** (3/3 kompletne). Zastępuje brakujący wynik testu 13.
4. **Marker URL-owy działa** (found@idx 11 → 11 nowych); zakłada listę "najnowsze na górze".
5. **AI#2 generuje konkretne propozycje z wycenami** przy dobrym prompcie (pełny opis + wymóg odniesienia do 2-3 szczegółów oferty).
6. ⚠️ DeepSeek potrafi przejściowo zawiesić się na pojedynczym żądaniu (raz zaobserwowano >6 min przy timeout 180 s w requests) — **obowiązkowy twardy watchdog** (daemon-thread + join z limitem) dodany i potwierdzony w działaniu.
7. ⚠️ Produkcja: `full_desc` z JSON-LD zawiera tagi HTML — strip przed podaniem do AI/formularza.

**Pliki do wglądu:** `final_flow_results.json`, `details_v3/` (raw HTML + JSON), `list_page_rendered.html` / `list_page_raw_fetch.html` (porównanie L4), `last_offer.txt`, `cookies.json` (kopia).
