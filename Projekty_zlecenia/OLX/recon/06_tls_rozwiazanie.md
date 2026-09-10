# Recon OLX — ROZWIĄZANIE blokady CloudFront (2026-08-24)

## Dowód 27: TLS fingerprint → rozwiązanie to curl_cffi (impersonate chrome124)

Test z lokalnego IP:

| Klient | Wynik |
|--------|-------|
| `requests` (Python) | 403 |
| `curl.exe` (PowerShell) | 403 |
| `curl_cffi` impersonate `chrome126` | błąd "not supported" |
| **`curl_cffi` impersonate `chrome124`** | **200 OK** ✅ |
| `curl_cffi` impersonate `chrome120` | 200 OK ✅ |
| `curl_cffi` impersonate `chrome110` | 200 OK ✅ |
| `curl_cffi` impersonate `chrome` | 200 OK ✅ |

**Wniosek:** OLX/CloudFront blokuje po TLS/JA3 fingerprint. Klienci z fingerprintem prawdziwej przeglądarki (curl_cffi chrome) przechodzą. To klucz do produkcji — bot na VPS musi używać `curl_cffi` (Python) lub ekwiwalentu z impersonacją TLS.

## Dowód 28: Pełny JSON oferty dostępny programowo

Przez `curl_cffi` dostajemy identyczny JSON jak przez WebFetch. Oznacza to, że możemy budować bota w Pythonie z pełnym dostępem do:
- odczyt oferty po numerycznym ID
- category.id, cena, region, tytuł, created_time
- filtr cross-list (partner.code == "otomoto_pl_form")

## STATUS KOŃCOWY FAZY 0 (recon)

1. ✅ API działa: `https://www.olx.pl/api/v1/offers/`
2. ✅ Odczyt po ID: `GET /api/v1/offers/{numeryczne_id}/`
3. ✅ ID numeryczne rośnie globalnie (sekwencja)
4. ✅ CloudFront obejściem: `curl_cffi` impersonate `chrome124`
5. ✅ category.id: auta=203, telefony=2912, laptopy=do ustalenia
6. ✅ cross-listy otomoto: `partner.code == "otomoto_pl_form"`
7. ✅ region w JSON: `location.region.name`
8. ⚠️ Klucz deweloperski (202745) — NIE jest potrzebny do odczytu ofert (API publiczne działa bez klucza). Klucz był w starej wersji, ale teraz główna wartość to TLS impersonation.

## Następny krok: prototyp detektora ID

Zbudować prototyp:
1. `curl_cffi` impersonate chrome124
2. Pobierz max ID z listy najnowszych ofert
3. Skanuj ID w górę (co 1), odczytuj `GET /offers/{id}/`
4. Filtruj category.id (auta=203, telefony=2912)
5. Odrzucaj cross-listy otomoto
6. Loguj detekcje (ID, tytuł, kategoria, cena, region, czas) do konsoli + pliku
7. Komparator: porównaj czas detekcji vs moment pojawienia się w wyszukiwarce (później)