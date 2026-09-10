# Analiza zdekmpilowanego APK Vinted 26.33.1 — pełny mapping endpointów checkout i możliwości optymalizacji

**Data:** 2026-08-31
**Źródło:** dekompilacja `fr.vinted.apk` (jadx 1.5.6), interfejsy Retrofit w `com/vinted/feature/*/api`
**Konwencja:** `[UDOWODNIONE]` / `[DOMNIEMANE]`

---

## 1. Pełny mapping endpointów checkoutu (z dekompilacji — UDOWODNIONE)

### 1.1 `CheckoutApi` (checkout)
```java
@POST("purchases/checkout/build")                    // initiateCheckout(@Header "X-Incognia-Request-Token")
@PUT("purchases/{id}/checkout")                       // updateCheckout(@Body CheckoutUpdateRequest)
@GET("purchases/{id}/checkout")                       // getSingleCheckoutData
```

### 1.2 `PaymentsApi` (płatność)
```java
@POST("purchases/{id}/checkout/payment")              // initiatePayment(@Header "X-Incognia-Request-Token")
@GET("purchases/{id}/checkout/payment")               // getPayment
@POST("purchases/{purchaseId}/checkout/payment/failure")   // failPayment(@Body {reason})
@POST("purchases/{purchase_id}/checkout/payment/continue") // getContinuePayment
```

### 1.3 `PaymentOptionsApi` (metody płatności)
```java
@GET("purchases/{id}/checkout/payment_methods")       // getPaymentMethods
```

### 1.4 `GatewayCheckoutApi` (pre-walidacja)
```java
@POST("checkout/purchases/check_availability")        // checkItemsAvailability(@Body {buyerId, itemIds[]})
```

### 1.5 `PaymentAuthorizationApi`
```java
@POST("users/{user_id}/user_2fa/ensure")              // startScaFlow (3DS/2FA)
@GET("purchases/{purchaseId}/payment_methods/google_pay/configurations")
```

### 1.6 `ReserveApi` (rezerwacja)
```java
@DELETE("items/{item_id}/reservation")                // unReserveItem
```

### 1.7 `ConversationApi` (transakcje)
```java
@POST("conversations")                                // createNewConversation (stary backend)
@POST("transactions/{transaction_id}/reservation")    // changeOrderReservation
@PUT("transactions/{transaction_id}/complete")        // completeTransaction
@GET("transactions/{transaction_id}")                 // getTransaction
```

### 1.8 `NewConversationApi` (nowy backend messaging)
```java
@POST("messaging/main/inquiries")                     // createConversation (NOWY endpoint)
```

---

## 2. Kluczowe ustalenia: struktura danych (UDOWODNIONE)

### 2.1 `NewBackendCheckoutDto` — odpowiedź buildu
```java
{ id: String, checksum: String, components: List<PluginData> }
```
- **`id`** = `purchase_id` (identyfikator checkoutu)
- **`checksum`** = to samo, co `_find_checksum` w naszym kodzie
- **`components`** = lista pluginów (shipping_address, payment_method, shipping_pickup_details itd.)

### 2.2 `PurchaseType` — pełne wartości enum
```java
transaction, push_up, closet_promotion, direct_donation, return_label
```
Nasz kod używa wyłącznie `"transaction"` — poprawnie. Pozostałe typy dotyczą innych operacji (wypychanie ofert, promocje, darowizny, etykiety zwrotne).

### 2.3 `PaymentRequest` — wymagane pola do płatności
```java
{ firebaseAppInstanceId: String, checksum: String, paymentOptions: PaymentOptions }
```

### 2.4 `PaymentOptions` — pełna struktura (to jest NOWOŚĆ!)
```java
{
  browserInfo: BrowserThreeDsTwoData,      // 3DS2 browser info
  googlePayMetadata: GooglePayMetadata,     // Google Pay
  blikCode: String,                         // BLIK
  paymentToken: String,
  encryptedCardDetails: EncryptedCardDetails,  // karta
  singleUseCard: Boolean,
  secure3dsDetails: Secure3dsDetails        // @SerializedName("secure_3ds_details")
}
```

---

## 3. Odpowiedzi na nierozwiązane pytania

### 3.1 Czy można pominąć build? [UDOWODNIONE]
**NIE dla świeżego przedmiotu.** `purchase_id` (czyli `checkout.id`) powstaje dopiero w `POST /checkout/build`. Potwierdzone w dekompilacji: `NewBackendCheckoutDto.id` jest zwracany wyłącznie przez `initiateCheckout` (build).

### 3.2 Czy można pominąć PUT? [DOMNIEMANE — częściowo]
`updateCheckout` (PUT) to jedyne miejsce, gdzie wysyła się `components` (metoda płatności, pickup). Bez niego checkout pozostaje w stanie domyślnym. **ALE** — dekmpilacja pokazuje, że build zwraca `components` jako listę pluginów; możliwe, że domyślne wartości wystarczą do `payment`. Nasz wcześniejszy test `test_minimal_checkout.py` (build → PUT puste → payment) sugeruje, że PUT z pustymi komponentami daje 200 — warto przetestować **pominięcie PUT w ogóle**.

