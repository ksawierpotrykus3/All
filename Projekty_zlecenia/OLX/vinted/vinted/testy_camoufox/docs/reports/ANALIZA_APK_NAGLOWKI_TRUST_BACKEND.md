# JAK APLIKACJA IDENTYFIKUJE SIĘ WOBEC BACKENDU (nagłówki trust)

**Data:** 2026-08-31
**Metoda:** dekompilacja APK — interceptory OkHttp (`shared/networking/interceptors`)
**Konwencja:** `[UDOWODNIONE]` (z kodu źródłowego)

---

## Cel

Czy backend „ufa" aplikacji bardziej niż web (szybciej odbiera, luźniejsza walidacja)? Klucz tkwi w **unikalnych nagłówkach**, które aplikacja dodaje do każdego requestu, a web ich nie wysyła.

---

## Unikalne nagłówki aplikacji [UDOWODNIONE]

### 1. `HeadersInterceptor` — platforma i urządzenie
```java
builder.addHeader("X-Platform", "android");
builder.addHeader("X-Portal", buildContext.PORTAL);
builder.addHeader("X-App-Version", buildContext.VERSION_NAME);
builder.addHeader("X-OS-Version", Build.VERSION.RELEASE);
builder.addHeader("X-Device-Model", MODEL);          // "Manufacturer Model"
builder.addHeader("X-Screen-Width", widthPixels);
builder.addHeader("X-Screen-Height", heightPixels);
builder.addHeader("X-Local-Time", System.currentTimeMillis());
```

### 2. `ApiHeadersInterceptor` — tożsamość i token urządzenia
```java
builder.addHeader("User-Agent", userAgentString);   // UA aplikacji (nie przeglądarki)
builder.addHeader("X-Anon-Id", anonId);             // to samo co w web
builder.addHeader("X-V-Udt", userDeviceToken);      // <- UNIKALNE dla app
```

### 3. `DeviceFingerprintHeaderInterceptor` — fingerprint urządzenia
```java
builder.addHeader("X-Device-UUID", deviceUUID);     // <- UNIKALNE dla app
```

### 4. `VintedContextInterceptor` — locale
```java
builder.addHeader("Locale", isoLocale);
```

---

## Kluczowa różnica: web vs app

| Nagłówek | Web (przeglądarka) | App (Android) |
|---|---|---|
| `X-Platform` | ❌ brak (albo `web`) | ✅ `android` |
| `X-Device-UUID` | ❌ brak | ✅ obecny |
| `X-App-Version` | ❌ brak | ✅ obecny |
| `X-V-Udt` | ❌ brak | ✅ obecny |
| `User-Agent` | przeglądarka (Chrome/Firefox) | UA aplikacji |

**To jest sygnatura, po której backend rozróżnia klienta.** Web nie wysyła `X-Device-UUID`, `X-App-Version`, `X-V-Udt`, `X-Platform: android`.

---

## Jak to sprawdzić (test hipotezy trust)

1. **Zreplikować nagłówki app w curl_cffi** i porównać odpowiedź/status/czas z tymi samymi requestami bez nich.
2. **Porównać zachowanie checkout/build**:
   - z nagłówkami web (aktualny stan bota)
   - z nagłówkami app (`X-Platform: android`, `X-Device-UUID`, `X-App-Version`, `X-V-Udt`)
3. **Sprawdzić, czy X-V-Udt jest powiązany z sesją/cookies** — to jest „device token" używany do optymalizacji/szybszego rozpoznania (widoczne w `OptimizeDeviceTokenAnalytics`).

---

## [UDOWODNIONE] X-Device-UUID jest generowany po stronie klienta (MD5)

Z `NetworkPreferences.java`:

```java
deviceUUID = MD5(
    FirebaseInstallationId + Build.DEVICE + Build.DISPLAY
    + Build.HARDWARE + Build.MODEL + Settings.Secure.android_id
)
```

To **deterministyczny fingerprint urządzenia liczony lokalnie** (MD5 hex lowercase). Nie jest sekretem serwerowym — można go odtworzyć, znając składniki (ale android_id + FirebaseInstallationId są unikalne per instalacja).

## [UDOWODNIONE] v_udt to cookie serwerowe + header

`v_udt` (odpowiednik `X-V-Udt` header) jest:
- zapisywany jako **cookie** (`www.vinted.pl`, exp=1822494879),
- odsyłany jako nagłówek `X-V-Udt`,
- aktualizowany z response header `x-v-udt` (logika w `ApiHeadersInterceptor`).

To token **wydawany i rotowany przez backend** — nie da się go wyliczyć, trzeba mieć ważny (z sesji/profilu). W przechwyconym profilu wartość `v_udt` jest **stała między oboma profilami** (ta sama wartość base64) → token device jest powiązany z kontem/sesją, nie z konkretnym uruchomieniem.

## Wniosek o hipotezie "trust"

- `X-Device-UUID`: klientowo liczony MD5 — **można zreplikować** (stały fingerprint urządzenia).
- `X-V-Udt`: token serwerowy — **trzeba mieć ważny** (jest w cookies profilu).
- `X-Platform: android`, `X-App-Version` i pozostałe: **statyczne**, łatwe do dodania.

Wiarygodny test wymaga: (1) ważnego `v_udt` (mamy w cookies), (2) doklejenia nagłówków `X-Platform/X-App-Version/X-Device-UUID` do curl_cffi i porównania odpowiedzi.

---

## WYNIK TESTU LIVE (2026-08-31) — `users/current`

Porównanie web vs app na bezpiecznym endpoincie `GET /users/current` (TLS firefox152 + świeże cookies):

| Wariant | Status | Czas |
|---|---|---|
| web (`X-Platform: web`) | 200 | 234 ms |
| app (`X-Platform: android` + X-App-Version + X-V-Udt + X-Device-UUID...) | 200 | 204 ms |

**[UDOWODNIONE]** Backend **nie rozróżnia** web vs app na `users/current` — oba 200, identyczne body. Różnica 30ms to szum (keep-alive/second request szybszy).

**[WNIOSEK]** Hipoteza "trust" **NIE potwierdza się na zwykłym GET**. Sygnatura app może mieć znaczenie dopiero na **checkout/build** (tworzenie transakcji) — tam backend może surowiej walidować. Wymaga testu na buildu (ostrożnie — tworzy checkout).

Dowód: `bot/output/wynik_headers_app_vs_web_1788216895.json`.

---

## Źródła

- `HeadersInterceptor.java` — X-Platform, X-App-Version, X-Device-Model, wymiary ekranu
- `ApiHeadersInterceptor.java` — User-Agent, X-Anon-Id, X-V-Udt (device token)
- `DeviceFingerprintHeaderInterceptor.java` — X-Device-UUID
- `VintedContextInterceptor.java` — Locale

---

*Koniec analizy.*