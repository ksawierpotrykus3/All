# Raport badawczy: Autobuy OLX — ustalenia z sesji (2026-09-02)

## Cel
Ustalić, czy do ogłoszeń z Przesyłką OLX można dodać autobuy (automatyczny zakup), oraz zweryfikować mechanizm rezerwacji 15 min / 409 Conflict opisany w koncepcji 08 i reklamowany przez FlipAlert.

## Kluczowe ustalenia (zweryfikowane na żywo)

### 1. Bearer access_token DZIAŁA na API OLX
- `GET https://www.olx.pl/api/v1/users/me/` z nagłówkiem `Authorization: Bearer {access_token}` → **200**, konto „Ksaw" (id 2553769477).
- To obala wcześniejsze założenie (raport 14), że API jest niedostępne i checkout idzie wyłącznie przez OAuth + stronę.
- TTL access_token = 15 min (`exp - iat = 900 s`). Po wygaśnięciu → 401.

### 2. Checkout to strona HTML, nie endpoint API
- `GET https://www.olx.pl/delivery/checkout/{numeric_id}/` → **200**, zwraca 1.93 MB HTML.
- HTML nie zawiera `__NEXT_DATA__` ani `buildId` → to NIE jest Next.js; framework własny OLX.
- Ścieżki API nie są w HTML — trzeba ich szukać w JS chunkach (reverse engineering).

### 3. Zgadywane endpointy delivery są błędne (404)
- `/api/v1/delivery/orders/` → 404
- `/api/v1/delivery/buyers/profile/` → 404
- `/api/v1/delivery/orders/saved-addresses/` → 404 (z wcześniejszego probe)

### 4. Struktura `delivery.rock` — WYKRYTE
- `delivery.rock.offer_id` = UUID formatu `aaaaaaaa-0000-0000-0000-{12 cyfr}`.
- Przykład: oferta 1084508890 → `aaaaaaaa-0000-0000-0000-758071080199`.
- Relacja między numerycznym ID a UUID rock jest **nieustalona** (nie jest to proste zero-padding). Zgodnie z AGENTS.md nakaz 3 traktujemy je jako **dwa różne identyfikatory**. [DOMNIEMANE]
- `delivery.rock.mode` przyjmuje **trzy wartości** (NOWE ODKRYCIE): `BuyWithDelivery` (oferta z przesyłką), `NotEligible` (brak), `Ask4Delivery` (dostawa na żądanie — znaleziona w `dane/` listing_data). [UDOWODNIONE]
- `delivery.rock.active` = true/false.

### 5. Cookies NIE wystarczają do flow checkoutu w przeglądarce
- Załadowanie cookies (w tym access_token) do Playwright → redirect na `login.olx.pl` z OAuth2 `/oauth2/authorize`.
- Wklejony dump `localStorage` z www.olx.pl **NIE zawiera refresh_token ani żadnego tokena Cognito** — jedyny klucz `f_token` jest pusty. [UDOWODNIONE]
- Gdzie OLX trzyma trwałą sesję (refresh token) — **nadal NIEWIADOME**. Możliwe lokalizacje: sessionStorage, IndexedDB, pamięć JS (nie-persystowana). [HIPOTEZA]

## Czego NIE udało się ustalić (niewiadome)
1. **Prawdziwe endpointy API checkoutu** — nie znaleziono; wymagają reverse engineeringu JS chunków.
2. **Czy blokada 15 min / 409 Conflict istnieje** — nadal niepotwierdzone (wymaga kliknięcia „Kup" w autoryzowanej sesji).
3. **Flow płatności (PayU/BLIK)** — żadnych endpointów nie przechwycono.
4. **Gdzie OLX trzyma trwałą sesję (refresh token)** — nie w cookies, nie w localStorage; do zlokalizowania (sessionStorage / IndexedDB / pamięć JS). [NIEPOTWIERDZONE]

## Co jest potrzebne do dalszych badań
1. **Zlokalizować refresh token / trwałą sesję** — sprawdzić sessionStorage, IndexedDB oraz requesty sieciowe przy zalogowanej sesji. Bez tego każda sesja umiera po 15 min.
2. **Reverse engineering JS chunków** strony checkoutu — znaleźć skrypt, który odpala przycisk „Kup z przesyłką", i wyciągnąć realne ścieżki API.
3. **Świeże logowanie z dumpem wszystkich magazynów przeglądarki** — skrypt, który po zalogowaniu zapisze `localStorage` + `sessionStorage` + `IndexedDB`.

## Pliki utworzone w tej sesji
- `recon/probe_token_bearer.py` — test Bearer tokena na API.
- `recon/probe_checkout_auth.py` — pobranie checkoutu z Bearerem, wyciąganie ścieżek.
- `recon/capture_checkout_buy.py` — przechwytywanie flow z kliknięciem „Kup" (Playwright).
- `dane/probe_token_bearer.json` — wyniki testu Bearer.
- `dane/checkout_auth_page.html` / `checkout_auth_paths.json` — strona checkoutu z autoryzacją.

## Wnioski dla klienta (smartcare)
Autobuy OLX pozostaje **prawdopodobnie wykonalny**, ale nie potwierdzony. Kluczowe pytanie — czy kliknięcie „Kup z przesyłką" faktycznie tworzy rezerwację blokującą innych (mechanizm FlipAlert) — wymaga dokończenia badań z refresh_token. Dopóki go nie ma, nie należy obiecywać autobuy klientowi.