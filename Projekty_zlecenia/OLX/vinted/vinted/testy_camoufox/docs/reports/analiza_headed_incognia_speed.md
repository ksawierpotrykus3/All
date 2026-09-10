# Analiza headed testu: wynik_headed_incognia_speed.json

Data testu: 2026-08-29 14:43:58 – 14:44:53
Test: `test_headed_incognia_speed.py` — headed Camoufox, przedmiot własny 9807925466.

## Surowe dane

| Krok | Wynik |
|---|---|
| goto_item | 2719 ms (OK) |
| button_ready | +2594 ms (przycisk `item-buy-button` załadowany) |
| reservation_timeout | 30 422 ms — brak redirectu `/checkout?purchase_id=` w ciągu 30 s |
| Incognia | `incognia_keys: []`, `has_Incognia: false` |
| WebGL | dostępny |
| UA | Firefox/152 (Camoufox spoof działa) |

## Ocena hipotez

### (3) Brak Incognia w headless i headed — POTWIERDZONE, to główny powód
- W trybie headed SDK Incognia w ogóle się nie załadowało: żadnych kluczy `Incognia` na `window`, `has_Incognia: false`.
- Z wcześniejszych testów (wynik_incognia_capture.json) pusta lista `captured` — Incognia nie była łapana też wcześniej.
- Flaga `headless=False` NIE zmienia zachowania SDK — więc przyczyna nie leży w wykrywaniu headless, a w tym, że SDK Incognia albo jest ładowane warunkowo (po spełnieniu sygnałów antyfraud/środowiskowych, których Camoufox nie dostarcza), albo jest blokowane/opóźnione i inicjalizuje się dopiero w ścieżce realnego kliknięcia z pełną telemetrią.
- Skrypt klika przycisk przez `element.click()` w JS — bez realnych zdarzeń trusted (mouse event z `isTrusted: true`). Frontend Vinted może wymagać sygnału Incognia przy rezerwacji; bez SDK i bez trusted click request `checkout/build` prawdopodobnie w ogóle nie został wysłany albo został cicho odrzucony → stąd brak jakiegokolwiek redirectu przez 30 s.

### (1) Wygasła sesja — MAŁO PRAWDOPODOBNA jako główna przyczyna
- Sesja była ważna 2026-08-28 13:44 (users/current zwróciło usera 3180346878). Test headed odpalony ~25 h później — sesja cookie mogła wygasnąć lub zostać unieważniona.
- ALE: strona przedmiotu i przycisk "Kup teraz" załadowały się poprawnie. Przy martwej sesji Vinted typowo odsyła do logowania lub pokazuje przycisk, który prowadzi do /member/signup. Brak redirectu do logowania w danych, choć test zapisuje tylko `/checkout?purchase_id=`, więc nie da się tego wykluczyć na 100% — jednak nawet zalogowany użytkownik bez Incognia dostał wcześniej HTTP 500 `server_error` na `checkout/build` (wynik_rezerwacja_realna.json, 2026-08-28), co pokazuje, że antyfraud blokuje rezerwację niezależnie od sesji.

### (2) Przedmiot zarezerwowany/sprzedany — ODRZUCONE
- `button_ready` przeszedł: przycisk `item-buy-button` istniał w DOM. Test klika go przez `.click()` bez sprawdzenia `disabled`, ale przy zarezerwowanym/sprzedanym przedmiocie Vinted nie renderuje aktywnego przycisku "Kup teraz" tylko status "Zarezerwowane"/"Sprzedane". To własny przedmiot testowy, wybrany właśnie po to, żeby był dostępny.

## Wniosek — przyczyna timeoutu 30 s

Timeout 30 s to objaw, nie własna przyczyna: po kliknięciu nie pojawił się ŻADEN request prowadzący do `/checkout?purchase_id=`. Najbardziej prawdopodobna kolejność zdarzeń:

1. Klik syntetyczny (`el.click()`, `isTrusted: false`, bez `humanize` na tym konkretnym elemencie — `humanize=True` działa tylko dla API Playwright, nie dla `page.evaluate`).
2. Frontend Vinted przy "Kup teraz" wymaga tokena Incognia; SDK niezaładowane → request `checkout/build` nie został wysłany lub odrzucony po stronie klienta/serwera bez redirectu.
3. Wygaszenie sesji (~25 h od weryfikacji) to możliwy czynnik dodatkowy, ale nie konieczny do wytłumaczenia timeoutu — blokada antyfraud (brak Incognia) wystarczy i jest spójna z wcześniejszym HTTP 500 `server_error` na `checkout/build` z świeżą sesją.

## Rekomendacje (bez nowych testów)

- Klikać przez `page.click()` / locator API (generuje trusted events + humanize), nie przez `evaluate -> el.click()`.
- Odświeżyć sesję bezpośrednio przed testem i logować, czy klik prowadzi do redirectu logowania.
- Diagnozować, dlaczego SDK Incognia nie ładuje się w Camoufox (sprawdzić requesty do domen Incognia, CSP, blokery; porównać z realnym Firefoksem) — to blokada krytyczna dla rezerwacji.
- Dodatkowo warto przechwytywać request `checkout/build` i jego status w timeout-cie, żeby odróżnić "request nie wysłany" od "odrzucony".
