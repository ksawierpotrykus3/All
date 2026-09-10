# Autoryzacja Vinted — APK vs Web (mapa nagłówków i porównanie)

Data: 2026-09-01
Status: APK w 100% z dekompilacji (`jadx_out`), Web z sond i reverse-engineeringu Next.js.
Zakres: mechanizm uwierzytelniania, nagłówki, tokeny, ochrona DataDome/Play Integrity.

---

## 1. STOS INTERCEPTORÓW W APK

Kolejność z [NetworkModule.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/networking/NetworkModule.java#L300-L314)
(`ProvideRawHttpClientMetroFactory`):

```
DomainFailoverInterceptor
DeviceFingerprintHeaderInterceptor
ApiHeadersInterceptor
LanguageInterceptor
VintedContextInterceptor
CountryInterceptor
HttpLoggingInterceptor
SecurityProtectionInterceptor
TwoFaErrorInterceptor
DataDomeInterceptor
EndpointTrackingInterceptor
ScreenPerformanceInterceptor
```

`ProvideAuthorizedOkHttpClientMetroFactory` dokłada do tego:
- `tokenInterceptor` (dodaje `Authorization`)
- `oauthTokenRefresher` jako `okhttp3.Authenticator`

---

## 2. MAPA NAGŁÓWKÓW APK

| Nagłówek | Źródło (interceptor) | Wartość |
|---|---|---|
| `User-Agent` | [ApiHeadersInterceptor](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/networking/interceptors/ApiHeadersInterceptor.java#L77) | statyczny UA (lub custom z debug) |
| `X-Anon-Id` | ApiHeadersInterceptor | anonimowy identyfikator sesji |
| `X-V-Udt` | ApiHeadersInterceptor | device token (persystentny, zapisywany z odpowiedzi `x-v-udt`) |
| `X-Platform` | [HeadersInterceptor](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/networking/interceptors/HeadersInterceptor.java#L59) | `android` |
| `X-Portal` | HeadersInterceptor | portal z `BuildContext` |
| `X-App-Version` | HeadersInterceptor | `BuildContext.VERSION_NAME` |
| `X-OS-Version` | HeadersInterceptor | `Build.VERSION.RELEASE` |
| `X-Device-Model` | HeadersInterceptor | `Build.MODEL` (kapitalizowany, z producentem) |
| `X-Screen-Width` / `X-Screen-Height` | HeadersInterceptor | `DisplayMetrics` |
| `X-Local-Time` | HeadersInterceptor | `System.currentTimeMillis()` |
| `X-Debug-Pin` | HeadersInterceptor | tylko gdy ustawiony tracker pin (debug) |
| `X-Device-UUID` | [DeviceFingerprintHeaderInterceptor](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/networking/interceptors/DeviceFingerprintHeaderInterceptor.java#L44) | persystentny UUID urządzenia |
| `X-Play-Integrity` | [SecurityProtectionInterceptor](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/security/SecurityProtectionInterceptor.java#L39-L61) | token Play Integrity — **tylko POST** na segment `users` / `facebook_users` / `google_user` (ścieżka 3-segmentowa) |
| `Authorization` | `tokenInterceptor` | `Bearer <access_token>` |
| nagłówki DataDome | DataDomeInterceptor (co.datadome.sdk) | fingerprint anti-bot, captcha |

### Nagłówki z dekodowanego JWT (tokenu)
Z [SharedApiHeaderHelperImpl.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/session/SharedApiHeaderHelperImpl.java#L76-L87):

`accessToken` jest JWT. APK dekoduje payload (Base64, część 2) i wyciąga:

| Pole JWT | Nagłówek |
|---|---|
| `sub` (userId) | `X-V-Uid` |
| `sid` (sessionId) | `X-V-Sid` |

(`X-V-Udt` — device token — także tu dodawany przez `addUserDeviceTokenHeader`).

---

## 3. MECHANIZM OAuth W APK

### Przechowywanie tokenu
`ApiToken` (kotlinx.serialization, encja [ApiTokenEntity.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/session/api/entity/ApiTokenEntity.java#L17-L21)) zawiera dokładnie 5 pól:

| Pole | Typ | Znaczenie |
|---|---|---|
| `expiresIn` | `long` | czas życia tokena (sekundy) |
| `tokenType` | `String` | typ tokena (np. `Bearer`) |
| `accessToken` | `String` | JWT dostępowy |
| `scope` | `String` | **`public`** (anonim) lub **`user`** (zalogowany) |
| `refreshToken` | `String` | token odświeżający |

Przechowywany w preferencjach przez [ApiTokenProviderImpl.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/session/preferences/ApiTokenProviderImpl.java#L26-L52).

### Refresh po 401
[OauthTokenRefresher.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/authentication/token/OauthTokenRefresher.java#L67-L122)
(implementacja `okhttp3.Authenticator`):

1. `authenticate()` odczytuje `Authorization` z nieudanego żądania.
2. Jeśli token już "resolved" → ponownie dokleja token (`applyToken`).
3. W przeciwnym razie woła `SessionTokenImpl.refreshCurrentToken(apiToken)`.
4. Po sukcesie zapisuje nowy `ApiToken` i ponownie dokleja token.
5. Przy `429` (TOO_MANY_REQUESTS) ustawia `skipRefreshTill` na 1 s i rzuca `IOException`.

### Refresh token — wykonanie
[SessionTokenImpl.refreshCurrentToken()](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/authentication/token/SessionTokenImpl.java#L164-L197):
- Jeśli `refreshToken` pusty → `RefreshTokenException`.
- Wybiera builder legacy vs nowy na podstawie flagi A/B (`PublicTokenRefreshAbState` / `PrivateTokenRefreshAbState`).
- OAuth `refresh_token` z retry 100/200/500 ms.

### Granty i endpointy OAuth
Z [OAuthNetworkingModule.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/authentication/networking/OAuthNetworkingModule.java).
Wszystkie z `client_id = "android"`.

| Grant | Scope | Endpoint |
|---|---|---|
| `password` | `public` | legacy `/token` |
| `public_token` | `public` | `API_GATEWAY_BASE_URL + oauth/api/token.issue` |
| `password` | `user` | legacy `/token` |
| `assertion` | `user` | legacy `/token` (Google) |
| `authorization_code` | `user` | legacy `/token` (web) |
| `refresh_token` | — | legacy `/token` ORAZ `oauth/api/token.issue` |

---

## 4. MECHANIZM AUTORYZACJI WEB (z reverse-engineeringu Next.js)

Z [KOMPENDIUM_ARCHITEKTURY_VINTED.md](file:///f:/PROJEKTY/vinted/vinted/raporty/02_reverse_engineering/KOMPENDIUM_ARCHITEKTURY_VINTED.md) i sondy.

### Sesja anonimowa (web)
`GET https://www.vinted.pl/` generuje:
- `access_token_web` (JWT Bearer)
- `refresh_token_web`
- `_vinted_fr_session`
- `anon_id`

### Nagłówki web (z `curl_cffi` chrome124)
- `Authorization: Bearer <access_token_web>`
- `User-Agent` Chrome 124
- `Referer` / `Origin` = `https://www.vinted.pl/`
- cookie `datadome` (z tego samego IP)
- cookie `_vinted_fr_session`, `anon_id`

### Ochrona
- DataDome WAF (`geo.captcha-delivery.com`) — chroni `POST /purchases/checkout/build`.
- Wymagany spójny odcisk TLS JA3/JA4.

---

## 5. PORÓWNANIE — NAGŁÓWKI

| Nagłówek | APK | Web |
|---|---|---|
| `Authorization: Bearer` | ✅ (accessToken, scope public/user) | ✅ (access_token_web) |
| `User-Agent` | ✅ (stały, android) | ✅ (Chrome) |
| `X-Anon-Id` | ✅ | ✅ (anon_id, cookie) |
| `X-V-Udt` | ✅ | ✅ (cookie/header) |
| `X-Platform` | ✅ `android` | ❌ (domyślnie brak) |
| `X-Portal` / `X-App-Version` | ✅ | ❌ |
| `X-OS-Version` / `X-Device-Model` | ✅ | ❌ (web ma inne: `sec-ch-ua`, screen) |
| `X-Screen-Width/Height` | ✅ | ✅ (inne nazwy) |
| `X-Device-UUID` | ✅ | ❌ |
| `X-Play-Integrity` | ✅ (logowanie/rejestracja) | ❌ (brak na web) |
| `X-V-Uid` / `X-V-Sid` | ✅ (z JWT `sub`/`sid`) | ✅ (z tego samego JWT) |
| DataDome cookie/headers | ✅ (SDK natywne) | ✅ (cookie `datadome`) |

---

## 6. PORÓWNANIE — MECHANIZM OAuth

| Aspekt | APK | Web |
|---|---|---|
| client_id | `android` | `web` (mobile web / desktop web) |
| Scope | `public` / `user` | `public` / `user` |
| Przyznanie public tokena | `public_token` przez `oauth/api/token.issue` | przy `GET /` (anon) |
| Refresh | `Authenticator` po 401, `refresh_token` | ten sam grant `refresh_token` |
| Odnawianie | automatyczne, 1s blokada przy 429 | ręczne / po wygaśnięciu |
| Dodatkowa ochrona logowania | `X-Play-Integrity` | DataDome |

---

## 7. PORÓWNANIE — ENDPOINTY (konkretny przypadek)

### Katalog `/api/v2/catalog/items`

| Parametr | APK | Web |
|---|---|---|
| Dostęp | ✅ Bearer scope public | ✅ Bearer scope public |
| `per_page` max | 96 | **96** (potwierdzone sondą) |
| `total_entries` | — | **zawsze 960** (sztuczny limit Vinted) |
| Rate-limit | natywny (okHttp/DataDome) | **~5 req / 6 s**, potem 429 code 106 |

### Checkout `POST /api/v2/purchases/checkout/build`

| Parametr | APK | Web |
|---|---|---|
| Ochrona | DataDome + Play Integrity | DataDome (403 bez cookie `datadome`) |
| Payload | `{"purchase_items":[{"id":..,"type":"item"}]}` | identyczny |

### Logowanie `POST /api/v2/oauth/token`

| Grant | APK | Web |
|---|---|---|
| public | `password` scope public (legacy) lub `public_token` (nowy) | `password` / anon |
| user | `password` / `assertion` (Google) / `authorization_code` (web) | te same |

---

## 8. KLUCZOWE RÓŻNICE (WNIOSKI)

1. **APK ma twardszą ochronę logowania**: `X-Play-Integrity` (Google) dla ścieżek
   `users`/`facebook_users`/`google_user` — web tego nie ma.
2. **APK ma natywny DataDome SDK** (fingerprint urządzenia, captcha), web polega na
   cookie `datadome` + TLS JA3/JA4.
3. **Web używa `client_id=web`**, APK `client_id=android` — endpointy OAuth wspólne, ale
   różny identyfikator klienta.
4. **Ten sam limit katalogu** po obu stronach: `per_page=96`, `total_entries=960`.
5. **APK odświeża token automatycznie** przez `Authenticator`; web musi zarządzać
   refresh tokenem ręcznie.
6. **Nagłówki device-fingerprint** (`X-Device-UUID`, `X-Platform`, `X-App-Version`)
   występują **tylko w APK** — web zastępuje je odciskiem przeglądarki (TLS, sec-ch-ua).

---

## 9. DODATKOWE USTALENIA (dopełnienie)

### `TwoFaErrorInterceptor` — nie dodaje nagłówków, obsługuje 2FA

[TwoFaErrorInterceptor.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/feature/verification/interceptor/TwoFaErrorInterceptor.java#L63-L99)
działa po stronie **odpowiedzi** (nie nagłówków żądania):

1. Gdy odpowiedź ma kod `400`, parsuje body jako `BaseResponse`.
2. Jeśli `baseResponse.code == GLOBAL_TWO_FACTOR_AUTH_REQUIRED` (i obecne
   `entityId` + `entityType`), publikuje zdarzenie `GlobalTwoFaRequired` na EventBus.
3. Czeka na wynik 2FA (`TwoFaResult.TWO_FA_PASSED`) i ponawia oryginalne żądanie
   przez `new RealCall(...).execute()`.

To wyjaśnia, dlaczego `TwoFaErrorInterceptor` figuruje w stosie `ProvideRawHttpClient`
między `SecurityProtectionInterceptor` a `DataDomeInterceptor` — jest to interceptor
reaktywny (retry po 2FA), a nie interceptor dodający nagłówki.

### `X-Debug-Pin`
Dodawany w [HeadersInterceptor.java](file:///f:/PROJEKTY/vinted/vinted/dane/apk/jadx_out/sources/com/vinted/shared/networking/interceptors/HeadersInterceptor.java#L76-L79)
**tylko** gdy ustawiona jest preferencja `trackerPin` (debug). W produkcji nieobecny.