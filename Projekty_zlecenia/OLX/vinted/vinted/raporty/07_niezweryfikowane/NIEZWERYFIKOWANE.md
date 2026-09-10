# Unikalne informacje z Hello.md

> **UWAGA: NIEZWERYFIKOWANE.** Ten plik zawiera wyłącznie informacje wyodrębnione z rozmowy w `Hello.md`, których nie ma w żadnym z raportów Vinted. Nie zostały one potwierdzone niezależnie i nie należy ich traktować jako zweryfikowanej wiedzy o Vinted.

## 1. Liczby Grep dla pliku `0~~ak8p40jr.6.js`
- Plik to kod **TURBOPACK** (pierwszy wiersz `(globalThis.TURBOPACK||...)`).
- Wystąpienia: `purchases` ×4, `checkout` ×73, `checkout/build` ×1.
- **0 wystąpień**: `api/v2`, `vinted.pl`, `http` w całym pliku.
- Wniosek: fragment `checkout/build` nie tworzy literalnego endpointu URL `/api/v2/...`.

## 2. Pełna lista ścieżek z `captured_api_paths.json` (raw_count: 42)
Raporty wymieniają tylko 3 ścieżki. Pełna lista 5:
- `/api/v2/banners`
- `/api/v2/conversations/stats`
- `/api/v2/external_crm/jwts`
- `/api/v2/info_banners/catalog`
- `/api/v2/promoted_closets`

Dodatkowo: `raw_count: 42` oraz lista 21 ścieżek.

## 3. Wykryty błąd w `DOWODY_INZYNIERIA_VINTED.md`
- Filtr `brand` ma `id: 8` **oraz** filtr `material` też ma `id: 8` — wewnętrzna sprzeczność danych.

## 4. Inwentaryzacja skryptów testowych (na żywo vs statyczne)
Podział, którego brak w raportach:
- **Na żywo** (HTTP przez curl_cffi/Playwright)
- **Statyczne** (analiza lokalnych plików)

Wybrane nazwy: `deep_analyze_checkout_js.py`, `inspect_transactions_chunk.py`, `extract_js_routes.py`, `analyze_nextjs_chunks.py`, `scan_vinted_js_endpoints.py` (hybrydowy).

Dodatkowe endpointy testowane (niewymienione w raportach):
- `/api/v2/catalog/blocks`
- `/api/v2/catalog/filters/facets`
- `/api/v2/catalog/filters/search?filterSearchText=...`
- warianty `/items/{id}`: `localize=false`, `/catalog/items/{id}`, `/item/{id}`, `/products/{id}`, `/items/{id}/similar`, `/items/{id}/photos`

## 5. Ciasteczka sprawdzane w `test_fresh_session.py`
- `datadome`, `_vinted_fr_session`, `v_sess`.

## 6. Brak twardych logów 200/403
- Wszystkie skrypty tylko `print(r.status_code)` w runtime.
- W repo nie ma żadnych plików logów ani zrzutów z zakodowanymi wynikami 200/403.

## 7. Metadane plików danych
- `flight_data.txt` ~27 KB — React Flight / Next.js RSC (nie dane lotnicze).
- `katalog_1904.html` ~7 MB.

## 8. Meta-analiza spójności czterech raportów
- Podział na „dwie warstwy wiarygodności": zmierzona (RAPORT_FINALNY + AUDYT) vs „reverse-engineeringowa" (DOWODY + KOMPENDIUM).
- Najpoważniejsza sprzeczność: deklaracja „rozpracowany w 100%" wobec braku przechwycenia checkoutu.