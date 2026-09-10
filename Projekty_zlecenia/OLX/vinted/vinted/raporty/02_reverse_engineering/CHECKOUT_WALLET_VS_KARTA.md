# Ścieżka płatności walletem vs kartą w APK

Data: 2026-09-01
Źródło: dekompilacja APK (jadx_out), 100% z kodu.

---

## 1. METODY PŁATNOŚCI (enumeracja)

### [UDOWODNIONE] PaymentMethod — pełna lista
Z [PaymentMethod.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/paymentsauthorization/api/entity/PaymentMethod.java#L10-L22):
`UNKNOWN, CREDIT_CARD, MANGOPAY_PAYPAL, IDEAL, WALLET, GOOGLE_PAY, BLIK_DIRECT, P24, TRUSTLY, TINK, KLARNA, BANCONTACT`

**WALLET istnieje** jako odrębna metoda.

### [UDOWODNIONE] Action — lista akcji po initiatePayment
Z [Action.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/paymentsauthorization/api/response/Action.java#L10-L16):
`PAYRAILS_CVV_RESUBMISSION, REDIRECT, NATIVE_ADYEN_PAYMENT_BLIK_AUTHORIZATION, GOOGLE_PAY, SCA_REQUIRED, KLARNA`

**Kluczowy wniosek: NIE MA osobnej akcji dla WALLET.** Wallet nie generuje własnej akcji — płatność kończy się od razu (brak akcji = sukces) albo zwraca REDIRECT/SCA_REQUIRED tak jak inne metody.

---

## 2. PRZEPŁYW DECYZYJNY PO initiatePayment

Z [handlePaymentDataResponse](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/payments/PaymentManagerImpl.java#L1490-L1544):

```
POST purchases/{id}/checkout/payment
        │
        ▼
PaymentData(payment, action)
        │
        ├── payment.status == FAILURE → throw PaymentError (kod błędu z payment.error)
        │
        └── payment.status != FAILURE → handleAction(action)
                │
                ├── PAYRAILS_CVV_RESUBMISSION → ponowny CVV (PayRails)
                ├── REDIRECT → PaymentsRedirectAuthHandler (3DS1/web redirect)
                ├── NATIVE_ADYEN_PAYMENT_BLIK_AUTHORIZATION → natywny BLIK (Adyen)
                ├── GOOGLE_PAY → Google Pay wrapper
                ├── SCA_REQUIRED → Adyen 3DS2 natywny / mangopay Browser 3DS2
                └── KLARNA → Klarna flow
```

### [UDOWODNIONE] Wallet = brak akcji → natychmiastowy SUCCESS
W `handleAction` nie ma case'a dla WALLET. Jeśli `action == null` (puste), płatność jest uznawana za udaną — `PaymentResult.Success`.

**Wniosek:** gdy saldo wallet pokrywa całość, ścieżka to **tylko 1 request** (`POST checkout/payment`) po `checkout/build` — bez Adyen CSE, bez 3DS2, bez redirectów.

---

## 3. PORÓWNANIE ŚCIEŻEK (wallet vs karta)

| Element | Wallet (pełne saldo) | Nowa karta | Stored card |
|---|---|---|---|
| Tokenizacja karty (card_registrations) | ❌ nie | ✅ 2 requesty | ❌ nie |
| Adyen CSE szyfrowanie | ❌ nie | ✅ pełne (number+cvc) | ✅ tylko CVV |
| 3DS2/SCA | ❌ nie | ✅ możliwe | ✅ możliwe |
| Action po payment | brak (od razu sukces) | SCA_REQUIRED/REDIRECT | SCA_REQUIRED/REDIRECT |
| Requesty w płatności | **1** | 2-4 | 1-3 |
| Ryzyko 3DS | **zero** | wysokie | wysokie |

### Szacunkowy zysk
[DOMNIEMANE — nie zmierzone] Wallet oszczędza ~2-4 requesty i eliminuje całe ryzyko 3DS/redirect. To **najszybsza możliwa ścieżka zakupu** w Vinted.

---

## 4. UWAGI OPERACYJNE

- Wallet jest akceptowany tylko gdy saldo ≥ cena (weryfikacja po stronie backendu — brak lokalnej kontroli w APK).
- Dla typowego użycia bota (oszczędności + szybkie kupno) **trzeba trzymać saldo na koncie**, żeby mieć gwarancję ścieżki wallet.
- Jeśli saldo nie wystarcza, Vinted i tak użyje karty — różnica jest czysto proceduralna po stronie backendu.

---

## 5. KONFRONTACJA Z DOKUMENTACJĄ

- Brak konfliktu z CHECKOUT_SEKWENCJA_APK.md (tam endpointy, tu decyzja po payment).
- Uzupełnia ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md o kontekst: CSE potrzebne tylko przy karcie, wallet ich nie używa.

### [NAKAZ] Pytania badawcze
1. Jak dokładnie backend komunikuje "wallet może pokryć"? (prawdopodobnie w `PaymentOptions`/`PayInMethod` w odpowiedzi checkout/build)
2. Czy w checkout/build można od razu wskazać `WALLET` jako preferowaną metodę?
