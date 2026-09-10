# Analiza aplikacji mobilnej Vinted 26.33.1 (XAPK) — endpointy i warstwy ochrony

**Data:** 2026-08-31
**Źródło:** `Vinted_+Shop+&+sell+pre-loved_26.33.1_APKPure.xapk` (fr.vinted.apk, version_code 263301, minSdk 29 / targetSdk 36)
**Metoda:** ekstrakcja XAPK → APK → `classes*.dex` (11 plików, ~102 MB) → skan stringów (`strings -n 8`, mingw)
**Konwencja:** `[UDOWODNIONE]` / `[DOMNIEMANE]`

---

## 1. Co to jest za plik

XAPK = bundle APKPure: zip zawierający `fr.vinted.apk` (bazowy, 124 MB) + 11 split-APK `config.*.apk` (natywne libki/zasoby per architektura i DPI). `manifest.json` potwierdza: pakiet `fr.vinted`, wersja **26.33.1**, minSdk 29 (Android 10), targetSdk 36.

**Wniosek [UDOWODNIONE]:** pełna, aktualna aplikacja produkcyjna Vinted na Androida.

---

## 2. Kluczowe odkrycie: ten sam backend + warstwy antyfraud natywnie w apce

Aplikacja mobilna **nie używa osobnego API** — woła ten sam backend (`api.vinted.pl` / `www.vinted.pl`), ale wnosi **dodatkowe warstwy ochrony**, których nie widać w webowym HAR:

| Warstwa | Obecność w APK | Dowód |
|---|---|---|
| **DataDome SDK (Android)** | ✅ | `https://api-sdk.datadome.co/sdk/`, `Lco/datadome/sdk/DataDomeSDK`, `DataDomeCookieJar` |
| **Incognia SDK** | ✅ | `Lcom/incognia/EventProperties;`, `"Incognia generated request token"`, `access$sendIncogniaEventIfNeeded` |
| **Adyen 3DS2** | ✅ | `Lcom/adyen/threeds2/*`, `v1/submitThreeDS2Fingerprint`, `AdyenThreeDSAction` |
| **Checkout.com (FPJS/risk)** | ✅ | `fpjs.checkout.com`, `risk.checkout.com`, `api.checkout.com/tokens`, `cloudevents.integration.checkout.com` |
| **Klarna** | ✅ | `KlarnaPaymentView`, `klarna.net` |

---

## 3. WNIOSEK Z DEKOMPILACJI (jadx 1.5.6) — mobile używa tego samego backendu checkout

[UDOWODNIONE — dekompilacja `CheckoutApi.java`]: mobilna apka **nie ma osobnego, szybszego skrótu zakupowego**. Używa dokładnie tych samych endpointów co web:

```java
// com/vinted/feature/checkout/api/CheckoutApi.java
@POST("purchases/checkout/build")
Single<SingleCheckoutResponse> initiateCheckout(@Body CheckoutInitiateRequest body,
                                                @Header("X-Incognia-Request-Token") String incogniaHeader);

@PUT("purchases/{id}/checkout")
Single<SingleCheckoutResponse> updateCheckout(@Path("id") String id, @Body CheckoutUpdateRequest body);

@GET("purchases/{id}/checkout")
Single<SingleCheckoutResponse> getSingleCheckoutData(@Path("id") String id);
```

Kluczowe ustalenia:

