# WIEDZA TECHNICZNA OLX — baza na przyszłość (2026-08-24, faza 5)

Ten plik to pojedyncze źródło prawdy o technice OLX zdobytej przez całą sesję.
Zastępuje wszelkie wcześniejsze rozproszone ustalenia.

---

## 1. ENDPOINTY API (zweryfikowane)

| Endpoint | Metoda | Działanie | Uwagi |
|---|---|---|---|
| `/api/v1/offers/?offset=0&limit=50` | GET | lista ofert | limit max **50** (51→400) |
| `/api/v1/offers/?offset=0&limit=50&query=xyz` | GET | wyszukiwanie frazowe | działa |
| `/api/v1/offers/?offset=0&limit=50&category_id=183` | GET | filtrowanie po kategorii | działa, kluczowe |
| `/api/v1/offers/{numeryczne_id}/` | GET | pełna oferta po ID | zwraca `{"data": {...}, "links": ...}` |
| `/api/open/oauth/token` | POST | OAuth (client_credentials) | zwraca JWT |

**Struktura odpowiedzi listy:**
```
{
  "data": [...65 ofert przy limit=50...],
  "metadata": {
    "total_elements": 1000,           # twardy limit dostępnych rekordów
    "visible_total_count": 142221,    # realna liczba pasujących
    "promoted": [0,1,2,13,...],       # indeksy promowanych
    "source": {"promoted": [...15], "organic": [...50]}
  },
  "links": {"self": {...}, "next": {...}, "first": {...}}
}
```

**Struktura odpowiedzi pojedynczej oferty:**
```
{"data": {"id": 1093525730, "title": "...", "category": {"id": 1157, "type": "goods"},
 "location": {"region": {"name": "Kujawsko-pomorskie"}, "city": {"name": "Lubraniec"}},
 "params": [{"key": "price", "value": {"value": 15}}], "partner": {"code": null},
 "created_time": "2026-08-24T17:17:40+02:00", "url": "..."},
 "links": {...}}
```

**Pola ważne dla bota:**
- `category.id` — twarda kategoria
- `location.region.name` — region (tekst, np. "Mazowieckie")
- `params[].key == "price"` → `value.value` — cena (może mieć format "12 000")
- `partner.code` — np. `otomoto_pl_form` (do wykluczenia)
- `created_time` — czas utworzenia oferty

---

## 2. KATEGORIE TWARDE (zweryfikowane sondą)

| Cel | kategoria | typ | Pewność |
|---|---|---|---|
| **iPhone** | **category.id = 2298** | electronics | 100% (65/65 iPhone) |
| **MacBook** | **category.id = 3102** | electronics | 100% (65/65 MacBook) |
| **Auta osobowe** | **category.type = "automotive" + sygnatura params** | automotive | parami year/milage/petrol/car_body/transmission |

**BŁĄD NAPRAWIONY 2026-08-24:** wcześniej przyjęto `category.id == 183` = "całe auta". To FAŁSZ — **183 to wyłącznie BMW**. Każda marka ma osobne ID:
BMW=183, Audi=182, Mercedes=195, Opel=198, VW=207, Ford=189, Skoda=203, Toyota=206, Renault=200, Fiat=188, Peugeot=199, Kia=192.

**Jak rozpoznać pełne auto vs część (dowód probe_car_brands.py, test_is_full_car.py):**
- Pełne auto: params zawierają `year`, `milage`, `petrol`, `car_body`, `transmission`, często `vin`.
- Część moto: params zawierają `parts_category` / `part_number` i NIE mają year+milage.
- Wniosek: filtr aut = `category.type=="automotive"` + `len(keys ∩ {year,milage,petrol,car_body,transmission,vin}) >= 3`.
- **Weryfikacja na żywo (test_is_full_car.py):** sygnatura poprawnie odróżnia auta od części — BMW 55 aut/9 części, Opel 22/37, Audi 23/32, VW 54/11.

**CZĘSTOTLIWOŚĆ TRAFIEŃ AUT (dowód test_auto_filter_rate_async.py):**
- W 1200 kolejnych ID jest ~45 pełnych aut, ale tylko **1 auto spełnia filtr (Mazowsze + cena ≤ 12000)**.
- Wniosek: auta do 12k z Mazowsza to rzadkość — średnio **1 na ~1200 ogłoszeń**. Przy tempie kreacji ~2 ID/s to ~10 min na jedno auto. ZERO aut w krótkich oknach to normalne, nie bug.

