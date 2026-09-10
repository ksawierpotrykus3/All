# Recon OLX — DLACZEGO klucz "przeszukiwał wszystko" — wyjaśnienie (2026-08-24)

## Dowód 32: Oficjalna odpowiedź OLX (developer.olx.pl FAQ)

Z oficjalnej dokumentacji OLX ([developer.olx.pl/artykuly/czeste-pytania](https://developer.olx.pl/artykuly/czeste-pytania)):

**Pytanie 6: "Czy mogę użyć API do pobierania informacji o ogłoszeniach innych użytkowników?"**

> **"Nie jest to możliwe - możesz zarządzać wyłącznie ogłoszeniami na swoim koncie OLX."**

**Pytanie 1: "Invalid owner in token"**

> "The problem occurs when you are authorized with **grant_type: client_credentials** and you are trying to perform actions in the OLX user context... In this situation you have to authorize yourself with **grant_type: authorization_code**."

**Pytanie 11: Rate limit**

> "OLX API zezwala na maksymalnie **4500 zapytań z danego IP w ciągu 5 minut**. Przekroczenie blokuje na 30 minut."

## Dowód 33: Co to oznacza

1. **Oficjalne API partnerskie (klucz 202745) NIGDY nie pozwalało na wyszukiwanie cudzych ogłoszeń.** To jest wprost w FAQ OLX. Służy wyłącznie do zarządzania własnymi ogłoszeniami konta.

2. Nasz błąd `Invalid user ID in token` to dokładnie odpowiednik `Invalid owner in token` z FAQ — bo użyliśmy `client_credentials`, a endpoint partnerski wymaga `authorization_code` (kontekst konta użytkownika).

3. **Skąd więc brała się "przewaga nad wyszukiwarką"?** NIE z klucza partnerskiego. Z **publicznego endpointu** `/api/v1/offers/{id}/` — tego, który znaleźliśmy i który działa BEZ klucza. To jest wewnętrzne API strony OLX (to samo, którego używa frontend), publicznie dostępne przez TLS impersonation.

## Dowód 34: Wniosek dla klienta

- Klient myśli, że klucz dawał mu "milion requestów bez banów" i "przeszukiwanie wszystkiego".
- Prawda: klucz = autoryzacja do własnych ogłoszeń (limit 4500/5min/IP). Przewaga = publiczne API strony + skanowanie ID + TLS impersonation.
- **Bot działa bez klucza.** Klucz można użyć opcjonalnie, ale nie jest źródłem danych o cudzych ofertach.

## Co mamy na pewno działające
1. `curl_cffi` impersonate chrome124 → 200 (omija CloudFront)
2. `GET /api/v1/offers/` → lista (domyślnie najnowsze)
3. `GET /api/v1/offers/{id}/` → pełna oferta po numerze ID
4. nieistniejące ID → 404
5. ID rośnie globalnie
6. Kategorie: auta=203, telefony=2912 (category.id w JSON)
7. Cross-listy otomoto = `partner.code == "otomoto_pl_form"`

## Do zrobienia (następne)
1. Ustalić prawdziwy max ID (lista nie sortuje po ID max).
2. Znaleźć category.id dla laptopów/MacBooków.
3. Komparator czasu (detekcja vs wyszukiwarka) → przewaga w minutach.
4. Długi live test (godziny) → statystyki.