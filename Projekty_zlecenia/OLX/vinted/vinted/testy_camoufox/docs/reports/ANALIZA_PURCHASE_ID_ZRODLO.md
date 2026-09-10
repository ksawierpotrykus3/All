# PURCHASE_ID — GDZIE JEST GENEROWANY I CZY DA SIĘ WYMUSIĆ

**Data:** 2026-08-31
**Metoda:** analiza APK (jadx) + realna odpowiedź conversations + kod bota
**Konwencja:** `[UDOWODNIONE]` (z kodu/danych)

---

## Werdykt kluczowy

**`purchase_id` jest identyfikatorem checkoutu (checkout_id), NIE transakcji.**

Powstaje wyłącznie po stronie backendu i **nie da się go wymusić z `conversations` ani żadnego innego endpointu** — jedyne źródło generowania to `checkout/build`.

---

## Wszystkie miejsca, gdzie pojawia się purchase_id [UDOWODNIONE]

### 1. `conversations` → `transaction.purchase_id`
Realna odpowiedź (`conv_resp_1788178897.json`):
```json
"transaction": {
  "id": 21941610014,
  "shipping_order_id": 24878132949,
  "purchase_id": null,          // ← null dla świeżej transakcji
  ...
}
```
`purchase_id` jest **null** przy świeżej transakcji. Nie-null tylko gdy checkout dla tej pary (item+seller) **już istnieje** (retry).

### 2. `checkout/build` → `checkout.id`
```json
{"checkout":{"id":"srJQA6tHL1mDH3ap_FBTx","components":{...}}}
```
`checkout.id` = `purchase_id`. To jest **jedyne miejsce, gdzie purchase_id jest tworzony**.

### 3. `check_availability` → NIE zwraca purchase_id
`Purchase.java`:
```java
public final class Purchase {
    private final boolean purchaseAvailable;  // tylko bool dostępności
    private final ItemUser user;
    private final Items items;                // unavailable_list per item
}
```
Brak pola `id`/`purchaseId`. To tylko pre-check dostępności, nie źródło identyfikatora.

---

## Czy da się wymusić purchase_id z conversations? [UDOWODNIONE: NIE]

`conversations` zwraca `transaction.purchase_id = null` dla nowej transakcji i **nie ma parametru żądania**, który by wymusił utworzenie checkoutu. Checkout powstaje dopiero przy `checkout/build`.

---

## Wniosek operacyjny

| Sytuacja | Droga do purchase_id | Koszt |
|---|---|---|
| Nowy przedmiot | `conversations` → build → `checkout.id` | build nieunikniony (~1.7s) |
| Retry tego samego | `conversations` → `transaction.purchase_id` (istnieje) | brak buildu |

Nie ma alternatywnego źródła. Dla nowego zakupu **build jest obowiązkowy**, bo to jedyny endpoint tworzący checkout (i tym samym `purchase_id`).

---

## Źródła

- `conv_resp_1788178897.json` — conversations: transaction.purchase_id = null
- `build_body_1788177293.json` — build: checkout.id = purchase_id
- `Purchase.java` — check_availability NIE ma purchase_id
- `detection.py` — logika skip-build (purchase_id z conversations tylko przy retry)
- `CheckoutApi.java` — build (initiateCheckout) vs GET checkout

---

*Koniec analizy.*