# JAK APLIKACJA PYTA BACKEND O CHECKOUT (po weryfikacjach)

**Data:** 2026-08-31
**Metoda:** dekompilacja APK (CheckoutStateManager.initialize)
**Konwencja:** `[UDOWODNIONE]` (z kodu źródłowego)

---

## Kluczowa funkcja: `CheckoutStateManager.initialize(id, purchaseType, purchaseId)`

Z dekompilacji widać **dokładną logikę** — co app robi, zanim poprosi backend o checkout:

```java
// sygnatura (pseudo):
initialize(String id, PurchaseType purchaseType, String purchaseId) {
    CheckoutApi checkoutApi = this.checkoutApi;
    IncogniaSdkGateway incogniaSdkGateway = this.incogniaSdkGateway;

    // ===== KROK 1: Jeśli purchaseId != null → GET checkout (skip-build) =====
    if (purchaseId != null) {
        // odczyt istniejącego checkoutu
        Single<SingleCheckoutResponse> s = checkoutApi.getSingleCheckoutData(purchaseId);
        // → zwraca { id, checksum, components }
    }

    // ===== KROK 2: W przeciwnym razie → BUILD nowy checkout =====
    else {
        // zbuduj PurchaseItem z id + purchaseType
        PurchaseItem item = new PurchaseItem(id, purchaseType);   // id=transaction_id, type=transaction
        CheckoutInitiateRequest req = new CheckoutInitiateRequest(listOf(item));

        // ===== KROK 3: Incognia (jeśli feature enabled) =====
        String incogniaToken = null;
        if (incogniaFeatureHelper.isIncogniaEnabled()) {
            incogniaToken = incogniaSdkGateway.generateRequestToken();
        }

        // ===== KROK 4: POST checkout/build =====
        Single<SingleCheckoutResponse> s = checkoutApi.initiateCheckout(req, incogniaToken);
        // → zwraca { id (purchase_id), checksum, components }
    }
}
```

---

## Kluczowy wniosek [UDOWODNIONE]

**Aplikacja ma dokładnie dwie ścieżki, bez żadnych „dodatkowych weryfikacji" przed backendem:**

| Warunek | Wywołanie | Co zwraca |
|---|---|---|
| `purchaseId != null` | `GET purchases/{id}/checkout` | istnienie checkoutu → checksum+components (odczyt, bez buildu) |
| `purchaseId == null` | `POST checkout/build` (z Incognia jeśli enabled) | nowy checkout → id+checksum+components |

**Brak etapu „sprawdź dostępność" między weryfikacją a buildem.** `check_availability` (gateway) to **osobny, opcjonalny pre-check UI** — nie jest wywoływany w `initialize`. Aplikacja idzie prosto: ma purchaseId → GET; nie ma → build.

---

## To potwierdza wnioski z wcześniejszych analiz

1. `purchase_id` powstaje **tylko** w `checkout/build` (krok 4).
2. `check_availability` NIE jest częścią ścieżki tworzenia checkoutu — to tylko pre-filter.
3. Przy istniejącym `purchaseId` app używa `GET` (bez buildu, bez Incognii).
4. Incognia token jest generowany **tylko przed buildem** (krok 3), i tylko gdy feature flag on.

---

## Odpowiedź na pytanie „jak app pyta backend po weryfikacjach"

Kolejność w app:
```
initialize(id, type, purchaseId)
  ├─ purchaseId != null ?  GET purchases/{id}/checkout
  └─ else ?  generateRequestToken() [Incognia] → POST checkout/build (purchase_items=[{id,type}])
```

Nie ma pośredniego kroku weryfikacji. Z punktu widzenia API: **albo odczyt istniejącego checkoutu (GET), albo jego utworzenie (build)**.

---

## Źródła

- `CheckoutStateManager.java` — `initialize` (dekompilacja, bytecode w komentarzach)
- `CheckoutApi.java` — `getSingleCheckoutData` + `initiateCheckout`
- `CheckoutInitiateRequest.java` — `purchaseItems: List<PurchaseItem>`
- `PurchaseItem.java` — `{id, type}`

---

*Koniec analizy.*