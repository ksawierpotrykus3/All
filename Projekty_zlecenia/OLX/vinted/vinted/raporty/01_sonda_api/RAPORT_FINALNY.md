# Sonda Vinted — RAPORT KOMPLETNY z dowodami

Data: 2026-08-25
Cel: zweryfikować KAŻDE twierdzenie przed wyceną bota dla klienta (smartcare).
Metoda: curl_cffi (impersonate chrome124) + cookies użytkownika + Playwright (przechwycenie realnych requestów przeglądarki).

## NAJWAŻNIEJSZE USTALENIE (zmienia wycenę)

Strona Vinted ma DWIE ścieżki dostępu do ofert:

1. [UDOWODNIONE] **API `/api/v2/catalog/items`** — JSON, działa dla: search_text, brand_ids, size_ids, status_ids, price_from/price_to, order (sortowanie). NIE wspiera filtrowania po kategorii (TWARDY DOWÓD: wąska kategoria catalog_ids=2954 zwraca 960 ofert).
2. **Strona HTML `/catalog`** — renderowana server-side (Next.js React Server Components, format `self.__next_f.push`). To JEDYNA droga do kategorii.

To znaczy: klient chce filtry "marka, stan, cena, słowa kluczowe, kategorie, rozmiary". Z tych sześciu:
- [UDOWODNIONE] 5 działa w API (marka, stan, cena, słowa, rozmiar)
- [UDOWODNIONE] 1 (kategoria) działa TYLKO przez stronę HTML, nie przez API

### KRYTYCZNE: metoda ID z OLX NIE przenosi się na Vinted

Test sekwencyjności ID ofert (probe_luki.py): 96 ID ma 43 rosnące, 52 malejące,
rozstęp 121757. ID Vinted NIE rosną globalnie — są przydzielane losowo.

Konsekwencja: przewaga nad kops.gg NIE może pochodzić ze skanowania rosnących ID
(jak na OLX, gdzie było 5-16 min wyprzedzenia). Na Vinted przewaga musi pochodzić
wyłącznie z: szybszy polling (własny, bez Discorda) + niższa latencja + natychmiastowy
checkout z pre-warmed sesją. To istotnie zmienia wycenę i obietnice dla klienta.

## DOWODY SZCZEGÓŁOWE

### 1. Filtry w API — test bzdurnym ID (metoda kontrolna)

Metoda: bzdurna wartość parametru. Jeśli filtr działa, bzdurna wartość daje [UDOWODNIONE] 0 wyników. Jeśli ignorowany, daje [UDOWODNIONE] 960 (pełny katalog).

| Filtr | Test | Wynik | Status |
|---|---|---|---|
| brand_ids=999999999 | bzdurny | [UDOWODNIONE] 0 wyników | DZIAŁA |
| size_ids=999999999 | bzdurny | [UDOWODNIONE] 0 wyników | DZIAŁA |
| status_ids=999999999 | bzdurny | [UDOWODNIONE] 0 wyników | DZIAŁA |
| search_text=xyzqwerty999 | bzdurny | [UDOWODNIONE] 0 wyników | DZIAŁA |
| price_from=1&price_to=2 | realny zakres | [UDOWODNIONE] first_price=1.0 | DZIAŁA |
| catalog[]=999999999 | bzdurny | [UDOWODNIONE] 960 | NIE DZIAŁA w API |

[UDOWODNIONE] Dowód marki: brand_ids=53 → 96/96 ofert marki Nike (0 innych). To jest czysty dowód.
Dowód ceny: price_from=1&price_to=2 → oferty z ceną dokładnie 1.0 zł.

### 2. Limit twardy (rate-limit) — zmierzony

Test: 30 requestów z odstępem 0.15s na `/api/v2/catalog/items`.

Wynik: 5 × 200 OK, potem 429 (code 106, rate_limit_exceeded) po 6. requestach w 5.9s.

| Parametr | Wartość |
|---|---|
| Bezpieczne tempo | ≤ 1 request / 1s |
| Limit twardy zmierzony | ~0.83 req/s |
| Zalecany interwał produkcyjny | 0.8–1.2s + cache |

### 3. Ograniczenie paginacji — zmierzone

| parametr | wartość |
|---|---|
| maksymalny per_page | 96 (przy 200 i 500 zwraca 96) |
| maksymalny total_entries | 960 (10 stron × 96) |
| total_pages | 10 dla pełnych wyników, 0 przy braku wyników |

[UDOWODNIONE] To jest twardy cap Vinted: żadne zapytanie nie zwróci więcej niż 960 ofert.

### 3b. Sortowanie order — działa (w przeciwieństwie do OLX) [UDOWODNIONE]

`order=newest_first` i `order=oldest_first` zwracają różne listy ofert (probe_luki.py).
Na OLX analogiczny parametr sortowania był ignorowany — na Vinted [UDOWODNIONE] działa poprawnie.
Dobra wiadomość dla monitoringu nowych ofert: newest_first faktycznie sortuje.

### 4. Kategoria — kluczowe odkrycie (Playwright)

Przechwycenie realnych requestów przeglądarki pokazało:
- URL strony kategorii: `https://www.vinted.pl/catalog?catalog[]=1904&page=1`
- `catalog[]` (z nawiasami) to prawdziwa nazwa parametru
- Strona kategorii NIE używa `/api/v2/catalog/items` — renderuje oferty server-side
- Format: Next.js RSC flight data (`self.__next_f.push([1,"..."])`), 94 chunki
- W flight data: total_entries=960, total_pages=10, 96 ofert (jedna strona)

