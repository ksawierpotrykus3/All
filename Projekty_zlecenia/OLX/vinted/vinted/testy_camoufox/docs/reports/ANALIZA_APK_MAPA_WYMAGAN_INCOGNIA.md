# MAPA WYMAGAŃ INCOGNIA PER ENDPOINT (analiza APK)

**Data:** 2026-08-31
**Źródło:** dekompilacja APK `jadx_out` (Retrofit interfejsy)
**Konwencja:** `[UDOWODNIONE]` (z kodu źródłowego APK)

---

## Przełomowe odkrycie [UDOWODNIONE]

**Tylko 2 endpointy wymagają nagłówka `X-Incognia-Request-Token`.** Cała reszta flow checkoutu/płatności chroniona jest wyłącznie cookies + CSRF + DataDome.

---

## Pełna mapa endpointów (z dekompilacji)

| Endpoint | Metoda | Nagłówek Incognia | Źródło (klasa) |
|---|---|---|---|
| `purchases/checkout/build` | POST | ✅ **WYMAGANY** | `CheckoutApi.initiateCheckout` |
| `purchases/{id}/checkout` | PUT | ❌ brak | `CheckoutApi.updateCheckout` |
| `purchases/{id}/checkout` | GET | ❌ brak | `CheckoutApi.getSingleCheckoutData` |
| `purchases/{id}/checkout/payment` | POST | ✅ **WYMAGANY** | `PaymentsApi.initiatePayment` |
| `purchases/{purchase_id}/checkout/payment/continue` | POST | ❌ brak | `PaymentsApi.getContinuePayment` |
| `purchases/{id}/checkout/payment` | GET | ❌ brak | `PaymentsApi.getPayment` |
| `purchases/{purchaseId}/checkout/payment/failure` | POST | ❌ brak | `PaymentsApi.failPayment` |
| `checkout/purchases/check_availability` | POST | ❌ brak | `GatewayCheckoutApi.checkItemsAvailability` |

---

## Struktury requestów [UDOWODNIONE]

### `CheckoutInitiateRequest` (checkout/build)
```json
{ "purchaseItems": [PurchaseItem] }  // PurchaseItem = {id, type}
```

### `CheckoutUpdateRequest` (PUT checkout)
```json
{ "components": Object }
```

### `PaymentRequest` (payment + payment/continue)
```json
{
  "firebaseAppInstanceId": "string|null",
  "checksum": "string|null",
  "paymentOptions": PaymentOptions
}
```

### `PaymentOptions` — pełna struktura [UDOWODNIONE]
```json
{
  "browserInfo": BrowserThreeDsTwoData,      // dane przeglądarki dla 3DS2
  "googlePayMetadata": GooglePayMetadata,    // Google Pay
  "blikCode": "string|null",                 // BLIK
  "paymentToken": "string|null",             // token PSP (np. Adyen)
  "encryptedCardDetails": EncryptedCardDetails, // karta szyfrowana
  "singleUseCard": "boolean|null",           // karta jednorazowa
  "secure_3ds_details": Secure3dsDetails     // dane 3DS (serializedName)
}
```

Kluczowe: `secure_3ds_details` ma `@SerializedName` (snake_case) — reszta jest camelCase. To ma znaczenie przy ręcznym budowaniu body.

### `CheckItemsAvailabilityRequest` (check_availability)
```json
{ "buyerId": "string|null", "itemIds": ["...", "..."] }  // BATCH!
```

### `CheckItemsAvailabilityResponse`
```
purchase | reservation | markAsSold
```

---

## Wnioski strategiczne

1. **[UDOWODNIONE]** `payment/continue` **NIE wymaga świeżego buildu ani tokenu Incognia** — wystarczy `purchase_id` + `PaymentRequest`. To droga retry krótsza o build (~1.6s) i bez zależności od Incognii.

2. **[UDOWODNIONE]** `check_availability` przyjmuje **batch `itemIds[]`** i NIE wymaga Incognii — idealny pre-filter pollera (sprawdzenie dostępności wielu przedmiotów naraz bez kosztu checkoutu).

3. **[UDOWODNIONE]** Incognia jest bramką tylko na **`checkout/build`** i **`initiatePayment`**. Jeśli te dwa przejdą (uzyskamy 200), reszta flow jest osiągalna bez SDK Incognia w pętli.

---

## Źródła

- `jadx_out/sources/com/vinted/feature/checkout/api/CheckoutApi.java`
- `jadx_out/sources/com/vinted/feature/payments/api/PaymentsApi.java`
- `jadx_out/sources/com/vinted/feature/checkout/api/GatewayCheckoutApi.java`
- `jadx_out/sources/com/vinted/feature/paymentsauthorization/api/request/PaymentRequest.java`
- `jadx_out/sources/com/vinted/feature/checkout/api/request/CheckItemsAvailabilityRequest.java`

---

*Koniec analizy.*