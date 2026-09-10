# Analiza wyprowadzalności ID i parametrów checkoutu Vinted — czy da się je przewidzieć/wyliczyć?

**Data:** 2026-08-31
**Metoda:** dekompilacja APK (jadx) + captured_requests.json + kod bota + analiza enumów Retrofit
**Konwencja:** `[UDOWODNIONE]` / `[DOMNIEMANE]`

---

## 1. Werdykt końcowy

**Nie ma master keyów ani dających się przewidzieć ID.** Wszystkie krytyczne identyfikatory checkoutu są **generowane po stronie serwera** i nie da się ich wyliczyć, zgadnąć ani uzyskać "developersko" z pominięciem API. Jedyna rzecz, którą można wyprowadzić lokalnie, to `csrf` (z JWT) i `anon_id` (cookie) — co nasz bot już robi.

---

## 2. Mapa wyprowadzalności każdego parametru

| Parametr | Źródło | Wyprowadzalny? | Metoda |
|---|---|---|---|
| `item_id` | listing (`item.id`) | ✅ ZNANY | z katalogu |
| `seller_id` | listing (`item.user.id`) | ✅ ZNANY | z katalogu |
| `csrf` | payload JWT `access_token_web` | ✅ DERIVOWALNY | [csrf_z_cookies](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py#L71-L82) |
| `anon_id` | cookie `anon_id` | ✅ ZNANY | z cookies |
| `sdk_instance_id` | `GET /j3r4zw/v1/config` | ✅ POBRANY (darmowy GET) | [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py#L49) |
| `X-Incognia-Request-Token` | HKDF(sdk_instance_id) → AES-GCM | ✅ DERIVOWALNY | Node.js `generate_incognia_token.js` |
| **`transaction_id`** | `POST /conversations` | ❌ **SERWEROWY** | nieprzewidywalny, kolejny ID |
| **`shipping_order_id`** | odpowiedź `/conversations` | ❌ **SERWEROWY** | nieprzewidywalny |
| **`checkout_id` (purchase_id)** | `POST /checkout/build` | ❌ **SERWEROWY** | losowy string (np. `eWjYk_Oxxq3qOpWC4gee4`) |
| **`checksum`** | odpowiedź build/PUT | ❌ **SERWEROWY** | wartość kryptograficzna `a|b` |
| **`rate_uuid`** | odpowiedź build | ❌ **SERWEROWY** | UUID |
| **`point_code`/`point_uuid`** | `GET nearby_pickup_points` | ❌ **SERWEROWY** (ale `suggested_shipping_point_code` daje domyślny) | |

---

## 3. Hardcoded UUID / master keys — CZY SĄ?

[UDOWODNIONE] W APK są setki UUID, ale **żaden nie jest master keyem checkoutu**. To identyfikatory wewnętrznych SDK:

- `00000000-0000-0000-0000-000000000000` — null placeholder
- UUID jak `94628ee5-fe99-436d-94b5-f3270ad06529` / `...6530` — identyfikatory bibliotek trzecich (Braze/Adyen/Facebook)
- `OT-App-Id`, `gmpAppId`, `ga_app_id`, `wx_app_id` — ID aplikacji Google/Braze/WeChat, nie Vinted

**Wniosek [UDOWODNIONE]:** brak statycznego sekretu, który odblokowałby checkout. Klucze Incognia (`HKDF salt`) są **znane** i już wykorzystane w `generate_incognia_token.js`, ale to warstwa sygnałów, nie ID transakcji.

---

## 4. Kluczowy trop: `type: "item"` vs `type: "transaction"` w buildzie

W [test_incognia_sequence.py](file:///f:/PROJEKTY/vinted/bot/scripts/test_incognia_sequence.py#L88-L89) build był próbowany z:
```python
{"purchase_items": [{"id": item_id, "type": "item"}]}   # ← type=item, id=item_id
```
zamiast produkcyjnego:
```python
{"purchase_items": [{"id": txn_id, "type": "transaction"}]}  # ← type=transaction, id=transaction_id
```

**Rozstrzygnięcie [UDOWODNIONE]:** enum `PurchaseType` w APK ma **wyłącznie** wartości:
```java
transaction, push_up, closet_promotion, direct_donation, return_label
```
**`"item"` NIE jest poprawnym typem.** To była eksploracyjna próba, nie działający skrót. Poprawny typ do zakupu to wyłącznie `"transaction"`.

Pozostałe typy (`push_up`, `closet_promotion`, `direct_donation`, `return_label`) dotyczą innych operacji — **żaden nie jest szybszym zakupem**.

---

## 5. Co daje strona listingu vs item page — minimalna wiedza

[UDOWODNIONE — na podstawie kodu bota i captured_requests]:

**Ze strony listingu (`GET /catalog/items`)** masz już wszystko do **rozpoczęcia** flow:
- `item_id`, `seller_id` → wystarczy do `POST /conversations`

**Z item page (`GET /items/{id}`)** dostajesz **więcej**, ale nic z tego nie skraca checkoutu:
- HTML + `__CONFIG__` (Incognia API key, DataDome key) — tylko do inicjalizacji SDK
- Te same `item_id` i `seller_id` co w listingu

**Wniosek [UDOWODNIONE]:** wejście na item page **nie jest potrzebne** do buildu — potwierdzone wcześniej. Listing daje 100% danych wejściowych do `conversations`.

---

## 6. Co jest NIE-przewidywalne (twarde granice)

| ID | Dlaczego nieprzewidywalny |
|---|---|
| `transaction_id` | kolejny monotoniczny ID serwera (widoczne przyrosty `21916128383` → `21921244747`) |
| `shipping_order_id` | serwerowy, powiązany z transakcją |
| `checkout_id` | losowy string 22-znakowy (base64) |
| `checksum` | kryptograficzna suma stanu checkoutu |

**Żadnego z nich nie da się wyliczyć, zgadnąć ani przewidzieć.** Muszą być pobrane z API w odpowiedniej kolejności.

---

## 7. Rekomendacje (co realnie można zoptymalizować)

1. **[WYSOKI]** Pre-filter `POST checkout/purchases/check_availability` z batch `itemIds[]` — odfiltruj niedostępne itemy **zanim** zapłacisz koszt `conversations` (~1.5 s).
2. **[WYSOKI]** Pre-warm `X-Incognia-Request-Token` w tle (cache TTL) — eliminacja subprocesu Node na zakup.
3. **[ŚREDNI]** Pomijalne GET-y: `payment_methods` (znasz `pay_in_method_id`), `pickup_points` (użyj `suggested_shipping_point_code`).
4. **[ŚREDNI]** `payment/continue` do retry bez re-buildu.
5. **[POZA KODEM]** Karta bez 3DS / BLIK.

**Nie ma drogi do przewidzenia ID.** Sekwencja `conversations → build → PUT → payment` z pobieraniem ID po drodze jest jedyną ścieżką.

---

## Źródła

- [captured_requests.json](file:///f:/PROJEKTY/vinted/vinted/dane/captured_requests.json) — sekwencja ID i statusów
- [config.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/config.py) — CSRF z JWT, stałe
- [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py) — flow i build body
- [test_incognia_sequence.py](file:///f:/PROJEKTY/vinted/bot/scripts/test_incognia_sequence.py) — trop `type: "item"`
- `PurchaseType.java` (jadx) — enum typów
- `strings_clean.txt` — skan hardcoded UUID

---

*Koniec analizy wyprowadzalności ID.*