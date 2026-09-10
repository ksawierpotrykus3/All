# Recon OLX — dowody (live, 2026-08-24)

## Dowód 1: CloudFront blokuje curl (ale nie WebFetch)

- `curl.exe` z lokalnego terminala → **403 Forbidden** na WSZYSTKICH endpointach, nawet na stronie głównej i robots.txt.
- Serwer: `CloudFront`, błąd: "Request blocked. We can't connect to the server for this app or website at this time."
- X-Amz-Cf-Pop: `WAW51-P3` (edge Warszawa).
- Testowane (wszystko 403):
  - `https://www.olx.pl/`
  - `https://www.olx.pl/robots.txt`
  - `https://www.olx.pl/api/v1/offers/?offset=0&limit=5`
  - `https://m.olx.pl/api/v1/offers/`
  - `https://api.olx.pl/api/v1/offers/`
- Dodatkowe nagłówki przeglądarkowe (sec-ch-ua, sec-fetch-*) **nie pomagają** — nadal 403.

**Wniosek:** OLX blokuje na poziomie CloudFront (edge) żądania bez pełnego fingerprintu JS/TLS. Bezpośredni scraping z lokalnego IP przez curl jest w tej chwili niemożliwy. Trzeba ustalić, czy blokada wynika z IP (data center / podejrzane ASN), TLS fingerprintu, czy braku cookie `__cf_bm` (CloudFront Bot Management / JS challenge).

## Dowód 2: WebFetch widzi treść OLX

- `WebFetch` na `https://www.olx.pl/` zwraca poprawną treść (kategorie, ogłoszenia promowane).
- To potwierdza, że strona działa — blokada dotyczy konkretnie naszego klienta HTTP (curl) / IP.

## Dowód 3: NOWY format URL ofert (zmiana vs stara wersja bota!)

Stary format (historyczny):
```
https://www.olx.pl/oferta/<slug>-ID<numer>.html
```

Nowy format (obecny, zaobserwowany w WebFetch):
```
https://www.olx.pl/d/oferta/<slug>-CID<numer>-ID<alfanumeryczny>.html
```

Przykłady ID z ogłoszeń promowanych (strona główna):
- `CID757-ID1bPxV0` — Zwierzęta (kura nioska)
- `CID3-ID1bNBBi`   — Nieruchomości (pokój Kraków)
- `CID3-ID1bRyBf`   — Nieruchomości (mieszkanie Wrocław)
- `CID767-ID19t6lP` — Sport (narty)
- `CID87-ID1bjH2q`  — Moda (buty)
- `CID5-ID1bXgcU`   — Motoryzacja/Samochody (Toyota Yaris)
- `CID4371-IDeWtIn` — Usługi (transport)
- `CID5-ID1bY6g9`   — Motoryzacja/Samochody (Renault Captur)
- `CID5-ID1bWnwK`   — Motoryzacja/Samochody (Renault Clio)
- `CID5216-IDJm4Y8` — Budowa (parapety)
- `CID628-ID1aj5di` — Dom i Ogród (agregat)
- `CID3-ID1bubYg`   — Nieruchomości (pokój Warszawa)
- `CID4371-ID15IiyI`— Usługi (ładowarka)
- `CID628-ID1bWMOz` — Dom i Ogród (piec)
- `CID5-ID1bWDnU`   — Motoryzacja/Samochody (Can-Am)
- `CID5-ID1bXQ2Q`   — Motoryzacja/Samochody (Suzuki Ignis)

## Dowód 4: ID ogłoszeń są teraz ALFANUMERYCZNE (nie czysto numeryczne)

- ID mają prefiks `ID` i wartość alfanumeryczną (prawdopodobnie base36/base62), np. `1bPxV0`, `1bNBBi`, `1bRyBf`, `1bjH2q`.
- **To fundamentalna zmiana względem starej wersji bota**, która działała na numerycznych, sekwencyjnych ID.
- Wartości zaczynają się od `1b...` — sugeruje wspólną, rosnącą przestrzeń ID (base36).
- Wniosek: metoda "przewidywania ID" wymaga teraz **inkrementacji w bazie alfanumerycznej** (np. base36), a nie zwykłego +1 na integerach. To trzeba zweryfikować.

## Dowód 5: Mapowanie CID (ID kategorii)

- `CID5`    = Motoryzacja → Samochody osobowe
- `CID3`    = Nieruchomości → Mieszkania/Pokoje
- `CID757`  = Zwierzęta
- `CID767`  = Sport i Hobby
- `CID87`   = Moda
- `CID4371` = Usługi
- `CID5216` = Budowa i Remont
- `CID628`  = Dom i Ogród

---

## Co dalej (następne sondy)

1. Ustalić, dlaczego curl dostaje 403 (IP? TLS? brak __cf_bm?) — przetestować inne User-Agenty, http2, cookie.
2. Przez WebFetch pobrać strony wyszukiwania kategorii i wyciągnąć:
   - ID kategorii dla iPhone, MacBook, auta (subkategorie telefonów/laptopów).
   - Region ID dla Mazowsza.
   - Listy ID ofert z jednej kategorii (do testu sekwencyjności).
3. Zweryfikować, czy alfanumeryczne ID są sekwencyjne (base36 rosnąco).