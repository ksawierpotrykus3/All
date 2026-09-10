# Endpointy transakcyjne i ścieżka buildu bez strony przedmiotu

**Data:** 2026-08-31
**Konwencja dowodowa:** `[UDOWODNIONE]` / `[DOMNIEMANE]`
**Zakres:** ustalenia dot. dwóch endpointów transakcyjnych, braku wymogu wejścia na `/items/{id}`, oraz relacji `purchase_id`/`order_id` do URL strony checkoutu.

---

## 1. Dwa endpointy tworzące transakcję

Oba tworzą transakcję przy „Kup teraz", ale różnią się zakresem odpowiedzi i przeznaczeniem.

| | `POST /api/v2/conversations` (STARY) | `POST /messaging/main/inquiries` (NOWY) |
|---|---|---|
| Domena | `www.vinted.pl` | `api.vinted.pl` |
| Body | `{"initiator":"buy","item_id":int,"opposite_user_id":int}` | `{"item_ids":[str],"receiver_id":str}` |
| `transaction_id` | w `conversation.transaction.id` | top-level |
| `shipping_order_id` | ✅ zwraca | ❌ nie zwraca |
| `purchase_id` | `transaction.purchase_id` | brak |
| Czas (pomiar) | ~719 ms | ~938 ms |

**Dowód [UDOWODNIONE]:** [probe_new_endpoint_out.txt](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/logs/probe_new_endpoint_out.txt) — ten sam przedmiot, oba wywołane po sobie, zwróciły **ten sam `transaction_id` `21921244747`**.

