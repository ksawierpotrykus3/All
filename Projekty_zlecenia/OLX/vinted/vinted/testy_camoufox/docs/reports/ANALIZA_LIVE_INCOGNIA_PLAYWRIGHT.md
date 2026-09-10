# Analiza dynamiczna (live) Incognia/DataDome przez Playwright — wyniki sesji Vinted

**Data:** 2026-08-31
**Metoda:** MCP Playwright (Chromium 151) + `browser_network_requests` + `browser_evaluate`/`browser_run_code`
**Konwencja:** `[UDOWODNIONE]` (obserwacja live) / `[DOMNIEMANE]`

---

## 1. Werdykt: Incognia DZIAŁA w czystym Playwright

[UDOWODNIONE — live] Na stronie głównej `https://www.vinted.pl/` (bez checkoutu, bez DataDome challenge) przeglądarka Playwright (Chromium 151) wykonała **pełną sekwencję Incognia**, którą wcześniej dokumentacja oznaczala jako "wymagającą prawdziwej przeglądarki / nieznaną".

To rozstrzyga wątpliwość z [analiza_headed_incognia_speed.md](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/docs/reports/analiza_headed_incognia_speed.md), gdzie w Camoufox (Firefox) `Incognia: false`. W Chromium przez Playwright SDK ładuje się i działa.

---

## 2. Pełna sekwencja requestów Incognia (przechwycona live)

| # | Request | Status |
|---|---|---|
| 1 | `GET api.vinted.pl/j3r4zw/v1/config` | 200 → `sdk_instance_id` + `version` |
| 2 | `POST api.vinted.pl/j3r4zw/v1/consume` | 200 (sygnały snapshot) |
| 3 | `GET metrics.vinted.lt/web/cchd_config` | 200 |
| 4 | `GET metrics.vinted.lt/web/pvt_cchd_config` | 200 |
| 5 | `POST conn-check.icg-in.com/connectioncheck` | 200 |
| 6 | `GET conn-check.icg-in.com/netconn/{JWE}` | 200 |
| 7 | `POST dd.vinted.lt/js` | 200 (DataDome) |

**Przełom [UDOWODNIONE]:** krok 6 — endpoint `conn-check.icg-in.com/netconn/{token}` — jest jawnym **JWE (RSA-OAEP + A128CBC-HS256)**. Nagłówek JOSE jest widoczny w URL:
```
{"alg":"RSA-OAEP","enc":"A128CBC-HS256"}
```
To jest **dokładnie** format, który wcześniejsze raporty (RAPORT_INZYNIERSKI_curl_cffi_JS_engine_luki.md) oznaczały jako „WebSocket binary frames — protokół nieznany". Live potwierdził: to **nie** WebSocket binarny, lecz **HTTP GET z JWE w ścieżce URL**.

---

## 3. Fakty o `sdk_instance_id` i SDK (live)

[UDOWODNIONE]:
- `sdk_instance_id` jest **dynamiczny per sesja**: `6ec548c0-c79e-4881-a980-17455dae544b` (UUID), a nie stała.
- `GET api.vinted.pl/j3r4zw/v1/config` zwraca: `{"sdk_instance_id":"...","version":"85d7e768568e"}` — wersja `85d7e768568e` = hash bundle SDK.
- `window.__V` = wrapper Incognia, **jedyna publiczna metoda** to `initSdk`. Nie ma `getToken`.
- Kod `initSdk` jest zminifikowany (tablica `t(1847)`, `t(1259)` itd.) — spójne z obfuskowanym SDK z dekompilacji APK (`k7v3q2_DEOBFUSCATED.js`).
- `initSdk` przyjmuje `{ sdkInstanceId, loaderTimings, onError, consumeUrl, snapshotCollectors, interactionCollectors }`.

[DOMNIEMANE] `x-incognia-request-token` jest generowany wewnątrz SDK (po `initSdk` + snapshot + interaction), nie eksponowany publicznie — potwierdza to brak metody `getToken` na wrapperze.

---

## 4. DataDome — status na homepage

[UDOWODNIONE]: `document.cookie` zawiera `datadome=...`, a `window.DataDomeJsTag`, `dataDomeProcessed`, `dataDomeOptions` istnieją. DataDome **nie rzucił challenge** na stronie głównej (200 na wszystkich requestach). To spójne z ustaleniem: DataDome blokuje dopiero checkout/build, nie listing.

---

## 5. Bloker sesji zalogowanej (nie cel — uwaga)

[UDOWODNIONE]: plik `cookies_profil.json` zawiera `access_token_web` z `exp=1788137858` — **przedawniony** o ~17h (test ~2026-08-31). `refresh_token_web` (exp=1788735458) byłby ważny, ale refresh wymaga świeżego CSRF z JWT, a hardcoded `75f6c9fa...` nie przechodzi (401/400). To bloker **tylko** dla przechwycenia realnego `x-incognia-request-token` z checkoutu — nie dla wniosków powyżej.

---

## 6. Wnioski dla projektu

1. **[UDOWODNIONE]** Incognia jest **transportem HTTP (JWE w URL)**, nie WebSocketem binarnym. To upraszcza potencjalną replikację.
2. **[UDOWODNIONE]** `sdk_instance_id` + `version` są pobierane z `j3r4zw/v1/config` per sesja — dokładnie jak zakładał kod bota (config.py → `SDK_CONFIG_URL`).
3. **[UDOWODNIONE]** Sekwencja Incognia działa bez pełnego fingerprintu przeglądarki — kluczowy sygnał, że emulacja SDK po stronie Node.js może być bliżej niż zakładano.
4. **[DOMNIEMANE]** Do replikacji `x-incognia-request-token` potrzebna jest pełna sekwencja snapshot + interaction z sygnałami — nadal wymaga polifilli browser API (canvas/WebGL/audio), ale warstwa transportowa jest już jasna.

---

## Źródła (live)

- `browser_network_requests` — przechwycone requesty Incognia/DataDome (sekcja 2)
- `browser_evaluate` — `window.__V` / cookies / `sdk_instance_id`
- `browser_run_code` — wstrzyknięcie cookies (sesja przedawniona, 401)

---

*Koniec analizy live.*