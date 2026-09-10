# Recon OLX — PRZEŁOM: API działa + podwójny system ID (2026-08-24)

## Dowód 16: Endpoint API wyszukiwarki DZIAŁA (przez WebFetch)

`https://www.olx.pl/api/v1/offers/` zwraca pełny JSON z listą ofert.

Struktura odpowiedzi (kluczowe pola):
- `data[]` — tablica ofert
- `data[].id` — **NUMERYCZNE id oferty** (np. `1093493751`)
- `data[].url` — pełny URL z alfanumerycznym ID (`...CID87-ID1c0bFZ.html`)
- `data[].title`, `created_time`, `last_refresh_time`, `valid_to_time`
- `data[].location.region.id` / `.name` — region (np. Małopolskie id=4, Śląskie id=6, Łódzkie id=7)
- `data[].category.id` — **inny system ID kategorii** (numeryczny wewnętrzny)
- `metadata.total_elements` — liczba zwróconych
- `metadata.visible_total_count` — **24 228 600** (całkowita liczba ofert!)

## Dowód 17: DWA SYSTEMY ID — numeryczny (API) i alfanumeryczny (URL)

| URL oferty | CID (URL) | category.id (JSON) | numeric id (JSON) |
|-----------|-----------|--------------------|--------------------|
| ...CID87-ID1c0bFZ.html (spodenki) | 87 (Moda) | 2940 | 1093493751 |
| ...CID99-ID17dp2e.html (kabel HDMI) | 99 (Telefony) | 2912 | 1022761686 |
| ...CID628-ID1818y4.html (pompa) | 628 (Dom i Ogród) | 1698 | 1034614712 |
| ...CID5-ID19wugD.html (Skoda) | 5 (Auta) | ? | 1056624375 |
| ...CID88-IDvkpUr.html (bluzka) | 88 | 2464 | 477708911 |

**Wniosek:** 
1. `id` w JSON to **numeryczne, rosnące ID** — to jest "główna baza" (najświeższa oferta 1093493751, starsze 477708911 itd.).
2. `category.id` w JSON jest INNY niż `CID` w URL. Są dwie mapy kategorii. Do filtrowania w API trzeba używać `category.id` (numerycznego), nie `CID`.

## Dowód 18: Odczyt pojedynczej oferty po NUMERYCZNYM ID DZIAŁA

`https://www.olx.pl/api/v1/offers/1093493751/` → zwraca pełną ofertę.

To jest **kluczowa możliwość**: możemy czytać ofertę po samym numerycznym ID. W połączeniu z faktem, że ID są rosnące, to podstawa metody "przewidywania ID".

## Dowód 19: sort_by=created_at:desc NIE sortuje poprawnie

Test `?limit=5&sort_by=created_at:desc` zwrócił STARE oferty:
- Pompa (created 2025-10-26)
- Skoda Kodiaq (created 2026-02-22)
- Bluzka (created 2018-08-21)

...podczas gdy domyślne `?offset=0&limit=3` zwróciło NAJNOWSZE (spodenki created 2026-08-24T15:25).

**Wniosek:** param `sort_by=created_at:desc` w tym formacie NIE działa tak jak oczekiwano. Domyślne sortowanie (bez sort_by) daje najnowsze. To trzeba lepiej zbadać — ale dla metody ID nie jest to krytyczne (my i tak celujemy w konkretne ID).

## Dowód 20: Domyślne sortowanie zwraca najświeższe oferty

`?offset=0&limit=3` (bez sort_by) zwróciło ofertę utworzoną 2 minuty temu (created 2026-08-24T15:25, pobrano 15:27). Czyli endpoint domyślnie zwraca najnowsze.

## Dowód 21: Region Mazowsze w JSON

Regiony widziane w JSON:
- id=4 Małopolskie
- id=6 Śląskie
- id=7 Łódzkie
- id=17 Podkarpackie

Mazowsze = trzeba potwierdzić (prawdopodobnie id=9 lub inny). Do ustalenia przez zapytanie z filtrem regionu.

---

## SEDNO METODY (nowa wersja)

Stara wersja liczyła ID numeryczne +1. Teraz wiemy, że:
1. W API numeryczne `id` jest **rosnące** (globalna sekwencja).
2. Odczyt `GET /api/v1/offers/{id}/` działa.
3. Więc: bierzemy max id z listy, potem odczytujemy `id+1`, `id+2`, ... i sprawdzamy, czy zwraca ofertę (200) czy 404.
4. Gdy oferta pasuje do kategorii (category.id) → detekcja PRZED wyszukiwarką.

**Do potwierdzenia:** czy odczyt `id+N` (N przyszłe) zwraca 404, czy coś innego. To zrobi następny test.

## Pozostałe niewiadome
1. Region Mazowsze — numeryczne id.
2. category.id dla iPhone (2912?), auta (dla CID5).
3. Czy odczyt przyszłych ID zwraca 404 (wtedy proste).
4. CloudFront na VPS — jak obejść (TLS fingerprint + __cf_bm).