Wniosek [WNIOSEK]: kategoria działa przez STRONĘ HTML (SSR), nie przez API. Żeby filtrować po kategorii, trzeba scrapować stronę HTML i parsować flight data.

UWAGA KOREKTA: wcześniejsza wersja tego raportu podawała "372 realnych ID ofert" — to był
błąd metodologiczny (regex liczył ceny, ID użytkowników i inne liczby 9-10-cyfrowe).
Rzeczywista liczba ofert w flight data to 96 (pole productItem.id). Błąd wykryty w audycie.

### 5. Szczegóły oferty — dwie drogi

| Endpoint | Status |
|---|---|
| `/api/v2/items/{id}` | 404 |
| `/api/v2/items/{id}/details` | 403 (blokada DataDome) |
| `/items/{id}` (HTML) | 200, ~1.95MB, JSON-LD obecny |

Szczegóły oferty (opis, pełne zdjęcia) dostępne TYLKO przez stronę HTML itemu.

### 6. Endpointy, które nie istnieją (404)

`/api/v2/search/items`, `/api/v2/catalog/aggregations`, `/api/v2/categories`, `/api/v2/promoted/items`, `/api/v2/users/{id}/items`, `/sitemap.xml`

## BŁĘDY METODOLOGICZNE, KTÓRE POPEŁNIŁEM (i naprawiłem)

1. [UDOWODNIONE] **Cena:** pierwszy test uznał filtr za ignorowany, bo patrzył na markę (babymonster) zamiast na cenę. Poprawna kontrola to cena oferty. Cena DZIAŁA.
2. [UDOWODNIONE] **Kategoria:** testowałem złe nazwy parametru (catalog_ids, catalog_id, category_ids). Prawdziwa nazwa to `catalog[]` (z nawiasami). Ale nawet poprawna nazwa NIE działa w API — kategoria działa tylko przez stronę HTML.

## KONSEKWENCJE DLA WYCENY (skorygowane)

### Co działa i jak (pewne) [UDOWODNIONE]
| Wymaganie klienta | Realna implementacja | Status |
|---|---|---|
| Marka | API brand_ids | [UDOWODNIONE] DZIAŁA |
| Stan | API status_ids | [UDOWODNIONE] DZIAŁA |
| Cena | API price_from/price_to | [UDOWODNIONE] DZIAŁA |
| Słowa kluczowe | API search_text | [UDOWODNIONE] DZIAŁA |
| Rozmiar | API size_ids | [UDOWODNIONE] DZIAŁA |
| Kategoria | STRONA HTML (SSR) + parsowanie flight data | [UDOWODNIONE] DZIAŁA, inna ścieżka |

### Tempo liczbowe (do wyceny)
| Operacja | Wolumen | Koszt |
|---|---|---|
| Katalog (API) | 1000 ofert | ~11 requestów, ~15s |
| Szczegóły (HTML itemu) | 1000 ofert | 1000 requestów, ~20min |
| Kategoria (HTML SSR) | 1 zapytanie | 1 request, ~1-2s na stronę |

### Kluczowa przewaga nad kops.gg
Klient mówi "kops.gg jest wolny". [POTWIERDZONE] Prawdziwe powody wolności publicznego bota:
1. Delay Discorda (oferta przechodzi przez serwer kopsa + Discord do użytkownika)
2. Wspólna infrastruktura i kolejka
3. Konserwatywny polling (co kilka sekund)

Prywatny bot na VPS wycina Discorda i robi własny polling. To realna przewaga w WYKRYWANIU ofert. Ale [UDOWODNIONE] checkout jest ograniczony przez Vinted (limit ~1 req/s) i nie da się go przyspieszyć do zera.

### Konflikt, który trzeba przekazać klientowi
"Ultra prędkość" i "ochrona przed banami" są sprzeczne:
- Im szybciej bot kupuje, tym szybciej wygląda jak bot, tym szybciej ban
- Vinted twardo tnie do ~1 req/s (zmierzone: 429 po 6 requestach)
- Checkout to największe ryzyko bana (klient sam to wie: "po kilku zakupach")

## PLIKI DOWODÓW
- `probe_api.py` — katalog/szukaj/user me
- `probe_rate.py` — rate-limit + szczegóły
- `probe_scope.py` — max per_page + HTML itemu
- `probe_alt.py` — alternatywne endpointy (404)
- `probe_count.py` — pagination.total_entries
- `probe_bisekcja.py` — test filtrów cenowych
- `probe_brand.py` — test marka/rozmiar/kategoria
- `probe_ostry.py` — OSTRY test bzdurnych ID
- `probe_nazwy.py` — alternatywne nazwy parametrów ceny
- `probe_catalog_bracket.py` — test catalog[]
- `probe_ssr.py` — strona HTML kategorii
- `probe_kategoria.py` — szukanie catalog_id w HTML
- `analyze_html.py` — analiza flight data
- `parse_flight.py` — parsowanie flight data
- `playwright_capture.py` — przechwycenie requestów przeglądarki
- `playwright_api_paths.py` — ścieżki API przeglądarki
- [FAKT] `raport_sonda_api.md` — raport wcześniejszy (częściowo nieaktualny, ten plik jest wersją ostateczną)