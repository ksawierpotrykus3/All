# Analiza ukrytych ścieżek, flag i trybów testowych checkoutu Vinted (APK 26.33.1)

**Data:** 2026-08-31
**Metoda:** dekompilacja jadx 1.5.6 + skan stringów (strings_clean.txt) + analiza interfejsów Retrofit i ViewModeli
**Konwencja:** `[UDOWODNIONE]` / `[DOMNIEMANE]`

---

## 1. Werdykt końcowy

**Nie istnieje ukryty, jednokrokowy ani szybszy skrót zakupowy.** Po przebadaniu wszystkich interfejsów API, ViewModeli, eksperymentów A/B i feature flags, potwierdzam: flow zakupowy jest jeden i identyczny z webem (`conversations → build → PUT → payment`). To, co wyglądało na skróty, okazało się nazwami analitycznymi lub eksperymentami UI.

---

## 2. Rozstrzygnięte "falszywe tropy" (UDOWODNIONE)

### 2.1 `instant_buy` — to NIE jest endpoint
Znaleziony w `ItemBuyNowPluginViewModel.onBuyNowClick()`:
```java
UserTargets userTargets = UserTargets.instant_buy;   // ← tylko event analityczny
((VintedAnalyticsImpl) this.vintedAnalytics).click(userTargets, Screen.item, str);
```
`instant_buy` to **nazwa zdarzenia analitycznego** (UserTargets), nie ścieżka zakupu.

### 2.2 "Kup teraz" (BuyNow) = standardowy escrow checkout
`ItemBuyNowPluginViewModel.onBuyClickedInternal()` i `ConversationBuyInteractor.handleConversationBuy()` prowadzą do tego samego:
```java
((CheckoutInitiationMetricsTrackerImpl) tracker).trackEscrowCheckoutInit();
// → nawigacja do checkoutu z (conversationId, transactionId, actions, readAfterWriteToken)
```
Czyli "Kup teraz" najpierw tworzy konwersację/transakcję, potem przechodzi do checkoutu — **dokładnie to samo, co robi nasz bot** (`conversations → build`).

### 2.3 Sandboxowe portale — wewnętrzne feature flags, nie publiczne API
`Portals_svc_checkout_sandbox`, `Portals_svc_payments_sandbox` itd. to **nazwy feature flags** (Portals = system konfiguracji backendu), wskazujące na wewnętrzne środowiska sandbox. Niedostępne z zewnątrz.

### 2.4 `/v2/purchase` — fragment klasy, nie endpoint
Potwierdzone wcześniej, powtórzone tu dla kompletności.

---

## 3. Co faktycznie istnieje i ma wartość (UDOWODNIONE)

### 3.1 `POST checkout/purchases/check_availability` [pre-check]
Body: `{buyerId, itemIds[]}` — zbiorcze sprawdzenie dostępności itemów.
**Zastosowanie:** pre-filter w pollerze, zanim zapłacimy koszt `conversations`.

### 3.2 `POST .../checkout/payment/continue` [retry bez re-buildu]
Wznowienie płatności bez ponownego buildu.

### 3.3 `POST .../checkout/payment/failure` [maszyna stanów]
Zgłoszenie nieudanej płatności.

### 3.4 `GET .../checkout/payment_methods` [pomijalny]
Lista metod płatności — zbędna, jeśli znamy `pay_in_method_id`.

### 3.5 `PUT transactions/{id}/reservation` [rezerwacja transakcji]
Body: `{reserved: boolean}` — osobny mechanizm rezerwacji (nie zakupu).

---

## 4. Feature flags i eksperymenty (DOMNIEMANE — brak wpływu na szybkość)

Zidentyfikowane systemy:
- `feature_flags_refresh_rate_limit`, `FEATURE_FLAGS_DATA_STORE_STORAGE` — infrastruktura flag
- `checkout_progressive_disclosure_ab_test_variant` — eksperyment UI (progressive disclosure), nie skrót
- `buyerShippingPoliciesExperiments`, `dynamicSellerPoliciesExperiments` — polityki, nie szybkość
- `flags.svc.vinted.com/android/` — endpoint feature flags (serwer decyduje)

**Wniosek:** feature flags sterują UI i wariantami eksperymentów, ale **żaden nie skraca flow checkoutu**. Wszystkie prowadzą do tej samej sekwencji API.

---

## 5. Ostateczna mapa ścieżek zakupu

```
WSZYSTKIE prowadzą do tego samego:
  conversations (createNewConversation / createConversation)
  → build (initiateCheckout, wymaga X-Incognia-Request-Token)
  → PUT (updateCheckout, {components})
  → payment (initiatePayment, wymaga X-Incognia-Request-Token)
```

Brak alternatyw:
- ❌ brak jednokrokowego "buy now" API
- ❌ brak "instant checkout"
- ❌ brak skip-build dla nowych itemów (purchase_id = null przed buildem)
- ❌ brak mobilnego skrótu

---

## 6. Rekomendacje (jedyne realne wektory optymalizacji)

| # | Wektor | Typ zysku |
|---|---|---|
| 1 | `check_availability` jako batch pre-filter w pollerze | unika kosztu `conversations` na niedostępnych itemach |
| 2 | Pre-warm `X-Incognia-Request-Token` (cache TTL) | eliminacja subprocesu Node + gotowość na egzekwowanie |
| 3 | `payment/continue` dla retry | unika re-buildu |
| 4 | Zrównoleglenie niezależnych GET (payment_methods ∥ pickup_points ∥ availability) | nakładanie latencji |
| 5 | Karta bez 3DS / BLIK | największy zysk, zależny od konta |

**Poza tym: flow jest wyczerpany.** Nie ma ukrytej furtki.

---

## Źródła (zdekmpilowane jadx)

- `com/vinted/feature/item/pluginization/plugins/buynow/ItemBuyNowPluginViewModel.java`
- `com/vinted/feature/conversation/domain/interactors/ConversationBuyInteractor.java`
- `com/vinted/feature/checkout/api/CheckoutApi.java`
- `com/vinted/feature/checkout/api/GatewayCheckoutApi.java`
- `com/vinted/feature/payments/api/PaymentsApi.java`
- `com/vinted/feature/paymentoptions/api/PaymentOptionsApi.java`
- `com/vinted/feature/paymentsauthorization/api/PaymentAuthorizationApi.java`
- `com/vinted/feature/conversation/api/ConversationApi.java`
- `com/vinted/feature/conversation/api/NewConversationApi.java`
- `com/vinted/feature/checkout/api/entity/NewBackendCheckoutDto.java`
- `strings_clean.txt` (dump stringów APK)

---

*Koniec analizy ukrytych ścieżek.*