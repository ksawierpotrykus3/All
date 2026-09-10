# Równoległość: card_registrations vs checkout/build — analiza zależności

Data: 2026-09-01
Źródło: dekompilacja APK (jadx_out).

---

## 1. ZALEŻNOŚCI DANYCH (co wymaga czego)

### [UDOWODNIONE] Graf zależności tokenizacji karty

```
POST payments/public/api/card_registrations      ← niezależne od checkoutu
        │  zwraca: card_registration_id, access_key, provider
        ▼
Szyfrowanie karty Adyen CSE (access_key)         ← czysto lokalne (CPU)
        │
        ▼
PUT payments/public/api/card_registrations/{id}  ← niezależne od checkoutu
```

- **Wniosek 1:** Żaden z 2 requestów tokenizacji nie wymaga `purchase_id`. Mogą działać **w pełni równolegle** z `checkout/build`.
- **Wniosek 2:** `access_key` z `POST card_registrations` jest potrzebny ZANIM zaczniemy szyfrować — ale szyfrowanie jest lokalne i trwa <10 ms.

### [UDOWODNIONE] Druga ścieżka — CVV stored card (PayRails)
Z [PayRailsCvvEncryptionServiceImpl$encryptCvv$2.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/creditcardadd/psp/encryption/PayRailsCvvEncryptionServiceImpl$encryptCvv$2.java#L53-L55):
```java
PayrailsCSE.INSTANCE
    .init((InitResponse) gson.fromJson(initializationData, InitResponse.class))
    .encryptCardData(new Card(null, null, null, null, null, cvv, 31, null));
```

- `initializationData` pochodzi z odpowiedzi checkoutu (funkcja `handlePaymentDataResponse` → akcja `PAYRAILS_CVV_RESUBMISSION`).
- **Wniosek:** CVV stored card **zależy od checkoutu** (init data z backendu). Nie da się pre-warmować w pełni — ale sam `encryptCardData` jest lokalny.

---

## 2. REKOMENDACJA RÓWNOLEGŁOŚCI

### [UDOWODNIONE] Optymalny harmonogram (2 niezależne wątki)

```
WĄTEK A (checkout)                    WĄTEK B (karta)
──────────────────────                ─────────────────────────
1. POST checkout/build                1. POST card_registrations (access_key)
   (Incognia token)                      (Incognia token)
        │                                  │
2. PUT checkout/{id}                  2. Adyen CSE szyfrowanie (lokalne)
   (wybór metody)                          │
        │                                  │
3. POST checkout/payment              3. PUT card_registrations/{id}
   (checksum + PaymentOptions)             │
        │                                  ▼
        └──────────── sync ──────────>  token gotowy
```

### Kluczowy warunek synchronizacji
- `PaymentOptions` przy nowej karcie zawiera `encryptedCardDetails` (Adyen CSE) → wymaga ukończenia wątku B krok 2.
- Jeśli karta już zapisana → `encryptedCvv` (PayRails) → zależy od init data z checkoutu.

### Szacowany zysk
[DOMNIEMANE — nie zmierzone] Równoległość oszczędza ~2 RTT (POST+PUT card_registrations wychodzą poza ścieżkę krytyczną).

---

## 3. CO ZNALEZIONO NOWEGO (dodatkowe odkrycie)

### [UDOWODNIONE] Dwa systemy CSE w APK
| System | Do czego | Init data |
|---|---|---|
| **Adyen CSE** (JWE RSA-OAEP-256) | Nowa karta (pełne dane) | `access_key` z card_registrations |
| **PayRails CSE** (init + encryptCardData) | Stored card (sam CVV) | `initializationData` z checkoutu |

To wyjaśnia `Action.PAYRAILS_CVV_RESUBMISSION` w [Action.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/paymentsauthorization/api/response/Action.java#L11):
- gdy płatność wymaga ponownego CVV, Vinted używa PayRails do zaszyfrowania tylko CVV (szybciej niż pełne Adyen CSE).

---

## 4. KONFRONTACJA Z DOKUMENTACJĄ

- Aktualizuje [CHECKOUT_SEKWENCJA_APK.md](file:///f:/PROJEKTY/vinted/vinted/raporty/02_reverse_engineering/CHECKOUT_SEKWENCJA_APK.md) sekcja 4: równoległość card_registrations potwierdzona kodem.
- Uzupełnia [CHECKOUT_PREWARMING.md](file:///f:/PROJEKTY/vinted/vinted/raporty/02_reverse_engineering/CHECKOUT_PREWARMING.md) o PayRails CSE (nowa ścieżka CVV).
- **Sprzeczność z hipotezą:** wcześniej [DOMNIEMANE], że stored card używa Adyen CSE tylko CVV — [UDOWODNIONE] to PayRails CSE, nie Adyen. Do poprawki w ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md.

### [NAKAZ] Pytania badawcze
1. ~~Czy `POST card_registrations` wymaga Incognia token?~~ **[ROZSTRZYGNIĘTE]** NIE. [CardRegistrationsCentralApi.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/creditcardadd/impl/svcpaymentspublicapicentral/apis/CardRegistrationsCentralApi.java#L27-L41) — brak `@Header("X-Incognia-Request-Token")`. PUT ma tylko `@Header("Origin")`.
2. Czy PayRails `encryptCardData` da się odtworzyć lokalnie (obfuskowany SDK)?

---

## 5. AKTUALIZACJA — card_registrations NIE wymaga Incognia token [UDOWODNIONE]

Pełna lista endpointów [CardRegistrationsCentralApi.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/creditcardadd/impl/svcpaymentspublicapicentral/apis/CardRegistrationsCentralApi.java#L27-L41):

| Metoda | Endpoint | Nagłówki |
|---|---|---|
| POST | `payments/public/api/card_registrations` | — (brak Incognia) |
| PUT | `payments/public/api/card_registrations/{id}` | `Origin` |
| POST | `.../authorisation` | — |
| POST | `.../failure` | — |
| GET | `.../brands?bin=` | — |

**Wniosek:** card_registrations jest **lżejszą ścieżką niż checkout/build** — nie wymaga tokenu Incognia. To zwiększa szansę, że przejdzie DataDome w curl_cffi (mniejszy próg) i pozwala na pre-tokenizację karty bez głównego endpointu transakcyjnego.
