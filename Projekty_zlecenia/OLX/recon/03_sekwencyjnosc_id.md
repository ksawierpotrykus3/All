# Recon OLX — sekwencyjność ID potwierdzona (2026-08-24)

## Dowód 11: ID są GLOBALNE i SEKENCYJNE — mocny dowód z tego samego dnia

Dwie oferty z różnych kategorii, wstawione niemal w tej samej chwili, mają **niemal identyczne ID**:

| Oferta | Kategoria | ID |
|--------|-----------|-----|
| iPhone 16 Pro 256GB White (odśw. dziś 11:06) | CID99 (Telefony) | `1bSRDX` |
| BMW E90 2.0 129KM (odśw. dziś 11:10) | CID5 (Auta) | `1bSRQ6` |

- Oba ID zaczynają się od `1bSR`. To NIE jest zbieg okoliczności — to dowód, że **cała platforma OLX używa jednego globalnego, rosnącego licznika ID** dla wszystkich kategorii.
- Telefon i auto wstawione w odstępie kilku minut mają ID różniące się tylko ostatnimi znakami.
- **Wniosek:** metoda "przewidywania ID" z poprzedniej wersji bota nadal ma podstawy — ale licznik jest teraz alfanumeryczny (base36/base62), nie dziesiętny.

## Dowód 12: Format ID (do rozgryzienia bazy)

Widziane wartości ID mają postać: `1` + litera + 5 znaków alfanumerycznych (7 znaków):
- Telefony: `1bZpPn`, `1bZUHX`, `1bCFHK`, `1bSRDX`, `1bN2sZ`, `1bNaQB`, `188nTL`, `18J4L1`, `19t6lP`
- Auta: `1bWad8`, `1bEyzg`, `1bW0WW`, `1bSRQ6`, `1bN8EE`, `1bVzWQ`, `16PINP`, `16OBDH`, `14aoQQ`, `12SfKf`

Obserwowany wzrost prefiksu (od starszych do nowszych): `12` → `14` → `16` → `18` → `19` → `1a` → `1b`.

Jeśli to **base36** (0-9, a-z): po `1bZZZZZ` idzie `1c00000`. To spójne z obserwacją, że starsze oferty mają `12..`, `14..`, `16..`, a dzisiejsze `1b..`.
Jeśli to **base62** (0-9, a-z, A-Z): kolejność zawiera też duże litery — do potwierdzenia eksperymentem inkrementacji.

## Dowód 13: Kategorie — subkategoria NIE zmienia CID

- Subkategoria "Smartfony i telefony komórkowe" ma URL `/elektronika/telefony/smartfony-telefony-komorkowe/`, ale oferty w tej subkategorii **nadal mają CID99** (to samo co cała kategoria "Telefony").
- Czyli **CID nie rozdziela "smartfon" od "akcesoria"** — oba są CID99.
- Filtr "czysty iPhone" trzeba robić inaczej: słowa kluczowe (q=iphone) + czarna lista (etui, szkło, obudowa, case, karta SIM, ładowarka) + ewentualnie filtry atrybutów (marka=Apple).

## Dowód 14: Auta Mazowieckie ≤12k działają + zanieczyszczenie cross-listami otomoto

URL z filtrem działa:
```
https://www.olx.pl/motoryzacja/samochody/mazowieckie/?search%5Bfilter_float_price%3Ato%5D=12000
```
- Pokazuje oferty Mazowieckie do 12 000 zł (potwierdzone: Skoda Rapid 10 490 zł, BMW E90 11 000 zł itd.).
- Zanieczyszczenie: część wyników to **cross-listy z otomoto.pl** (np. Skoda Octavia 1750 zł z `otomoto.pl/...ID6IbZJ6.html`, Volvo XC90 z `otomoto.pl`). Bot musi je odfiltrowywać (po domenie linku lub CID).

## Dowód 15: CloudFront blokuje curl, ale WebFetch przechodzi

- `curl.exe` → 403 na wszystkim (CloudFront edge Warszawa `WAW51-P3`).
- `WebFetch` → zwraca poprawną treść OLX.
- Oznacza to: **blokada zależy od klienta HTTP** (TLS fingerprint / brak cookie `__cf_bm` po JS challenge), nie od samego IP. Do produkcji na VPS konieczne będzie: TLS fingerprint przeglądarki + obsługa cookie CloudFront (albo headless browser).

## Co dalej
1. Potwierdzić bazę ID (base36 vs base62) — eksperyment inkrementacji.
2. Znaleźć endpoint "głównej bazy" (odczyt oferty po samym ID) — test przez WebFetch endpointów `/api/v1/offers/`.
3. Test klucza partnerskiego OLX (`/api/partner/adverts`).