**Wniosek:**
- [UDOWODNIONE] Właściwy endpoint produkcyjny to **`/conversations`** — jest szybszy i daje pełny kontekst transakcji (w tym `shipping_order_id`, niezbędny dla `nearby_pickup_points`).
- [DOMNIEMANE] `/inquiries` to nowy backend messagingu („inquiry" = zgłoszenie chęci zakupu), eksperymentalny i nieprodukcyjny dla checkoutu — nie zwraca `shipping_order_id`.
- Kod produkcyjny używa `/conversations` ([detection.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/detection.py#L157-L189)); `INQUIRIES_URL` w [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py#L40) pozostaje niewykorzystany.

---

## 2. Build bez wchodzenia na stronę przedmiotu

[UDOWODNIONE] Wejście na `https://www.vinted.pl/items/{id}` **nie jest wymagane** do zrobienia buildu.

Dane do buildu pochodzą wyłącznie z katalogu:

| Potrzebne | Źródło |
|---|---|
| `item_id` | `GET /catalog/items` → `item.id` |
| `seller_id` | `GET /catalog/items` → `item.user.id` |
| `transaction_id` + `shipping_order_id` | `POST /conversations` |
| `checkout_id` + `checksum` | `POST /checkout/build` |

[checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L134-L270) woła `zrealizuj_zakup(o.id, o.seller_id, konto)` z callbacka monitora — `o.id`/`o.seller_id` to pola z odpowiedzi katalogu. Referer do strony przedmiotu nie jest wymagany; produkcyjny `_build` używa ogólnego `Referer: https://www.vinted.pl/` i przechodzi 200 (dowód w [captured_requests.json](file:///f:/PROJEKTY/vinted/vinted/dane/captured_requests.json#L430)).

---

## 3. Relacja purchase_id / order_id do URL strony checkoutu

URL strony checkoutu ma postać:

```
https://www.vinted.pl/checkout?purchase_id={checkout_id}&order_id={transaction_id}&order_type=transaction
```

| Param | Wartość | Źródło |
|---|---|---|
| `purchase_id` | `checkout.id` z odpowiedzi buildu (nie ma osobnego pola „purchase_id" — to ten sam identyfikator) | build |
| `order_id` | `transaction_id` z `/conversations` | conversations |
| `order_type` | stała `transaction` | — |

**Dowód [UDOWODNIONE]:** [checkout_sequence_from_har.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/core/checkout/checkout_sequence_from_har.json) — `purchase_id=eWjYk_Oxxq3qOpWC4gee4` (checkout.id) + `order_id=21872241924` (transaction_id).

---

## 4. Strona checkoutu NIE jest shortcutem

[DOMNIEMANE — ocena architektoniczna] Wejście na `https://www.vinted.pl/checkout?purchase_id=...` to renderowana strona SPA (frontend HTML), nie API:

1. Wymaga przeglądarki (Camoufox/Playwright), co dodaje warstwę narzutu.
2. Strona i tak pod spodem woła te same endpointy, które bot robi bezpośrednio przez curl_cffi:
   - `PUT /api/v2/purchases/{id}/checkout` (metoda płatności + pickup),
   - `POST /api/v2/purchases/{id}/checkout/payment` → `redirect_url` do bramki Adyen.

**Wniosek:** dla produkcyjnego wyścigu o ofertę bot przez czyste API (`build → PUT → payment`) jest szybszy i nie potrzebuje strony checkoutu. Otwarcie strony ma sens tylko dla manualnego testu/debugu wizualnego.

---

## 5. Pomiń build tylko przy istniejącym checkout

[UDOWODNIONE] `purchase_id` w `conversations` jest `null` dla świeżej transakcji — build jest krokiem, który **tworzy** ID checkoutu. Pominięcie buildu („skip-build": `conversations → PUT → payment`) działa wyłącznie dla itemów z już istniejącym checkoutem ([checkout_skip_build_full.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/checkout_skip_build_full.py#L94-L98)), nie dla nowej oferty.

---

## 6. Najkrótsza realna ścieżka dla świeżego itemu

```
catalog → conversations → build → [PUT payment_method ∥ GET pickup_points] → PUT pickup_details → payment
```

- Do buildu: ~2.7–3.2 s (floor serwerowy: conversations ~1.2–1.5 s + build ~1.5–1.6 s).
- Do bramki: ~7.5–10 s (payment floor ~2.5–2.7 s).

---

## 7. Co jest potrzebne do payment i skąd wziąć dane BEZ buildu

### 7.1 Endpoint payment

```
POST https://www.vinted.pl/api/v2/purchases/{purchase_id}/checkout/payment
```

Body (dokładnie to w [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py#L119-L131), potwierdzone HAR `content-length: 235`):

```json
{
  "checksum": "<krytyczne>",
  "payment_options": {
    "browser_info": {
      "language": "pl",
      "color_depth": 24,
      "java_enabled": false,
      "screen_height": 1080,
      "screen_width": 1920,
      "timezone_offset": -120
    }
  }
}
```

Tylko **dwa dynamiczne pola**: `{purchase_id}` w URL i `checksum` w body. `browser_info` to stały fingerprint.

### 7.2 Skąd wziąć każdą wartość BEZ buildu

| Wartość | Źródło bez buildu | Dowód |
|---|---|---|
| `purchase_id` | `POST /conversations` → `conversation.transaction.purchase_id` | tylko jeśli checkout już istniał |
| `checksum` | odpowiedź `PUT /purchases/{id}/checkout` (rekurencyjnie `_find_checksum`) | [wynik_skip_build_full.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/wynik_skip_build_full.json) `checksum: true` |
| `so_id`, `lat`, `lon`, `rate_uuid` | ta sama odpowiedź PUT → `components.shipping_address` + `components.shipping_pickup_details` | jw. `so_id: 24808608689`, `lat/lon`, `rate_uuid` |
| `point_code`/`point_uuid` | `GET nearby_pickup_points` (z so_id + lat/lon z PUT) | `pickup_points done: n=15, sug=4303773` |

Pełny łańcuch bez buildu (udokumentowany w [checkout_skip_build_full.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/checkout_skip_build_full.py)):

```
conversations → purchase_id
→ PUT payment_method   → checksum + so_id + coords + rate_uuid
→ GET pickup_points    → point_code/point_uuid
→ PUT pickup_details   → FINALNY checksum
→ POST payment         → checksum + browser_info
```

### 7.3 Kluczowe ograniczenia (dwa)

1. **`purchase_id` jest `null` dla świeżego itemu.** [checkout_skip_build_new.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/checkout_skip_build_new.py) dowodzi: `conversations` na nowej transakcji zwraca `purchase_id: null`. Bez buildu nie ma purchase_id → nie ma do czego robić PUT/payment. Skip-build działa **tylko dla retry** (checkout już istniał).

2. **Payment i tak dostał 403 DataDome.** W [wynik_skip_build_full.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/wynik_skip_build_full.json) cała ścieżka bez buildu przeszła (PUT 200, pickup 200, PUT 200), ale sam `payment` zwrócił **403 z CAPTCHA**. Problem nie leży w braku buildu, lecz w blokadzie DataDome na warstwie transportowej.

**Wniosek:** wszystkie informacje do paymentu (checksum, so_id, koordynaty, rate_uuid, punkt odbioru) pochodzą z odpowiedzi **PUT**, nie z buildu. Buildu potrzeba wyłącznie po to, by **wygenerować `purchase_id`** dla świeżego przedmiotu. Nawet działający flow bez buildu kończy się 403 na payment — to DataDome, nie brak danych.

---

## Źródła

- [probe_new_endpoint_out.txt](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/logs/probe_new_endpoint_out.txt)
- [detection.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/detection.py)
- [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py)
- [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py)
- [captured_requests.json](file:///f:/PROJEKTY/vinted/vinted/dane/captured_requests.json)
- [checkout_sequence_from_har.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/core/checkout/checkout_sequence_from_har.json)
- [checkout_skip_build_full.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/checkout_skip_build_full.py)
- [checkout_skip_build_new.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/checkout_skip_build_new.py)
- [checkout_skip_build_put.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/checkout_skip_build_put.py)
- [wynik_skip_build_full.json](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/wynik_skip_build_full.json)
- [probe_build_isolated.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/probe_build_isolated.py)

---

*Koniec dokumentacji ustaleń.*