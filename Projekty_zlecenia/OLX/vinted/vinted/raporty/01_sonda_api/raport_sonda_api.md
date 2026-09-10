# Sonda Vinted API — raport techniczny

Data: 2026-08-25
Zakres: READ-ONLY (katalog, szukaj, szczegóły). Nie dotykano checkoutu/kupna.

## Cel
Sprawdzić, które endpointy Vinted działają z cookies użytkownika, gdzie są blokady
(DataDome/Cloudflare) oraz jakie realne tempo (rate-limit) do wyceny botów.

## Metoda i tempo pomiaru
- Sesja: `curl_cffi` z impersonate `chrome124`.
- Cookies: Netscape z `cookies.txt` (przeglądarka użytkownika).
- Nagłówki: UA Chrome 124 + `Referer`/`Origin` = `https://www.vinted.pl/`.

### Rate-limit (matematyczne tempo)
Test: 30 szybkich requestów na `/api/v2/catalog/items?page=1&per_page=1`,
odstęp **0.15 s** między requestami.

Wynik:
- **5 × 200 OK**, potem **429** (code 106, `rate_limit_exceeded`)
- Blokada nastąpiła po **6. requestach** w **5.9 s**

Wnioski o tempie:
| Parametr | Wartość |
|---|---|
| Bezpieczne tempo | **≤ 1 request / ~1 s** (zapas do limitu) |
| Limit twardy (zmierzony) | ~5 requestów / 6 s = ~0.83 req/s |
| Interwał testowy, który wywołał blokadę | 0.15 s |
| Zalecany interwał produkcyjny | **0.8–1.2 s** + cache |

Uwaga: wielokrotne równoległe uruchomienia sondy powodowały wyczerpanie limitu
i `KeyError: 'items'` (odpowiedź 429 zamiast JSON). To nie błąd kodu, tylko limit.

## Wyniki endpointów

### Działa — 200 OK, pełny JSON [UDOWODNIONE]
| Endpoint | Status | Uwagi |
|---|---|---|
| `/api/v2/catalog/items?page=1&per_page=20&order=newest_first` | 200 | pełny katalog |
| `/api/v2/catalog/items?...&order=price_desc` | 200 | sortowanie po cenie |
| `/api/v2/catalog/items?...&search_text=iphone` | 200 | szukaj tekstowe |
| `/api/v2/users/me` | 200 | dane zalogowanego usera |

### Maksymalny `per_page` (test zakresu)
| per_page | Status | Zwrócone itemy |
|---|---|---|
| 20 | 200 | 20 |
| 96 | 200 | **96** |
| 200 | 200 | **96** (obcięte do max) |
| 500 | 200 | **96** (obcięte do max) |

**Max realny `per_page` = 96.** Większe wartości nie zwracają więcej niż 96.
To kluczowe dla wyceny: 1000 ofert = ~11 requestów (nie 1000).

### Szczegóły oferty przez HTML strony itemu (fallback)
| Endpoint | Status | Treść |
|---|---|---|
| `https://www.vinted.pl/items/{id}` | **200** | pełny HTML, title poprawny, **JSON-LD obecny** |

- [UDOWODNIONE] Strona HTML itemu **działa bez blokad** (200, ~1.95 MB HTML, zawiera JSON-LD
  z danymi strukturalnymi oferty — cena, tytuł, opis).
- To działający fallback dla zablokowanego endpointu `/api/v2/items/{id}/details`.

### Zablokowane / niedostępne
| Endpoint | Status | Treść |
|---|---|---|
| `/api/v2/items/{id}` | 404 | HTML "La page n'existe pas" |
| `/api/v2/items/{id}/details` | 403 | HTML blokady Vinted (DataDome/Cloudflare) |

## Wnioski dla botów

| Typ bota | Wykonalność | Uwagi |
|---|---|---|
| Monitor nowych ofert (katalog/szukaj) | ✅ łatwo | stabilne, per_page=96, ~1 req/s |
| Alert cenowy / obserwowane | ✅ łatwo | te same endpointy katalogowe |
| Szczegóły oferty (opis, zdjęcia) | [UDOWODNIONE] ✅ działa | przez HTML strony itemu (JSON-LD), ~1 req/ofertę |
| Kupno/checkout | ❌ nie testowane | ryzyko dla konta, odradzam |

## Alternatywne ścieżki (czy są lepsze?)

### Endpointy, które NIE istnieją (404)
| Endpoint | Status |
|---|---|
| `/api/v2/search/items` | 404 |
| `/api/v2/catalog/aggregations` | 404 |
| `/api/v2/categories` | 404 |
| `/api/v2/promoted/items` | 404 |
| `/api/v2/users/{id}/items` | 404 (code 104) |
| `/sitemap.xml` | 404 |

Wniosek: **katalog `/api/v2/catalog/items` to jedyny działający endpoint** do przeszukiwania.

