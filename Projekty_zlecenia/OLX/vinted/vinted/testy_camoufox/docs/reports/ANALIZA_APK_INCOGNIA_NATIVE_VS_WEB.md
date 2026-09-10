# ANALIZA APK: Incognia native vs web — przepływ tokena

**Data:** 2026-09-01
**Źródło:** dekompilacja APK Vinted 26.33.1 (`jadx`)
**Poziom pewności:** [UDOWODNIONE] — analiza statyczna kodu produkcyjnego

---

## 🎯 Cel

Porównać natywną implementację Incognii (SDK Androida) z wersją web (przechwycony
wcześniej plaintext), aby odpowiedzieć: **czy token `X-Incognia-Request-Token` da się
zbudować bez SDK?**

## ❌ WNIOSEK GŁÓWNY: web ≠ native (dwie różne implementacje)

**[UDOWODNIONE]** Token Incognia w APK **NIE jest standardowym JWE** jak w wersji web.

| Aspekt | Web (przechwycony) | Native (APK) |
|--------|--------------------|---------------|
| Format | JWE (`header.encryptedKey.iv.cipherText.tag`) | Custom binarny |
| RSA | RSA-OAEP **SHA-1** | RSA-OAEP (custom `HVz`) |
| Szyfr danych | **A128CBC-HS256** (AES-CBC + HMAC) | **AES (custom, obfuskowane S-boxy)** |
| Klucz publiczny | wyekstrahowany (RSA-2048) | **hardcoded, ale obfuskowany** |
| Dodatkowa warstwa | — | **Deflater (zlib level 5)** przed szyfrowaniem |
| Użyte endpointy | checkout/build | checkout/build + checkout/payment |

**Wniosek:** replikacja tokenu native wymaga odtworzenia obfuskowanego szyfru AES
(ukryte S-boxy), deobfuskacji klucza RSA oraz kompresji zlib — znacznie trudniejsze niż
wersja web.

---

## 🔐 Struktura natywnego tokena (odtworzona)

Źródło: `qvI.n(String)` [qvI.java L170-226]

```
[1 bajt  = 0x01]                    // wersja/typ
[RSA-OAEP(32-bajtowy klucz AES)]    // klucz sesyjny zaszyfrowany kluczem publicznym
[16 bajtów = IV]
[Deflater(zlib,5) → AES-CBC(plaintext JSON)]  // skompresowane i zaszyfrowane dane
```

Całość base64 (`Qa.n(11, ...)`).

### Przepływ generowania (od publicznego API do tokena)

```
Incognia.generateRequestTokenSync()
  └─ VE.nMe()                          // buduje JSON fingerprintu
       └─ qvI.n(json)                  // kompresja + szyfrowanie
```

Źródła:
- `Incognia.java` L84-155 — `generateRequestTokenSync` (timeout 5000ms)
- `IncogniaSdkGatewayImpl.java` L119 — `Incognia.generateRequestTokenSync(0L, 1, null)`
- `VE.java` L35-95 — konstrukcja JSON + dodanie pól (`device_id`, timestamp, sequence)
- `qvI.java` L170-226 — kompresja zlib + szyfrowanie

---

## 🔑 Klucze RSA (hardcoded, ale obfuskowane)

Źródło: `POB.java` L114-115

```java
this.l = new HVz(new BigInteger(new String(gcd.Obx().nMe, UTF_8)), ...);  // klucz #1
this.z = new HVz(new BigInteger(new String(gcd.n().nMe, UTF_8)), ...);    // klucz #2
```

Klucze pochodzą z `gcd.Obx()` / `gcd.n()` — setki bajtów obfuskowanych
(wartości jawne > 255 rzutowane na `byte`, potem dekodowane przez `Yv`).
**Realny moduł nie jest czytelny bez deobfuskacji.**

---

## 🧩 Custom AES z obfuskowanymi S-boxami

