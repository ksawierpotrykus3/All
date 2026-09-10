# Recon OLX — kategorie i analiza ID (2026-08-24)

## Dowód 6: Kategorie (CID)

### Telefony (kategoria nadrzędna: Elektronika)
- `CID99` = Telefony (cała kategoria, smartfony + akcesoria + stacjonarne + złote numery)
- Podkategorie w CID99:
  - Akcesoria: `355 410` ogłoszeń
  - Smartfony i telefony komórkowe: `55 183` ogłoszeń
  - Telefony stacjonarne: `5382`
  - Złote numery: `1008`

> WAŻNE (potwierdza słowa klienta o słowach-kluczach): kategoria "Telefony" (`CID99`) zawiera ŚMIECI: etui, szkła ochronne, karty SIM, obudowy. Do czystego monitoringu iPhone'ów trzeba zejść do subkategorii **"Smartfony i telefony komórkowe"** (potrzebne jej osobne CID — do ustalenia) + filtr słów-kluczowych (np. "iphone") + ewentualnie czarna lista słów (etui, szkło, obudowa, case, karta SIM).

### Samochody (kategoria: Motoryzacja)
- `CID5` = Samochody osobowe
- Cenniki obserwowane: auta też mają problem z zanieczyszczeniem (cross-listingi z otomoto.pl, wyróżnione stare oferty). Do monitoringu "auta do 12k Mazowsze" potrzebny filtr: cena ≤ 12 000 + region Mazowsze + sortowanie po dacie.

### Inne CID (z mapy strony głównej)
- `CID3` = Nieruchomości
- `CID757` = Zwierzęta
- `CID767` = Sport i Hobby
- `CID87` = Moda
- `CID4371` = Usługi
- `CID5216` = Budowa i Remont
- `CID628` = Dom i Ogród

## Dowód 7: NOWY format ID ogłoszeń (alfanumeryczny, nie numeryczny)

Format URL oferty:
```
https://www.olx.pl/d/oferta/<slug>-CID<n>-ID<alfa>.html
```
- `ID` + wartość alfanumeryczna. NIE są to już rosnące liczby dziesiętne (stara wersja bota liczyła +1).
- Obserwacje sugerują, że to **base36** (0-9, a-z) — wartości zaczynają się od `1a`, `1b`, `16`, `12`, `18`, `14`.

## Dowód 8: ID są WSPÓLNE dla całej platformy (globalny licznik)

Porównanie ID z różnych kategorii pokazuje jedną wspólną przestrzeń:
- iPhone: `1bUwd0`, `1bSRDX`, `1bN2sZ`, `1bNaQB`, `1bN0uv` (CID99)
- Auta: `14aoQQ`, `12SfKf`, `16PINP`, `16OBDH`, `16OUTl`, `16OHZQ`, `16OSjf`, `16OOCe`, `16P1Dz`, `16PFY0` (CID5)

> Kluczowa obserwacja: CID5 (auta) mają ID z prefiksem `12…`, `14…`, `16…`, a CID99 (telefony) — `18…`, `1a…`, `1b…`. To znaczy, że **licznik ID nie jest per-kategoria, tylko globalny i rośnie** — nowsze oferty mają wyższe ID w bazie alfanumerycznej. To potwierdza, że metoda "przewidywania ID" NADAL ma sens, ale wymaga:
> 1. Zrozumienia bazy (base36 vs base62) i kolejności.
> 2. Inkrementacji ID w tej bazie (np. base36: po `1bZZZZ` idzie `1c0000`).
> 3. Filtrowania wyników po CID (kategoria) — bo ID jest globalne, a my chcemy tylko konkretne kategorie.

## Dowód 9: Wzór na inkrementację (do weryfikacji)

ID są alfanumeryczne, prawdopodobnie base36. Wartości widziane:
- Auta (starsze, wg daty odświeżenia): `12SfKf` → `14aoQQ` → `16PINP` → ... → `16PFY0`
- Telefony (nowsze): `18oeko` → `18J4L1` → `19t6lP` → `1a6REX` → ... → `1bSRDX` → `1bUwd0` → `1bXgcU` → `1bY6g9`

Widać wzrost prefiksu: `12` → `14` → `16` → `18` → `19` → `1a` → `1b`. To spójne z base36 (po 9 idzie a, b, c...).

## Dowód 10: Co dalej
1. Musimy potwierdzić bazę ID (base36 czy 62) — test inkrementacji.
2. Ustalić CID subkategorii "Smartfony i telefony komórkowe" (nie czysty CID99, bo tam są akcesoria).
3. Ustalić region ID dla Mazowsza.
4. Kluczowa niewiadoma: jak czytać ofertę "po ID" zanim trafi do wyszukiwarki. WebFetch widzi tylko to, co w wyszukiwarce (czyli "za późno"). Musimy znaleźć endpoint "głównej bazy" — prawdopodobnie ten sam, którego używa strona, ale blokowany dla curl (CloudFront).