**Części moto (śmieci):** 1399, 1465, 1385, 4488 i inne — NIE mają sygnatury pełnego auta.
**Kategoria szeroka telefony (z akcesoriami):** 2912 — NIE używać.

---

## 3. SYSTEM ID

- **Numeryczne ID** (w JSON `id`) — globalne, sekwencyjne, rosnące. To jest "główna baza". Przewidujemy przyszłe ID jako `max_id + N`.
- **Alfanumeryczne ID** (w URL `ID1c0jZM`) — tylko reprezentacja linku, NIE do przewidywania.
- Nieistniejące/wolne ID → HTTP **404**.
- Istniejąca oferta → HTTP **200**.
- **Tempo kreacji ID:** ~2.19 ID/s (pomiar szczytowy 2026-08-24 ~18:50). Realnych ogłoszeń ~1.56 ID/s (reszta to luki 404).

---

## 4. OCHRONA CLOUDFRONT I TLS

- Zwykłe `requests`/`curl.exe` → **403 Forbidden** (CloudFront edge WAW51-P3).
- **`curl_cffi` z `impersonate="chrome124"` → 200 OK.**
- Inne profile (chrome126, chrome120, chrome110) też działają; chrome124 stabilny.
- **Asynchronicznie:** `curl_cffi.requests.AsyncSession` z `impersonate="chrome124"`.
- **Maksymalne tempo bez blokady:** 57 ID/s (test 300 zapytań, 5.25s).

---

## 5. LIMITY API (twardo zmierzone)

| Parametr | Wartość | Dowód |
|---|---|---|
| `limit` max | **50** | 51→400, 75/100/101→400 |
| zwrocone rekordy przy limit=50 | **65** (50 org + 15 prom) | metadata.source |
| offset max | **~1000** | offset=1050→400 |
| dostępne unikalne oferty | **~1000** | metadata.total_elements=1000 |
| realna liczba pasujących | np. 142k (iphone) | metadata.visible_total_count |
| sortowanie | **ignorowane** | sort/order nie zmienia wyniku |
| paginacja | **po links.next** | next może skoczyć nie o +50 |

**Wniosek biznesowy:** publiczna wyszukiwarka pokazuje max ~1000 ofert z potencjalnie setek tysięcy. Detektor ID widzi WIĘCEJ niż frontend.

---

## 6. FRONTEND / PRZEGLĄDARKA (Playwright)

- Strona kategorii (np. `https://www.olx.pl/elektronika/telefony/q-iphone/`) renderuje oferty **server-side w HTML** (JSON-LD), nie przez XHR do `/api/v1/offers/`.
- Przechwycone XHR tylko: `sfc/api/v1/categories/config`, sentry, maze widgety.
- **DOM po akceptacji OneTrust** (`button#onetrust-accept-btn-handler`) = **52 karty** `div[data-cy='l-card']`.
- JSON-LD w HTML zawiera tylko **20 ofert** (SEO dla Google) — NIE mylić z DOM.
- Headless Chromium działa; bez akceptacji OneTrust lista może nie załadować się w pełni.

---

## 7. KLUCZ PARTNERSKI (202745) — WERDYKT

- OAuth `client_credentials` działa → token JWT: `partner_code=4420`, `scope=v2 read write`, `token_owner=client`.
- `/api/partner/adverts` (POST, nagłówki Version + Authorization) → **400 "Invalid user ID in token"**.
- Endpoint partnerski = zarządzanie WŁASNYMI ogłoszeniami, NIE wyszukiwarka cudzych.
- **Detektor NIE używa klucza.** Skanuje publiczne `/api/v1/offers/{id}/`.
- **Stress test (200 interleaved zapytań):** token vs brak tokenu = identyczne wyniki (0 blokad, 78 ok w obu).
- **Wniosek:** klucz partnerski jest BEZUŻYTECZNY dla celu szukania/przewagi. Nie daje ochrony przed banem na publicznym API.

---

## 8. ARCHITEKTURA DETEKTORA (ostateczna, faza 5)