Źródło: `G.java` (klasa `G` — szyfr blokowy)

- `AAX` / `Io` — dwa 256-bajtowe S-boxy (substytucja nieliniowa)
- `RC` — stałe rundowe (Rcon)
- Klucz 16/24/32 bajtów → konstrukcja rozszerzonego klucza w `G(byte[], byte[], byte[])`
- `nMe(byte,byte)` — mnożenie w GF(2^8) (mod 0x1B = redukcja AES)
- To jest **AES z obfuskowanymi tabelami** (white-box/obfuskacja), nie standardowe tablice AES.

**Wniosek:** odwzorowanie na czysty Python wymaga rekonstrukcji S-boxów i pełnej
logiki rund — wykonalne, ale pracochłonne; bez tego nie odtworzymy tokena native.

---

## 🌐 Gdzie token jest wysyłany

**[UDOWODNIONE]** Header `X-Incognia-Request-Token` w 2 endpointach:

| Endpoint | Plik |
|----------|------|
| `POST purchases/checkout/build` | `CheckoutApi.java` L23-24 |
| `POST purchases/{id}/checkout/payment` | `PaymentsApi.java` L29-30 |

---

## 📦 Natywna biblioteka .so (potwierdzenie PRIORYTETU 4)

**[UDOWODNIONE]** `Incognia` ładuje **jedną** natywną bibliotekę:

```java
// FT.java L26
System.loadLibrary((String) ad.qf.getValue());
```

- Nazwa biblioteki jest zaszyfrowana (obfuskowana stała `ad.qf`)
- To **jedyna** natywna zależność Incognii w Dex
- Potwierdza, że część logiki (kryptografia / fingerprint) jest poza Dex w `.so`

---

## 📊 Status wiedzy

| Element | Status |
|---------|--------|
| Web używa JWE (RSA-OAEP SHA-1 + A128CBC-HS256) | ✅ UDOWODNIONE (plaintext + SPKI) |
| Native używa custom formatu (zlib + AES + RSA) | ✅ UDOWODNIONE (analiza `qvI`) |
| Web ≠ native (dwie implementacje) | ✅ UDOWODNIONE |
| Klucz RSA native | ⚠️ hardcoded, obfuskowany |
| Szyfr AES native | ⚠️ obfuskowane S-boxy |
| Natywna biblioteka .so | ✅ potwierdzona (`System.loadLibrary`) |
| Replikacja tokena native w pure Python | ❌ znacznie trudniejsza niż web |

---

## 🚀 Rekomendacja

1. **NIE drążyć deobfuskacji native AES/RSA** — wysoki koszt, niepewna wartość.
2. **Zamiast tego:** token web (JWE) już mamy i jest **prostszy** — sprawdzić, czy
   backend akceptuje token web w kontekście, gdzie native by go nie wysłał.
   To jest tańszy eksperyment niż odtwarzanie white-box AES.
3. **PRIORYTET 4 (.so)** — uruchomić tylko, jeśli test akceptacji tokenu web zawiedzie
   i okaże się, że fingerprint device (poza Dex) jest wymagany przez serwer.

---

**Źródła (jadx):**
- `com/vinted/feature/incognia/IncogniaSdkGatewayImpl.java`
- `com/incognia/Incognia.java`
- `com/incognia/internal/VE.java` (budowa fingerprintu)
- `com/incognia/internal/qvI.java` (kompresja + szyfrowanie)
- `com/incognia/internal/G.java` (obfuskowany AES)
- `com/incognia/internal/HVz.java` (RSA-OAEP custom)
- `com/incognia/internal/POB.java` (klucze RSA)
- `com/incognia/internal/gcd.java` (obfuskowane klucze)
- `com/incognia/internal/FT.java` (loadLibrary)
- `com/vinted/feature/checkout/api/CheckoutApi.java`
- `com/vinted/feature/payments/api/PaymentsApi.java`