### 3.3 Czy można pominąć `GET payment_methods` i `GET pickup_points`? [UDOWODNIONE]
- `getPaymentMethods` (`GET .../payment_methods`) — **NIE jest wymagane**, jeśli znamy `pay_in_method_id` z góry (u nas: karta = "1", P24 = "12").
- `pickup_points` (shipping-estimation) — potrzebne tylko do wybrania punktu odbioru; można użyć domyślnego/suggested.

### 3.4 Czy Incognia jest wymagana? [UDOWODNIONE — WAŻNE]
Tak — `X-Incognia-Request-Token` jest wymagany **na buildzie i na payment**. Co kluczowe: **mobile też go wymaga** (nagłówek w `initiateCheckout` i `initiatePayment`). To ostatecznie falsyfikuje tezę, że mobile ma lżejsze zabezpieczenia.

---

## 4. Możliwości optymalizacji (konkretne)

### 4.1 Pre-warm `X-Incognia-Request-Token` [WYSOKI zysk]
Skoro token Incognia jest wymagany na buildu i payment, a w naszym kodzie build przechodzi **z pustym tokenem** (`_build(s, txn, "", konto)`), to znaczy, że aktualnie **omijamy** warstwę Incognia — ale to kruche. Jeśli Vinted zacznie egzekwować token, build padnie. 

**Rekomendacja:** pre-generować token Incognia w tle (Node.js subprocess) i cache'ować z krótkim TTL, żeby nie płacić kosztu ~50–200 ms na zakup.

### 4.2 Zrównoleglenie `payment_methods` + `pickup_points` + `availability` [WYSOKI zysk]
Dekompilacja pokazuje 3 niezależne GET-y, które można wykonać równolegle **przed** buildem lub tuż po:
- `check_availability` (pre-walidacja itemu — można zrobić od razu po wykryciu)
- `payment_methods` (jeśli potrzebne)
- `pickup_points` (jeśli znamy so_id)

Nasz kod już równolegle robi `build ∥ pickup_point`. Można pójść dalej: **pre-warm `check_availability` już na etapie pollingu** — odrzucić niedostępne itemy zanim zapłacimy koszt `conversations`.

### 4.3 `check_availability` jako pre-filter [WYSOKI zysk]
`POST checkout/purchases/check_availability` z body `{buyerId, itemIds[]}` pozwala **zbiorczo** sprawdzić dostępność wielu itemów jednym requestem. To idealne do pollera: zamiast sprawdzać item po itemie, wyślij listę i odfiltruj niedostępne.

### 4.4 `payment/continue` — obsługa ponowienia [ŚREDNI zysk]
`POST .../checkout/payment/continue` + `payment/failure` to maszyna stanów płatności. Jeśli payment padnie (3DS, timeout), `continue` pozwala wznowić bez ponownego buildu i całego flow.

### 4.5 Karta bez 3DS / BLIK [WYSOKI zysk — poza kodem]
`PaymentOptions` pokazuje, że BLIK (`blikCode`) i karta (`encryptedCardDetails`, `singleUseCard`) są wspierane. BLIK z kodem może pominąć 3DS. To największy pojedynczy zysk czasowy, ale zależy od konta klienta.

---

## 5. Czego NIE przyspieszymy (twarde granice)

| Element | Granica |
|---|---|
| `conversations` (tworzenie transakcji) | ~1.2–1.5 s serwerowo |
| `build` (tworzenie checkoutu) | ~1.5–1.6 s serwerowo |
| `payment` | ~2.5–2.7 s serwerowo |
| Rate-limit Vinted | ~0.83 req/s |

Żaden skrót po stronie klienta nie usunie tych serwerowych floorów.

---

## 6. Rekomendacje końcowe (priorytetyzowane)

1. **[WYSOKI]** Pre-warm tokenu Incognia w tle (cache TTL) — przygotuj się na egzekwowanie.
2. **[WYSOKI]** Pre-filter `check_availability` w pollerze (batch itemIds).
3. **[WYSOKI]** Test pominięcia `PUT` z pustymi komponentami (build → payment bez PUT).
4. **[ŚREDNI]** `payment/continue` do retry bez re-buildu.
5. **[POZA KODEM]** Karta bez 3DS / BLIK — największy pojedynczy zysk.

---

## Źródła (pliki zdekmpilowane jadx)

- `com/vinted/feature/checkout/api/CheckoutApi.java`
- `com/vinted/feature/checkout/api/GatewayCheckoutApi.java`
- `com/vinted/feature/payments/api/PaymentsApi.java`
- `com/vinted/feature/paymentoptions/api/PaymentOptionsApi.java`
- `com/vinted/feature/paymentsauthorization/api/PaymentAuthorizationApi.java`
- `com/vinted/feature/paymentsauthorization/api/request/PaymentRequest.java`
- `com/vinted/feature/paymentsauthorization/api/request/PaymentOptions.java`
- `com/vinted/feature/item/api/ReserveApi.java`
- `com/vinted/feature/conversation/api/ConversationApi.java`
- `com/vinted/feature/conversation/api/NewConversationApi.java`
- `com/vinted/feature/checkout/api/entity/NewBackendCheckoutDto.java`
- `com/vinted/feature/checkoutpluginbase/api/entity/PurchaseType.java`

---

*Koniec analizy optymalizacyjnej.*