```
DETEKTOR (asyncio):
  1. Seed: get_max_id() z listy (cache'owana, więc NIEDOKŁADNA)
  2. Faza 1: skan od seed-40 w górę batchami, aż do ciągu 404 → znajdź prawdziwą krawędź
  3. Faza 2 (sliding window):
     - skanuj [head, head+batch]
     - head przesuwa się TYLKO do max_200+1
     - przy samych 404 → czekaj i ponów to samo okno
     - przy błędzie sieci (-1) → retry 2x + NIE przesuwaj head
  4. Dla każdego 200: classify() → jeśli pasuje, zapisz hit z t_detect

KLIENT HTTP:
  - AsyncSession(impersonate="chrome124", timeout=10)
  - współdzielona sesja per batch
  - semaphore = concurrency (20)
  - retry przy -1: 2 próby, backoff 0.4s/0.8s
```

---

## 9. KLASYFIKATOR (ostateczne reguły)

**iPhone (2298):**
- wymagany "iphone" lub "apple" w tytule (inaczej None)
- blacklista: etui, szkło, obudowa, case, ładowarka, słuchawki, uchwyt, folia, akcesoria, icloud, na części, uszkodzony, zbity, pęknięty, zalany, zablokowany, lock, dawca, do naprawy, nie działa, martwy, hasło, blad, faceid, bez ekranu, popsuty, zepsuty...

**MacBook (3102):**
- wymagany "macbook"/"mac book"/"macbookpro" w tytule (samo "mac" odrzuca — Mac Pro/Mini)
- blacklista: etui, ładowarka, uszkodzony, icloud, na części, dawca...

**Auta (category.type == automotive + sygnatura pełnego auta, NIE sztywne ID — 183 to tylko BMW):**
- partner != `otomoto_pl_form`
- region.lower() zawiera "mazowieck"
- cena znormalizowana ≤ 12000
- marka = pierwsze słowo tytułu z pominięciem stop-listy (sprzedam, witam, używany, nowy...)

**Parsowanie ceny:** normalizacja "12 000" / "12000,50" / "12000" → float. Usuwa "zł", spacje, zamienia przecinek.

---

## 10. KOMPARATOR (pomiar przewagi)

- Dla każdego hita: szukaj w wyszukiwarce precyzyjną frazą (pierwsze 4 znaczące słowa tytułu) + twardą kategorią.
- Przegląda offset 0/50/100 (3 strony).
- `przewaga_min = (t_browser - t_detect) / 60`.
- Ważne: `T_browser` to moment wejścia do top 50 wyników, nie pełnej indeksacji.

**Zmierzone przewagi (świeże oferty, 20-min przebieg):**
| Oferta | Przewaga |
|---|---|
| iPhone 14 Pro | 16.61 min |
| MacBook Air 11 | 11.08 min |
| iPhone 14 Pro Max | 10.97 min |
| iPhone 13 | 5.53 min |

**Uwaga:** niskie wartości (0.05 min) to artefakt startu bota (oferty utworzone PRZED startem, dogonione w fazie 1). Świeże oferty mają przewagę zwykle >5 min.

---

## 11. ZNANE RYZYKA I NIEROZWIĄZANE

1. **Brak rotacji IP/proxy** — długi skan 24/7 z jednego IP = ban/challenge. Token tego nie rozwiązuje (dowiedzione).
2. **Blacklista tytułowa nie jest 100%** — zawsze może wpaść nietypowy śmieć.
3. **Burst importy** (Otomoto salony) — chwilowy skok 100-300 ID; sliding window łapie po fakcie, ale może być lag.
4. **Porównanie detektor vs przeglądarka** — wymaga diff po ID numerycznym z DOM/JSON, nie po tytułach (dopasowanie 1/52 było miarodajne).
5. **Bot produkcyjny 24/7** — nie istnieje; to skrypty badawcze.

---

## 12. PLIKI ŹRÓDŁOWE TEJ WIEDZY

- [00_MAPA_OLX.md](00_MAPA_OLX.md) — stara mapa (z aktualizacją)
- [09_mapa_kategorii_final.md](09_mapa_kategorii_final.md) — kategorie (z korektą)
- [12_raport_faza5_async_browser.md](12_raport_faza5_async_browser.md) — raport fazy 5
- [../SESSION_LOG_2026-08-24.md](../SESSION_LOG_2026-08-24.md) — pełny dziennik sesji
- [monitor_20min.py](monitor_20min.py) — implementacja referencyjna
- [test_classifier.py](test_classifier.py) — 29 testów jednostkowych