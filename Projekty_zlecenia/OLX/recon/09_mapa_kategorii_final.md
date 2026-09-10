# Recon OLX — Mapa kategorii (category.id) — potwierdzone (2026-08-24)

> ## PRZESTARZAŁE — TA KOREKTA BYŁA BŁĘDNA (zweryfikowano na żywo 2026-08-25)
> Twierdzenie „Auta osobowe (całe): category.id == 183 — 64/64 auta" okazało się FAŁSZYWE.
> Sonda `verify_cat_183.py`: `category_id=183` zwraca **65/65 samych BMW** (183 = tylko marka BMW).
> `query=audi` → `category.id=182`. Każda marka ma osobne ID.
> **Prawidłowy filtr aut:** `category.type == "automotive"` + sygnatura pełnego auta
> (params: year/milage/petrol/car_body/transmission), NIE sztywne `category_id`.
> Patrz: [13_wiedza_techniczna_olx.md](13_wiedza_techniczna_olx.md) sekcje 2 i 9.

> ## WAŻNA KOREKTA (faza 5, wieczór)
> Wpis "Auta — Opel 198 / Skoda-SUV 203" poniżej jest **przestarzały**. Ostateczna weryfikacja sondą na żywo:
> - **Auta osobowe (całe): `category.id == 183`** — 64/64 ofert to auta, nie części.
> - Części/akcesoria motoryzacyjne: **1399, 1465, 1385, 4488** (NIE 183).
> - **iPhone: `2298`** (100% czysty), **MacBook: `3102`** (100% czysty), szeroka "telefony z akcesoriami": `2912` — nie używać.
> - Filtr aut NIE może być `type=="automotive"` (łapie części). Twardo: `cat_id == 183`.

## Dowód 35: category.id dla docelowych grup

| Grupa klienta | category.id | type | Uwagi |
|---------------|-------------|------|-------|
| **MacBooki / laptopy** | **3102** | electronics | komputery/laptopy |
| **iPhone / smartfony** | **2298** | electronics | smartfony (czysta subkategoria) |
| Telefony (szeroka, z akcesoriami) | 2912 | electronics | zawiera etui/kable — NIE używać |
| **Auta — całe osobowe (OSTATECZNE)** | **183** | automotive | 64/64 auta, nie części |
| Części samochodowe (śmieci) | 1465 | automotive | ODRZUCAĆ (jedna z 4 kategorii części) |

## Wniosek — kategorie aut (SKORYGOWANY)

Stara teza "kategorie aut są rozbite na wiele ID, więc filtruj po type" okazała się **błędna w praktyce** — `type=="automotive"` łapało części. Ostatecznie:

**Filtr aut:** `category.id == 183` + `price <= 12000` + `region.name == "mazowieckie"` + wykluczyć partner `otomoto_pl_form`.

**Filtr iPhone:** `category.id == 2298` + blacklista słów (etui, szkło, icloud, uszkodzony...).

**Filtr MacBook:** `category.id == 3102` + tytuł zawiera "macbook"/"mac book"/"macbookpro" + blacklista.

## Dowód 36: wyszukiwanie frazowe działa

`GET /api/v1/offers/?query=macbook` → 200, zwraca pasujące oferty. To potwierdza, że API wspiera `query` (słowa kluczowe) — przydatne do komparatora "co widzi wyszukiwarka".