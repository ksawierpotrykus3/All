# Sekwencja checkout w APK — graf zależności i ścieżka krytyczna

Data: 2026-09-01
Źródło: dekompilacja APK (jadx_out), 100% z kodu.

---

## 1. ENDPOINTY CHECKOUT (komplet)

### Gateway (przed checkoutem) — [GatewayCheckoutApi.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/checkout/api/GatewayCheckoutApi.java#L14-L16)
| Metoda | Endpoint | Body | Cel |
|---|---|---|---|
| POST | `checkout/purchases/check_availability` | `CheckItemsAvailabilityRequest(id, list)` | Szybki pre-check kupowalności, zwraca `purchaseAvailable`, `reservation.available`, `markAsSold.available` |

### Checkout — [CheckoutApi.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/checkout/api/CheckoutApi.java#L19-L27)
| Metoda | Endpoint | Body | Cel |
|---|---|---|---|
| POST | `purchases/checkout/build` | `CheckoutInitiateRequest` + nagłówek `X-Incognia-Request-Token` | Buduje sesję checkout, zwraca purchase_id + dane |
| GET | `purchases/{id}/checkout` | — | Pobiera stan checkoutu |
| PUT | `purchases/{id}/checkout` | `CheckoutUpdateRequest` | Aktualizacja (wybór metody płatności, transportu) |

### Płatność — [PaymentsApi.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/payments/api/PaymentsApi.java#L19-L30)
| Metoda | Endpoint | Body | Cel |
|---|---|---|---|
| POST | `purchases/{id}/checkout/payment` | `PaymentRequest` + nagłówek `X-Incognia-Request-Token` | Inicjacja płatności (checksum + totalPrice) |
| GET | `purchases/{id}/checkout/payment` | — | Pobranie statusu płatności (polling po redirect/SCA) |
| POST | `purchases/{purchase_id}/checkout/payment/continue` | `PaymentRequest` | Kontynuacja (po 3DS/Google Pay) |
| POST | `purchases/{purchaseId}/checkout/payment/failure` | `FailPaymentRequest` | Anulowanie/raport błędu |

### Tokenizacja karty (Adyen) — osobna ścieżka
| Metoda | Endpoint | Cel |
|---|---|---|
| POST | `payments/public/api/card_registrations` | Access key (Adyen public key) |
| PUT | `payments/public/api/card_registrations/{id}` | Wysłanie zaszyfrowanej karty (Adyen CSE) |

---

## 2. SEKWENCJA WYKONANIA (graf zależności)

```
1. POST checkout/purchases/check_availability      ← pre-check (opcjonalny, UI)
        │
        ▼
2. POST purchases/checkout/build (Incognia token)  ← BUILD — główny punkt wejścia
        │
        ▼
3. (UI: wybór metody płatności/transportu)
        ▼
4. PUT purchases/{id}/checkout                     ← aktualizacja
        │
        ▼
5. setupInitiatePaymentData → checksum + totalPrice
        │
        ▼
6. POST purchases/{id}/checkout/payment (Incognia) ← PŁATNOŚĆ
        │
        ├── brak action → SUCCESS
        ├── 3DS2/SCA  → handleAction (Adyen ThreeDS2)
        ├── Google Pay → handleGooglePay
        ├── Klarna    → handleKlarna
        └── BLIK      → showBlikCode
        │
        ▼
7. GET purchases/{id}/checkout/payment              ← polling statusu
        │
        ▼
8. (opcjonalnie) POST .../payment/continue | .../payment/failure
```

### Równoległe możliwości
- **Krok 1 (check_availability) i krok 2 (checkout/build)** — oba niezależne od tokenizacji karty.
- **Tokenizacja karty (card_registrations)** — **niezależna** od kroków 2-6. Access key nie wymaga purchase_id.
- **Incognia token** wymagany w kroku 2 (build) i 6 (payment) — patrz sekcja 3.

---

## 3. KLUCZOWE OBSERWACJE (ścieżka krytyczna)

### [UDOWODNIONE]
1. **Incognia token wysyłany w 2 miejscach**: `checkout/build` i `checkout/payment` (annotation `@Header("X-Incognia-Request-Token")`).
2. **Payment nie zaczyna się od razu** — między build a payment jest interakcja UI (PUT checkout), więc build można zrobić wcześniej/pre-warm.
3. **`check_availability` to osobny gateway** (`checkout/purchases/check_availability`) — najszybsza droga do poznania czy item jest kupowalny, bez wywoływania build.
4. **3DS2 obsługiwane w PaymentManagerImpl** przez `handleAction` → `PaymentsAdyenThreeDsTwoHandler` (ścieżka Adyen) lub mangopay `BrowserThreeDsTwoDataGenerator`.
5. **checksum jest generowany po stronie backendu** — przychodzi w `PaymentInitiationData` (setupInitiatePaymentData), jest wymagany do `startPayment`.

### [DOMNIEMANE — wymaga weryfikacji]
- Czy `check_availability` przechodzi DataDome łatwiej niż `checkout/build`? (test do wykonania)
- Czy token Adyen (card_registration) jest wielokrotnego użytku? (pre-warm raz, użyj wiele razy)

---

## 4. CO TO ZNACZY DLA PRZYSPIESZENIA

Ścieżka krytyczna = `build → PUT → payment → (3DS)`. Można przyspieszyć przez:

| Optymalizacja | Oszczędność | Warunek |
|---|---|---|
| Pre-warm `check_availability` (zanim item się pojawi) | 1 RTT przed build | Endpoint dostępny bez item id |
| Pre-warm tokenizacji karty | 2 RTT (POST+PUT card_registrations) poza ścieżką | Token wielokrotnego użytku |
| Równoległość build + tokenizacja karty | ~2 RTT | Oba niezależne |
| Pominięcie GET checkout (polling) gdy payment zwraca action | 1+ RTT | PaymentResponse zwraca wszystko |

---

## 5. KONFRONTACJA Z ISTNIEJĄCĄ DOKUMENTACJĄ

Plik `wynik_playwright_rezerwacja.json` (test na żywo 2026-09-01):
- `item_page` → 200
- `identity_check` → **403 code=106 access_denied**
- `checkout_build` → **403 DataDome captcha**

**Zgodność:** [UDOWODNIONE] DataDome nadal blokuje `checkout/build` na świeżej sesji (zgodne z SYNTEZA_CAMOUFOX_FIREFOX.md). Nowa obserwacja: `identity_check` zwraca 403 code=106 — to ten sam błąd co rate-limit, ale na innym endpointcie. **Do rozstrzygnięcia**: czy 106 na identity_check to DataDome (ten sam WAF) czy osobny limit.
