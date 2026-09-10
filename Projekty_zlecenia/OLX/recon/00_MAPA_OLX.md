# MAPA OLX — pełna dokumentacja poznawcza (2026-08-24)

> ## AKTUALIZACJA PO FAZIE 5 (2026-08-24, wieczór) — PRZECZYTAJ NAJPIERW
> Niniejszy dokument pochodzi z fazy RECON (rano). Poniższe punkty zostały **zweryfikowane/obalone** w dalszych fazach. Szczegóły: [12_raport_faza5_async_browser.md](12_raport_faza5_async_browser.md) i [SESSION_LOG_2026-08-24.md](../SESSION_LOG_2026-08-24.md).
>
> ### Ustalenia ZASTĘPUJĄCE stare wpisy
> - **Kategoria auta:** NIE sztywne `category.id` — **`category.id == 183` to tylko BMW** (zweryfikowane na żywo: `category_id=183` → 65/65 samych BMW; Audi=182, każda marka ma osobne ID). Filtr aut = **`category.type == "automotive"` + sygnatura pełnego auta** (params: year/milage/petrol/car_body/transmission). Części/akcesoria moto: **1399, 1465, 1385, 4488**.
> - **iPhone:** `category.id == 2298` (100% czyste iPhone'y, 65/65). Kategoria 2912 to szeroka "telefony z akcesoriami" — NIE używać.
> - **MacBook:** `category.id == 3102` (100% MacBooki, 65/65). Wymagany tytuł: "macbook"/"mac book"/"macbookpro" (nie samo "mac" — odsiewa Mac Pro/Mac Mini).
> - **Limit API:** `limit` max **50** (51→400). Głębokość wyszukiwania max **1000 unikalnych** (`metadata.total_elements`), mimo `visible_total_count` np. 142k dla "iphone".
> - **Detektor:** asynchroniczny `curl_cffi.AsyncSession` → **57 ID/s** (test), współdzielona sesja per batch. Tempo kreacji OLX **~2.19 ID/s** (pomiar). Sliding window (head = max_200+1) + retry przy błędach sieci.
> - **Frontend (Playwright):** DOM renderuje **52 karty** `div[data-cy='l-card']` po akceptacji OneTrust (`button#onetrust-accept-btn-handler`). JSON-LD w HTML to tylko 20 ofert (SEO, Google) — NIE mylić z DOM.
> - **Klucz partnerski (202745):** OAuth OK (`partner_code=4420`, scope v2 read write), ale `/api/partner/adverts` → `Invalid user ID in token`. **Detektor nie używa klucza.** Stress test: token vs brak tokenu = 0 różnicy na publicznym API. Klucz bezużyteczny dla szukania.
> - **Przewaga czasowa:** dla świeżych ofert (created po starcie bota) zmierzono **5.53–16.61 min** (20-min przebieg).

---

## Co wiemy na pewno (dowody)

### 1. Blokada i jej obejście
- OLX ma **CloudFront** (edge Warszawa `WAW51-P3`) z blokadą 403 dla klientów bez przeglądarkowego TLS.
- `requests`, `curl.exe` → 403.
- **`curl_cffi` (Python) z `impersonate="chrome124"` → 200 OK.** ✅
- To jest główny klucz techniczny: bot na VPS musi używać `curl_cffi` (lub innego klienta z impersonacją TLS/JA3).
- `impersonate="chrome126"` i inne warianty też działają (testowane); chrome124 = stabilny wybór.

### 2. Endpointy API (działające)
| Endpoint | Funkcja |
|----------|---------|
| `GET https://www.olx.pl/api/v1/offers/?offset=0&limit=N` | lista ofert (domyślnie najnowsze) |
| `GET https://www.olx.pl/api/v1/offers/{numeryczne_id}/` | pełna oferta po ID |
| nieistniejące ID → **404** | wykrywanie luk |

### 3. Dwa systemy ID
- **Numeryczne ID** (w JSON `id`) — globalne, rosnące. To jest "główna baza".
- **Alfanumeryczne ID** (w URL `ID1c0bFZ`) — to tylko reprezentacja w linku, NIE służy do przewidywania.
- Metoda: skanuj numeryczne ID w górę (co 1), odczytuj `GET /offers/{id}/`, 404 = luka, 200 = oferta.

### 4. Kategorie (dwie mapy!)
| Kategoria | CID (URL) | category.id (API JSON) |
|-----------|-----------|------------------------|
| Samochody osobowe | 5 | **203** |
| Telefony | 99 | **2912** |
| MacBooki (laptopy) | ? | **do ustalenia** |
| Dom i Ogród | 628 | 1698 |
| Moda | 87/88 | 2940/2464 |
| Budowa (wiata) | 103 | 2969 |

### 5. Cross-listy otomoto (do odrzucenia)
- Pole `partner.code == "otomoto_pl_form"` + `external_url` na otomoto.pl.
- Bot musi je odrzucać — to duplikaty/zanieczyszczenie kategorii auta.

### 6. Filtry w JSON
- Cena: `params[].key=="price"` → `value.value` (liczba)
- Rok: `params[].key=="year"` → `value.label`
- Paliwo: `params[].key=="petrol"` → `value.label`
- Przebieg: `params[].key=="milage"` → `value.label`
- Region: `location.region.name` (tekst, np. "mazowieckie")
- Miasto: `location.city.name`

### 7. Zanieczyszczenie kategorii Telefony (potwierdza słowa klienta)
- Kategoria CID99 zawiera: smartfony, akcesoria, etui, szkła, karty SIM, stacjonarne.
- Trzeba czarnej listy słów: etui, szkło, obudowa, case, karta sim, ładowarka, słuchawki, akcesoria, uchwyt.

## Status metody (co już działa, co nie)

### DZIAŁA ✅
1. Dostęp do API z lokalnego IP przez curl_cffi.
2. Odczyt oferty po numerycznym ID.
3. Odczyt listy ofert.
4. Wykrywanie 404 dla nieistniejących ID.
5. Skanowanie ID w górę (99 ID w 45s przy odstępie 0.15s).

### DO USTALENIA ⚠️
1. **Prawdziwy max ID** — lista `?offset=0&limit=50` NIE sortuje po max ID (zawiera stare oferty). Trzeba ustalić max ID inaczej: skanować w górę aż do ciągu 404, albo znaleźć endpoint z sortowaniem po ID.
2. **category.id dla MacBooków/laptopów** — do znalezienia (pobrać ofertę laptopa z API).
3. **Region Mazowsze** — używać `location.region.name == "mazowieckie"` (tekst), nie wymaga numerycznego ID.
4. **Przewaga czasowa** — czy odczyt po ID faktycznie wyprzedza wyszukiwarkę (komparator). Fundament stoi, ale przewaga NIE została jeszcze zmierzona.
5. **Klucz deweloperski (202745)** — publiczne API działa BEZ klucza. Klucz może być zbędny (albo przydatny do wyższego rate-limitu). Do zweryfikowania oddzielnie.

## Pliki dowodów
- `01_dowody_recon.md` — CloudFront blokuje, format URL, CID
- `02_kategorie_i_id.md` — kategorie, analiza ID alfanumerycznych
- `03_sekwencyjnosc_id.md` — globalny licznik ID
- `04_przelom_api_id.md` — API działa, podwójny system ID
- `05_potwierdzenie_sekwencji.md` — sekwencja + mapa kategorii API
- `06_tls_rozwiazanie.md` — rozwiązanie CloudFront (curl_cffi)
- `test_cloudfront.py`, `test_tls.py`, `detector_proto.py`, `detector_live.py` — skrypty testowe

## Następne kroki
1. Ustalić prawdziwy max ID (skan w górę + notowanie maksymalnego 200).
2. Znaleźć category.id dla laptopów/MacBooków.
3. Przetestować klucz deweloperski (czy daje cokolwiek przy publicznym API).
4. Zbudować właściwy detektor: start od realnego max ID, skan w górę, filtrowanie 203/2912/laptopy, czarna lista.
5. Komparator: porównać czas detekcji vs moment pojawienia się w wyszukiwarce → liczyć przewagę w minutach.
6. Test długi (godziny) → statystyki trafień i przewagi.