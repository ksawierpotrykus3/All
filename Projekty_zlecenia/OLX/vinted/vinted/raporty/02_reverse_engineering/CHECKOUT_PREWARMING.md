# Pre-warming checkoutu — analiza możliwości przyspieszenia

Data: 2026-09-01
Źródło: dekompilacja APK (jadx_out), 100% z kodu.
Kontekst: sekcja 2 cyklu analizy przyspieszania zakupu (po CHECKOUT_SEKWENCJA_APK.md).

---

## 1. PRE-WARMING KARTY — czy token jest wielokrotnego użytku?

### [UDOWODNIONE] Token karty (Adyen CSE) jest SINGLE-USE

| Dowód | Źródło |
|---|---|
| `CreditCardDto.singleUse` (pole boolean) | [CreditCardDto.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/creditcardadd/CreditCardDto.java#L22) |
| `PaymentOptions.singleUseCard` wysyłane do backendu | [PaymentOptions.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/paymentsauthorization/api/request/PaymentOptions.java#L23) |
| `PaymentInitiationData.singleUseCard` — flaga propagowana z checkoutu | [PaymentInitiationData.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/payments/PaymentInitiationData.java#L18) |

**Wniosek:** sam zaszyfrowany blok karty (JWE Adyen) nie może być użyty wielokrotnie — flaga `singleUseCard` jest jawnie wysyłana w `PaymentOptions`. Backend wie, że to token jednorazowy.

### [DOMNIEMANE — wymaga testu na żywo] Access key (POST card_registrations) NIE musi być single-use

- `POST payments/public/api/card_registrations` zwraca `access_key` (klucz publiczny Adyen) — to nie token płatności, tylko klucz do szyfrowania.
- Pytanie otwarte: czy **jeden** access_key może posłużyć do zaszyfrowania karty **wielokrotnie** (różne szyfrogramy, bo AES key + IV losowe), czy każda próba wymaga nowego POST-a.

### [UDOWODNIONE] Istnieją 2 ścieżki płatności kartą

W `getRequest` ([PaymentManagerImpl.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/payments/PaymentManagerImpl.java#L1277-L1285)):

| Ścieżka | Kiedy | Co wysyła w `PaymentOptions` |
|---|---|---|
| **Stored card** | Karta zapisana (bez full re-tokenizacji) | `encryptedCvv` (tylko CVV zaszyfrowany Adyen CSE) |
| **New card** | Nowa karta | pełne `encryptedCardDetails` (number+expiry+cvc) |
| **Google Pay** | GPay wybrany | `googlePayMetadata` + `paymentToken` (token GPay) |

**Wniosek:** stored card = tylko CVV do zaszyfrowania (mniej pól, szybsze). Nowa karta = pełne CSE.

---

## 2. PRE-WARMING CHECKOUTU — co można zrobić wcześniej

### [UDOWODNIONE] `check_availability` (gateway) — najszybszy pre-check
- Endpoint: `POST checkout/purchases/check_availability` ([GatewayCheckoutApi.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/checkout/api/GatewayCheckoutApi.java#L14-L16))
- Zwraca: `purchaseAvailable`, `reservation.available`, `markAsSold.available`
- **Można wysyłać regularnie** (polling) dla obserwowanych itemów — zanim klikniemy kup.

### [UDOWODNIONE] Firebase App Instance ID wymagany przy płatności
`PaymentRequest` zawiera `firebaseAppInstanceId` ([PaymentRequest.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/paymentsauthorization/api/request/PaymentRequest.java#L13)).
`getRequest` czeka na niego przez `awaitOrNull(this.firebaseAppInstanceIdTask, ...)` ([PaymentManagerImpl.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/payments/PaymentManagerImpl.java#L1256)).

**Wniosek:** w web botcie nie mamy Firebase App Instance ID. [HIPOTEZA] Backend może akceptować request bez niego (null) — do przetestowania. Jeśli wymaga, trzeba go pozyskać (odczyt z profilu / fikcyjny).

### [UDOWODNIONE] Checksum — generowany przez backend, wymagany do płatności
`PaymentInitiationData.checksum` przychodzi z backendu (setupInitiatePaymentData), `PaymentRequest.checksum` wymagany do `startPayment`.

**Wniosek:** nie da się pre-warmować samej płatności bez zbudowania checkoutu (checksum per-checkout).

---

## 3. OSZACOWANIE OSZCZĘDNOŚCI (ścieżka krytyczna)

| Optymalizacja | RTT zaoszczędzone | Status wiedzy |
|---|---|---|
| Pre-polling `check_availability` | 1 (usuwa pierwszy GET) | [UDOWODNIONE] endpoint istnieje |
| Pre-fetch access_key (POST card_registrations) przed build | ~2 (POST+PUT poza ścieżką) | [DOMNIEMANE] zależy czy access_key reużywalny |
| Stored card zamiast nowej karty | ~2 RTT (mniej pól CSE, brak full tokenizacji) | [UDOWODNIONE] encryptedCvv ścieżka istnieje |
| Pominięcie GET payment (polling) | 1+ | [DOMNIEMANE] wymaga testu |

---

## 4. DOKUMENTACJA — KONFRONTACJA

Brak sprzeczności z istniejącymi dokumentami. Uzupełnienie:
- [CHECKOUT_SEKWENCJA_APK.md](file:///f:/PROJEKTY/vinted/vinted/raporty/02_reverse_engineering/CHECKOUT_SEKWENCJA_APK.md) — sekcja 4 (tabela optymalizacji) aktualizowana tą analizą.
- [ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md) — nowa informacja: flaga `singleUseCard`.

### [NAKAZ] Nowe pytania badawcze
1. Czy jeden access_key Adyen pozwala szyfrować kartę wielokrotnie?
2. Czy backend akceptuje `payment` bez `firebaseAppInstanceId`?
3. Czy `check_availability` przechodzi DataDome łatwiej niż `checkout/build`?
