# POZYSKANIE PLAINTEXTU INCOGNII — PRZEŁOM W REPLIKACJI TOKENU

**Data:** 2026-08-31
**Metoda:** Hook `crypto.subtle.encrypt` / `crypto.subtle.importKey` przez `add_init_script` w Camoufox (Firefox 152, profil `profil_firefox`)
**Konwencja:** `[UDOWODNIONE]` (obserwacja live) / `[DOMNIEMANE]` (hipoteza wymagająca weryfikacji)

---

## 1. Cel i rezultat

[UDOWODNIONE] Przechwycono **plaintext sygnałów Incognii ZANIM został zaszyfrowany** do tokenu `x-incognia-request-token`. Wcześniej token widzieliśmy wyłącznie jako nieprzenikniony JWE. Teraz znamy pełną zawartość.

Hook `crypto.subtle.encrypt` / `crypto.subtle.importKey` wstrzyknięty przez `page.add_init_script` przechwycił **14 wywołań `encrypt`** i **27 wywołań `import_key`** podczas realnego checkoutu.

---

## 2. Dekompozycja tokenu JWE [UDOWODNIONE]

Token `x-incognia-request-token` to **standardowy JWE (RFC 7516)**, 5 segmentów base64url:

| Segment | Rola | Rozmiar (dekodowany) |
|---|---|---|
| 1 | Protected header | `{"alg":"RSA-OAEP","enc":"A128CBC-HS256"}` (40 B) |
| 2 | Encrypted Key (CEK szyfrowany RSA-OAEP) | **256 B** → RSA 2048-bit |
| 3 | IV | 16 B |
| 4 | Ciphertext (AES-128-CBC + PKCS7) | 1952 B |
| 5 | Auth Tag (HMAC-SHA256 skrócony do 16 B) | 16 B |

Klucz publiczny Incognii: **RSA-2048, e=65537**, wyekstrahowany z `crypto.subtle.importKey` (format `spki`, 294 B DER).

---

## 3. Struktura plaintextu fingerprintu [UDOWODNIONE]

Główny payload (`{"app_id":...}`) zawiera **39 pól**. Klasyfikacja na podstawie porównania dwóch niezależnych pomiarów (run1 vs run2, ten sam profil, restart Camoufox):

### Pola deterministyczne (26) — stałe między sesjami:
`app_id`, `installation_id`, `cache_id`, `private_cache_id`, `user_agent`, `navigator_platform`, `timezone`, `timezone_offset`, `sdk_code_version` (12400), `sdk_build_timestamp`, `relevant_window_keys` (`["SharedWorker","WebSocket"]`), `token_version`, `url_host`, `ad_blocker_likely_present` i in.

### Pola zmienne (13):
| Pole | Charakter |
|---|---|
| `session_id` | nowy UUID per sesja Incognii |
| `event_id`, `event_timestamp`, `navigation_start_timestamp` | per request |
| `token_sequence_number` | **monotoniczny licznik (85 → 86)** |
| `token_generation_sequence_number` | jak wyżej |
| `last_data_sent_timestamp`, `last_vpn_data_sent_timestamp` | timestampy |
| **`canvas_paint_cpu_1/2`** | **ZMIENIA SIĘ między restartami Camoufox** |
| **`canvas_paint_gpu_1/2`** | **ZMIENIA SIĘ między restartami Camoufox** |

### Kluczowe wartości (run1):
- `app_id`: `0e806f9a-66d6-4c7e-bd94-382236e16bc8`
- `session_id`: `211936c0-f258-49b5-aead-dfb315b12c3b`
- `installation_id`: `88491775-9fde-4f08-bf9b-3f44929df23f`
- `canvas_paint_cpu_1`: SHA-256 hex (deterministyczny w obrębie jednej sesji)
- `token_sequence_number`: 85

---

## 4. Lekki generator tokenu — pure Python (bez JS runtime) [UDOWODNIONE]

Zbudowano generator [incognia_token_generator.py](file:///f:/PROJEKTY/vinted/vinted/testy_camoufox/implementation/curl-cffi/incognia_token_generator.py), który:

1. Generuje CEK 32 B (mac_key 16 B + enc_key 16 B)
2. Szyfruje CEK przez **RSA-OAEP(SHA-1)** kluczem publicznym Incognii
3. Szyfruje plaintext przez **AES-128-CBC + PKCS7**
4. Liczy tag przez **HMAC-SHA256** (skrócony do 16 B)
5. Składa kompletny JWE (5 segmentów)

**Weryfikacja:** wygenerowany token ma strukturę **identyczną** z realnym (header 40 B, encrypted_key 256 B, iv 16 B, ciphertext 1952 B, tag 16 B). Jedyna zależność: biblioteka `cryptography`.

**Wniosek:** lekki silnik asystujący curl-cffi **nie wymaga JS runtime** — wystarczy podmienić pola zmienne (`session_id`, `event_timestamp`, `token_sequence_number`) w znanym plainteście, zaszyfrować i wysłać.

---

## 5. Architektura wynikowa (rekomendowana)

```
Camoufox (ciężki silnik)          Lekki silnik (pure Python + curl-cffi)
├─ bootstrap sesji (logowanie)     ├─ pobiera plaintext fingerprintu
├─ generuje fresh session_id       ├─ podmienia pola zmienne
├─ harvestuje canvas/WebGL         ├─ szyfruje JWE (RSA-OAEP + AES)
└─ raz na ~N minut                 └─ wysyła checkout w <1s
```

---

## 6. Otwarte pytanie (bloker do weryfikacji)

[DOMNIEMANE] Serwer Incognii może odrzucić token z:
1. **Zduplikowanym/cofniętym `token_sequence_number`** — licznik jest monotoniczny, serwer może śledzić sekwencję.
2. **Niespójnym `canvas_paint_*` vs faktyczny fingerprint renderowanej strony** — Camoufox randomizuje canvas przy restarcie, co może powodować 403.

Wymagany test: wysłać wygenerowany token przez curl-cffi do endpointu i sprawdzić akceptację.

---

## Źródła

- `docs/logs/_crypto_hook_out.json` oraz `_crypto_hook_out_run1.json` — przechwycone wywołania crypto
- `docs/logs/_incognia_plaintext_0.json` … `_incognia_plaintext_13.json` — dekodowane plaintexty
- `docs/logs/_incognia_rsa_pub.spki` — klucz publiczny RSA Incognii (2048-bit)
- `docs/logs/_camoufox_checkout_probe.json` — status checkout/build (403)
- `implementation/curl-cffi/incognia_token_generator.py` — lekki generator JWE

---

*Koniec analizy.*