1. **`X-Incognia-Request-Token` jest wymagany** w `initiateCheckout` → Incognia działa również na mobile (falsyfikuje tezę „mobile = lżejsze zabezpieczenia").
2. **Body buildu identyczne z webem**: `CheckoutInitiateRequest` = `List<PurchaseItem>`; `PurchaseItem` = `{id: String, type: PurchaseType}` — dokładnie to samo co `{"purchase_items":[{"id":...,"type":"transaction"}]}` w naszym [checkout.py](file:///f:/PROJEKTY/vinted/bot/src/vintedbot/checkout.py).
3. **`PUT` to `CheckoutUpdateRequest`** z pojedynczym polem `components` — identycznie jak web.
4. **Jeden nowy endpoint:** `POST checkout/purchases/check_availability` (GatewayCheckoutApi) — sprawdza dostępność itemu przed zakupem. Potencjalnie przydatny do pre-walidacji.

## 4. Sprostowanie: `/v2/purchase` to NIE endpoint zakupowy

Wcześniejszy skan stringów wykazał `/v2/purchase` — po dekompilacji okazuje się to **fragment nazwy klasy/URL wewnętrznego**, nie endpoint Retrofit checkoutu. Mobile nie oferuje jednokrokowego skrótu; flow zakupowy jest identyczny z webowym (`conversations → build → PUT → payment`).

---

## 5. Endpointy mobilne (nieobecne lub rzadkie w web HAR)

### 3.1 Zakup / rezerwacja / escrow

| Endpoint | Uwaga |
|---|---|
| `/v2/purchase` | mobilny endpoint zakupu (odpowiednik web `/checkout/build` + `/payment`?) |
| `api/v2/reserve_item_details/{id}` | rezerwacja itemu |
| `/purchases/{purchaseId}/checkout/payment/failure` | **nowy** — obsługa nieudanej płatności |
| `/escrow_orders/{id}` oraz `/escrow_orders/{escrow_order_id}` | escrow (depozyt) |
| `api/v2/transactions/{transaction_id}/services` | usługi na transakcji |
| `items/{item_id}/shipping_details` | koszt wysyłki per item |

### 3.2 Płatności / portfel

| Endpoint | Uwaga |
|---|---|
| `users/{user_id}/payments_account` | konto płatnicze użytkownika |
| `ledger/public/api/wallet/balance` | saldo portfela |
| `api/v2/users/{user_id}/balance` | saldo |
| `api/v2/users/{userId}/payouts` | wypłaty |

### 3.3 3DS / autoryzacja płatności

| Endpoint | Uwaga |
|---|---|
| `v1/submitThreeDS2Fingerprint` | fingerprint 3DS2 (Adyen) |
| `v1/face-tec/mobile-license`, `v1/face-tec/sessions` | weryfikacja twarzy (KYC) |
| `/v1/kyc-identifications`, `/v1/identity-verifications/{id}` | KYC/AML |

### 3.4 Infrastruktura / config

| Host | Rola |
|---|---|
| `flags.svc.vinted.com/android/` | feature flags Androida |
| `logs-ingress.svc.vinted.com` / `metrics-ingress.svc.vinted.com` | logi + metryki (OpenTelemetry) |
| `localisation-assets.vinted.com/bundles/android/{languageTag}.json` | lokalizacje |
| `https://api-sdk.datadome.co/sdk/` | DataDome SDK endpoint |

---

## 4. Co to zmienia dla naszego researchu

### 4.1 Wartość pozytywna [DOMNIEMANE]

- **`/v2/purchase`** — potencjalnie uproszczona, jednokrokowy endpoint zakupowy. Warto go sprościć do werdyktu: czy robi to, co web robi w 4–5 krokach (conversations → build → PUT → payment)?
- **`reserve_item_details/{id}`** — może być lżejszą ścieżką rezerwacji niż web build.
- **`checkout/payment/failure`** — pokazuje pełną maszynę stanów płatności (sukces/failure), co pomaga zrozumieć flow.

### 4.2 Wartość negatywna / ryzyko [DOMNIEMANE]

- **DataDome jest natywnie w apce** (`api-sdk.datadome.co/sdk/`). To falsyfikuje luźną tezę z AGENTS.md „mobile API = lżejszy DataDome" — mobilna apka ma **własny SDK DataDome**, więc nie jest „mniej chroniona", tylko chroniona inaczej (device attestation zamiast TLS fingerprint).
- **Incognia + Adyen 3DS2 + FPJS** — mobile ma pełną wieżę antyfraud, podobnie jak web.

---

## 5. Ograniczenia obecnej analizy i czego potrzebuję

Skan stringów daje **fragmenty** endpointów, ale nie pełne ścieżki Retrofit — adnotacje `@GET/@POST` w tej apce są **obfuscowane** (ścieżki nie siedzą wprost w string pool; jedyne wycieki to logi typu `"Call to @GET(...) failed"`).

Aby wydobyć **kompletny mapping endpointów (ścieżka + metoda + parametry + nagłówki)**, potrzebuję narzędzia dekompilującego DEX:

1. **jadx** (`jadx -d out fr.vinted.apk`) — najszybsza droga do `resources/` + dekompilacja do Java/Smali z widocznymi ścieżkami Retrofit.
2. **apktool** (`apktool d`) — do odczytania `AndroidManifest.xml`, `res/`, i zasobów (np. klucze API).

Z `jadx` celuję konkretnie w klasy:
- `com/vinted/feature/checkout/**` (CheckoutApi, GatewayCheckoutApi)
- `com/vinted/feature/payments/**` (PaymentsApi, pay_in_methods)
- `com/vinted/feature/reservations/**` (ReserveApi)
- `com/vinted/shared/session/**` (VintedAuthApi)
- `com/datadome/sdk/**` i `com/incognia/**` (konfiguracja SDK)

---

## 6. Rekomendacja dalszych kroków

1. **Zainstalować jadx** i zdekmpilować `fr.vinted.apk` → pełny mapping endpointów z adnotacji Retrofit.
2. **Zweryfikować `/v2/purchase`** — czy to skrót zakupowy (największy potencjalny zysk dla celu 2–3 s).
3. **Porównać `/v2/purchase` vs web `conversations→build→PUT→payment`** — liczba kroków i czas.
4. **[NAKAZ konfrontacja]** Zaktualizować syntezę o fakt: mobilny DataDome SDK istnieje → teza „lżejszy DataDome na mobile" wymaga weryfikacji empirycznej, nie może pozostać założeniem.

---

## 7. Pliki wyjściowe

- `vinted/dane/apk/fr.vinted.apk` — główny APK (124 MB)
- `vinted/dane/apk/extracted/` — pełna zawartość APK (3852 pliki, w tym 11 `classes*.dex`)
- `vinted/dane/apk/strings_clean.txt` — pełny dump stringów (24 MB)
- `vinted/dane/apk/apk_strings_endpoints.txt` — przefiltrowane stringi

---

## Źródła

- [manifest.json](file:///f:/PROJEKTY/vinted/vinted/dane/apk/manifest.json)
- `vinted/dane/apk/strings_clean.txt` (dump stringów z classes*.dex)
- AGENTS.md — nota o „Mobile API endpoints"

---

*Koniec analizy XAPK.*