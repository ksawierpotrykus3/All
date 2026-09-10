# BRAMKA PŁATNOŚCI BEZ BUILD — `payment/continue`

**Data:** 2026-08-31
**Źródło:** dekompilacja APK (`PaymentsApi`, `PaymentActionDeserializer`, `PaymentParameters`)
**Konwencja:** `[UDOWODNIONE]` (z kodu źródłowego APK)

---

## Odpowiedź wprost

**[UDOWODNIONE] TAK — można wejść do bramki płatności bez nowego buildu.**

`POST payments/{purchase_id}/checkout/payment/continue` przyjmuje tylko `purchase_id` + `PaymentRequest` i **NIE wymaga nagłówka `X-Incognia-Request-Token`** (w przeciwieństwie do `initiatePayment`).

Warunek: musi istnieć **ważny `purchase_id`** (checkout utworzony wcześniej — przez build, albo skip-build z `conversations`).

---

## Endpoint i body [UDOWODNIONE]

```java
@POST("purchases/{purchase_id}/checkout/payment/continue")
Single<PaymentResponse> getContinuePayment(@Path("purchase_id") String id, @Body PaymentRequest body);
```

`PaymentRequest`:
```json
{
  "firebase_app_instance_id": null,
  "checksum": "<checksum z checkoutu>",
  "payment_options": { ... }
}
```

Brak `@Header("X-Incognia-Request-Token")` → **bez Incognii**.

Dla porównania `initiatePayment` (wymaga Incognii):
```java
@POST("purchases/{id}/checkout/payment")
Single<PaymentResponse> initiatePayment(@Path("id") String id, @Body PaymentRequest body,
    @Header("X-Incognia-Request-Token") String incogniaHeader);
```

---

## Odpowiedź → wejście do bramki [UDOWODNIONE]

`PaymentResponse` = `{ payment: Payment, action: PaymentAction }`.

`PaymentAction` deserializowany po polu `type` (enum `Action`):

| type | Parametry | Co to daje |
|---|---|---|
| `REDIRECT` | `url`, `deepLinkUrl` | **URL bramki PSP** — bezpośrednie wejście do płatności |
| `SCA_REQUIRED` | `correlationId` | wymaga 3DS/SCA |
| `GOOGLE_PAY` | `merchantIdentifier`, `gateway`, `paymentToken` | Google Pay |
| `KLARNA` | `clientToken`, `data` | Klarna |
| `PAYRAILS_CVV_RESUBMISSION` | `initializationData`, `card` | ponowne CVV |
| `NATIVE_ADYEN_PAYMENT_BLIK_AUTHORIZATION` | `configuration`, `action` | BLIK Adyen |

---

## Wnioski strategiczne

1. **[UDOWODNIONE]** `payment/continue` = retry bez buildu. Mając `purchase_id`, wywołujesz jeden POST i dostajesz `action.url` (redirect do PSP) — oszczędzasz ~1.6s buildu.

2. **[UDOWODNIONE]** Bramka płatności nie jest związana z Incognią po stronie wejścia — tylko `initiatePayment` (pierwsze wejście) wymaga tokena. `continue` już nie.

3. **[DOMNIEMANE]** Error 114 ("Purchase card is not valid") to brak realnej, ztokenizowanej karty (patrz `ANALIZA_APK_FLOW_ZAPISU_KARTY.md`), nie walidacja `payment/continue`.

---

## Źródła

- `PaymentsApi.java` — `getContinuePayment` vs `initiatePayment`
- `PaymentActionDeserializer.java` — mapowanie `type` → `Action`
- `PaymentParameters.java` — `RedirectParameters` (url/deepLinkUrl) i in.
- `PaymentResponse.java`, `Payment.java`, `PaymentData.java`

---

*Koniec analizy.*