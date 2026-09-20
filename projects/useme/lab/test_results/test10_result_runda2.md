# Test 10 – Wynik (Runda 2)

**Status:** ✅ (częściowy sukces – evaluate+fetch działa dla detali, zawodzi dla listy)
**Data:** 2026-08-06 15:35
**Skrypt:** `lab/test10_flow_v2/test10_flow_v2.py`

---

## Podsumowanie flow

| Krok | Opis | Status | Szczegóły |
|------|------|--------|-----------|
| 0 | Playwright init | ✅ | Firefox, headless=False |
| 1 | Warmup (useme.com) | ✅ | page.goto, wait 5s |
| 2 | Lista (evaluate+fetch) | ⚠️ Fallback | evaluate+fetch = `Execution context was destroyed`; użyto fallback HTML z test01 |
| 3 | Marker | ✅ | NOWE (pierwsze uruchomienie) |
| 4 | AI Selekcja #1 | ✅ | 5 wybranych, 5 odrzuconych (DeepSeek działa) |
| 5 | Detale (evaluate+fetch) | ⚠️ Częściowo | 5/5 pobrano HTML, ale parser dał `"?"` dla wszystkich pól |
| 6 | AI Propozycje #2 | ⚠️ Generyczne | 5/5 wygenerowanych, ale przez brak danych z detali – propozycje bardzo ogólne |
| 7 | Zapis wyników | ✅ | `flow_v2_results.json` |

**Czas całkowity:** ~119 sekund (15:33:12 → 15:35:11)

---

## Kluczowe odpowiedzi

### 1. Czy flow działa z evaluate?

**Częściowo.** Dla detali ofert `page.evaluate()` + `fetch` działa – pobiera HTML (5920–6047 bajtów).  
Dla listy ofert **NIE działa** – `page.evaluate()` rzuca `Execution context was destroyed, most likely because of a navigation`.  
Powód: po `page.goto('https://useme.com/')` wykonuje się przekierowanie na `https://useme.com/en/` (widoczne w logach – URL warmupu to `/en/`), co niszczy kontekst wykonania. Trzeba poczekać aż nawigacja się całkowicie zakończy przed wywołaniem evaluate.

### 2. Ile ofert sparsowano z listy?

**10 ofert** (fallback do HTML z test01, ponieważ evaluate+fetch zawiodło).

### 3. Ile ofert wyselekcjonował AI #1?

**5 wybranych, 5 odrzuconych** (DeepSeek zadziałał prawidłowo).  
Wybrane: Automatyzacja Make/n8n/Python, Platforma AI, API Allegro, Integrator Optima-Base.com, Automatyzacja procesów i AI.

### 4. Ile propozycji wygenerował AI #2?

**5/5 wygenerowanych**, ale wszystkie są **bardzo generyczne** – proszą o doprecyzowanie, nie odnoszą się do konkretnych zleceń.  
Powód: parser detali nie rozpoznał struktury HTML szczegółów – wszystkie pola `title`, `full_desc`, `category`, `published` to `"?"`.

### 5. Czy AI #2 pomyliło kontekst?

**Nie pomyliło kontekstu w sensie mieszania ofert ze sobą** (bo wysyłano jedną ofertę na raz).  
Ale przez to, że dane wejściowe były puste (wszystkie pola `"?"`), AI generowało bezpieczne, ogólne odpowiedzi.

---

## Przykładowe propozycje (2 z 5)

| # | Tytuł oferty (z listy) | Propozycja (skrót) | Stawka |
|---|----------------------|-------------------|--------|
| 1 | Automatyzacja Make/n8n/Python: web scraping, OCR i AI | "Dzień dobry, zainteresowałem się Pana/Pani zleceniem dotyczącym programowania w Pythonie. Chociaż opis jest na tym etapie bardzo ogólny, chętnie podejmę się realizacji po doprecyzowaniu wymagań..." | 90 PLN/h netto |
| 2 | Stworzenie Inteligentnej Platformy AI do Zakupu | "Dzień dobry, Anno. Z zainteresowaniem przejrzałem Pani ogłoszenie, jednak zauważyłem, że w tytule i opisie brakuje jeszcze szczegółowych informacji o zakresie prac..." | 100 zł/h netto |