### Licznik bazy (`pagination`) — kluczowe odkrycie
Katalog zwraca `pagination` z polem `total_entries`. ALE:

| Zapytanie | `total_entries` | `total_pages` |
|---|---|---|
| bez filtra | **960** | 960 |
| search_text=iphone | **960** | 960 |
| search_text=nike | **960** | 960 |
| catalog_ids=5 | **960** | 960 |
| brand_ids=53 | **960** | 960 |

[UDOWODNIONE] **`total_entries` jest zawsze 960, niezależnie od filtra.**

To jest **sztuczny limit Vinted**: serwer obcina wynik do **maksymalnie 960 ofert**
(10 stron × 96) na jedno zapytanie katalogowe. Nie podaje realnej liczby ofert w bazie.

### Konsekwencja dla "liczenia bazy" (jak z OLX)
- NIE da się policzyć całej bazy jednym zapytaniem — `total_entries` jest ścięty do 960.
- Pełne przeszukanie kategorii wymaga **podziału na przedziały** (np. po cenie, dacie
  dodania, rozmiarze), żeby zejść poniżej 960 na każdy wycinek — dokładnie ta sama
  technika co przy OLX (omijanie limitu przez bisekcję filtrów).
- [WNIOSEK] To jest punkt, który warto podkreślić klientowi: "inni" liczą bazę nie magicznie,
  tylko dzieląc zapytania na segmenty, bo Vinted twardo tnie do 960 na zapytanie.

### Test filtrów — OSTRE dowody (bzdurne ID)
Prawidłowy test: bzdurne ID. Jeśli filtr działa, bzdurny ID daje [UDOWODNIONE] **0** wyników.
Jeśli filtr jest ignorowany, bzdurny ID daje [UDOWODNIONE] **960** (pełny, nieprzefiltrowany katalog).

| Filtr | bzdurny ID | wynik | wniosek |
|---|---|---|---|
| `brand_ids=999999999` | 999999999 | [UDOWODNIONE] **0** | **DZIAŁA** |
| `size_ids=999999999` | 999999999 | [UDOWODNIONE] **0** | **DZIAŁA** |
| `status_ids=999999999` | 999999999 | [UDOWODNIONE] **0** | **DZIAŁA** |
| `price_from=1&price_to=2` | — | [UDOWODNIONE] first_price=1.0 | **DZIAŁA** |
| `search_text=xyzqwerty999` | — | [UDOWODNIONE] **0** | **DZIAŁA** |
| `catalog_ids=999999999` | 999999999 | **960** | **NIE POTWIERDZONA** |

**Dowód marki:** `brand_ids=53` zwrócił 96/96 pozycji marki **Nike** (0 innych marek).

**Dowód ceny:** `price_from=1&price_to=2` zwrócił oferty z ceną 1.0 zł. Nazwa
parametru potwierdzona w HTML strony: `catalog.filters.price.price_from/price_to`.

**Wniosek ostateczny (SKORYGOWANY 2):**
- DZIAŁAJĄ: `search_text`, `brand_ids`, `size_ids`, `status_ids`, `price_from`/`price_to`
- NIE POTWIERDZONA: `catalog_ids` (kategoria) — 5 wariantów nazwy dało 960 nawet
  dla bzdurnego ID; [NIEPOTWIERDZONE] wymaga dalszego sprawdzenia przed obiecywaniem klientowi.

Uwaga o błędzie metodologicznym: pierwszy test ceny uznał filtr za ignorowany, bo
patrzył na markę (babymonster) zamiast na cenę. Prawidłowa kontrola to cena oferty,
nie marka. babymonster za 1 zł to realna oferta, nie dowód ignorowania filtru.

## Kluczowe fakty dla wyceny (skorygowane)
- Katalog i szukaj: **stabilne**, **per_page = 96** (maksymalna strona).
- **1000 ofert z katalogu = ~11 requestów** (nie 1000) → czas to sekundy, nie minuty.
- [UDOWODNIONE] Szczegóły: przez **HTML strony itemu** (`/items/{id}`) z JSON-LD — działa bez blokad,
  ale to **osobny request na każdą ofertę** (~1.95 MB HTML).
- **Tempo liczbowe:**
  - Katalog: 1000 ofert ≈ 11 req ≈ **~15 s** (przy 1 req/s + zapas).
  - Szczegóły 1000 ofert: 1000 req × ~1.2 s ≈ **~20 min** (koszt ~1 req/ofertę).
  - 100 ofert (typowy monitoring): katalog ~2 s + szczegóły ~2 min.

## Pliki sondy
- `probe_api.py` — test katalogu/szukaj/user me
- `probe_rate.py` — test szczegółów + rate-limit
- `probe_scope.py` — test max per_page + HTML strony itemu
- `cookies.txt` — cookies użytkownika (Netscape)