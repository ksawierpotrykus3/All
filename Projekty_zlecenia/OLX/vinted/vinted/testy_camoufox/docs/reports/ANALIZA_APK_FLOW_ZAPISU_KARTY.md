# MAPA FLOW ZAPISU KARTY (bez build, bez transaction)

**Data:** 2026-08-31
**Źródło:** dekompilacja APK (`jadx_out` — `svcpaymentspublicapicentral`)
**Konwencja:** `[UDOWODNIONE]` (z kodu źródłowego APK)

---

## Cel

Ustalić, co dokładnie wysłać do endpointów Vinted, aby **zapisać kartę na koncie kupującego** — bez `checkout/build` i bez tworzenia transakcji, ale w sposób, który serwer powiąże z zalogowanym kontem (sesja/cookies).

---

## Endpointy (Retrofit, z dekompilacji) [UDOWODNIONE]

Bazowy host: `payments/public/api` (scena central payments — wymaga weryfikacji hosta, najpewniej `api.vinted.pl`).

| Metoda | Ścieżka | Rola |
|---|---|---|
| POST | `payments/public/api/card_registrations` | utwórz rejestrację karty (zwraca `card_registration_id`, `provider`, `access_key`, `url`, `data`) |
| PUT | `payments/public/api/card_registrations/{card_registration_id}` | wyślij ztokenizowaną kartę + 3DS |
| POST | `payments/public/api/card_registrations/authorisation` | finalizuj (3DS result) |
| POST | `payments/public/api/card_registrations/failure` | oznacz niepowodzenie |
| GET | `payments/public/api/card_registrations/brands` | rozpoznaj brand po BIN |
| GET | `payments/public/api/cards` | lista zapisanych kart |
| DELETE | `payments/public/api/cards/{id}` | usuń kartę |

---

## Pełny flow zapisu karty [UDOWODNIONE z kodu]

```
1. POST card_registrations (puste body) → {card_registration_id, provider, access_key, url, data}
2. Tokenizacja karty u PSP (zewnętrzne SDK):
   - provider ∈ {adyen, mangopay, adyen_bank, payrails, checkout}
   - tokenizacja zwraca: token + encryptedCardDetails(number, expMonth, expYear, securityCode)
3. PUT card_registrations/{id} z UpdateCardRegistrationRequest
4. Jeśli 3DS → POST authorisation z paymentData
5. Karta zapisana → PublicCard(id, last4, brand, default, singleUse)
```

---

## Struktura `UpdateCardRegistrationRequest` [UDOWODNIONE]

```json
{
  "card_registration": {
    "return_url": "scheme://card_add_result",
    "single_use": false,
    "token": "<token z PSP>",
    "encrypted_card_details": {
      "number": "<encrypted>",
      "expiration_month": "<encrypted>",
      "expiration_year": "<encrypted>",
      "security_code": "<encrypted>"
    },
    "secure_3ds_details": {
      "platform": "android",
      "browser_info": {
        "language": "pl",
        "color_depth": 24,
        "java_enabled": false,
        "screen_height": 1080,
        "screen_width": 1920,
        "timezone_offset": -120
      }
    }
  },
  "tracking_context": null
}
```

## Kluczowy wniosek [UDOWODNIONE]

**Zapis karty jest POWIĄZANY z kontem wyłącznie przez sesję/cookies** (nie przez `buyer_id` w body). Nie ma `buyer_id`/`user_id` w requestach card_registrations — autoryzacja idzie z ciasteczek sesji (jak `users/current`).

**Ale** kroki 2 i 3 są **blokowane przez tokenizację PSP**:
- Karta nie idzie do Vinted wprost. Najpierw zewnętrzne SDK (Adyen/MangoPay/PayRails/Checkout.com) tokenizuje numer karty → zwraca `token` + `encrypted_card_details`.
- Dopiero ten token Vinted zapisuje.

To znaczy: **nie da się zapisać karty samym curl/endpointami Vinted** — trzeba przejść przez JavaScript SDK PSP (web) lub natywne SDK (app), które tokenizuje kartę kluczem publicznym PSP.

---

## Źródła

- `CardRegistrationsCentralApi.java` — endpointy card_registrations
- `CardsCentralApi.java` — endpointy cards (list/get/delete)
- `CardRegistrationsRepositoryImpl.java` — flow + budowa `UpdateCardRegistrationRequest`
- `UpdateCardRegistrationRequest.java` + `...EncryptedCardDetails` + `...Secure3dsDetails` — struktura body

---

*Koniec analizy.*