📌 W obu przypadkach AI nie wie o czym jest oferta – propozycje są poprawnym placeholderem, ale **bezużyteczne komercyjnie**. W przeciwieństwie do rundy 1, gdzie AI #2 myliło kontekst (oferta o AI dostała propozycję o PDF-ach), tutaj problem jest odwrotny – AI nie dostało żadnego kontekstu z detali.

---

## Porównanie z rundą 1 (test06)

| Aspekt | Runda 1 (test06) | Runda 2 (test10) |
|--------|-----------------|-----------------|
| Pobieranie listy | page.goto → ✅ | evaluate+fetch → ❌ (fallback) |
| Pobieranie detali | page.goto → ✅ (5/5) | evaluate+fetch → ✅ pobrane, ❌ sparsowane |
| Parsowanie detali | ✅ poprawne (tytuły, opisy, budżety) | ❌ wszystkie pola = "?" |
| AI #1 (selekcja) | ✅ 5/5 | ✅ 5/5 (takie same oferty) |
| AI #2 (propozycje) | ⚠️ 5/5, ale #2 pomyliło kontekst (PDF zamiast AI) | ⚠️ 5/5, ale wszystkie generyczne (brak danych) |
| Czas wykonania | ~161 sekund | ~119 sekund |
| Cloudflare | ⚠️ blokował headless (drugie podejście OK) | ✅ headless=False działa |

---

## Problemy zidentyfikowane

### 🔴 Krytyczne
1. **evaluate+fetch dla listy nie działa po przekierowaniu** – `page.goto` na `useme.com` przekierowuje na `/en/`, niszcząc execution context. Rozwiązanie: albo `page.goto` bezpośrednio na stronę listy przed evaluate, albo czekać na `networkidle` przed evaluate.

2. **Parser detali nie działa na HTML z evaluate+fetch** – selektory `h1`, `div.offer-content`, `div.job-description` nie trafiają w strukturę. HTML z evaluate+fetch ma inną strukturę niż z page.goto (prawdopodobnie fetch zwraca surowy HTML serwera przed renderowaniem JS). Trzeba dostosować selektory.

### 🟡 Średnie
3. **Propozycje AI #2 są bezużyteczne** – przez brak danych z detali. To bezpośrednia konsekwencja problemu #2.

### 🟢 Drobne
4. **Propozycja #3 zawiera placeholder `[Twoje Imię]`** – AI nie zostało poinstruowane o podpisie.

---

## Pliki wygenerowane

| Plik | Ścieżka |
|------|---------|
| Skrypt | `lab/test10_flow_v2/test10_flow_v2.py` |
| Wyniki | `lab/test10_flow_v2/flow_v2_results.json` |
| Lista HTML | `lab/test10_flow_v2/intermediate/list_page_evaluate.html` |
| Parsowane oferty | `lab/test10_flow_v2/intermediate/parsed_offers.json` |
| Selekcja AI | `lab/test10_flow_v2/intermediate/ai_selection.json` |
| Propozycje AI | `lab/test10_flow_v2/intermediate/ai_proposals.json` |
| Detale (×5) | `lab/test10_flow_v2/intermediate/details/detail_*.json` |
| Marker | `lab/test10_flow_v2/last_offer.txt` |

---

## Wnioski

1. **evaluate+fetch jako zamiennik page.goto** – działa dla podstron (detali) gdy już jesteśmy na tej samej domenie, ale NIE działa bezpośrednio po page.goto z przekierowaniem. Trzeba albo użyć `page.goto` na stronę listy przed evaluate, albo czekać na pełne załadowanie strony.

2. **Struktura HTML z fetch vs page.goto** – fetch zwraca surowy HTML serwera (bez renderowania JS), co oznacza że selektory CSS muszą być dostosowane do struktury server-side, nie client-side. W teście 06 parsowano HTML po pełnym renderowaniu (page.content()).

3. **AI #2 jedna-na-raz działa lepiej** – nie pomyliło kontekstu między ofertami (w przeciwieństwie do rundy 1). Problemem nie jest już mieszanie ofert, tylko brak danych wejściowych.

4. **Następne kroki** – poprawić evaluate+fetch dla listy (czekać na zakończenie nawigacji) i dostosować parser detali do struktury HTML z fetch.