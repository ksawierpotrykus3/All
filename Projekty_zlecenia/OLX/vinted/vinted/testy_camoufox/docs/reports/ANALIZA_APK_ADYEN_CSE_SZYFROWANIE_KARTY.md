# ANALIZA APK: Adyen CSE — szyfrowanie karty (JWE)

**Data:** 2026-09-01
**Źródło:** dekompilacja APK Vinted 26.33.1 (`jadx`)
**Poziom pewności:** [UDOWODNIONE] — pełny algorytm odtworzony z kodu produkcyjnego

---

## 🎯 Cel

Odtworzenie algorytmu szyfrowania karty Adyen (Client-Side Encryption, CSE), aby
tokenizować kartę lokalnie — bez emulatora. To klucz do rozwiązania błędu
**payment error 114** („Purchase card is not valid"), który wynika z braku poprawnej
tokenizacji karty przed finalizacją płatności.

---

## 🧩 Przepływ tokenizacji karty (3 requesty)

**[UDOWODNIONE]** Źródło: `CardRegistrationsCentralApi.java` + `CardRegistrationsRepositoryImpl.java`

```
1. POST payments/public/api/card_registrations
   body: {"card_registration": null}
   → odpowiedź 200: { card_registration_id, access_key, provider: "adyen", ... }

2. Szyfruj lokalnie kartę kluczem access_key (algorytm JWE poniżej)

3. PUT payments/public/api/card_registrations/{card_registration_id}
   header: Origin
   body: encrypted_card_details (4 osobne pola JWE)
```

### Endpointy (z adnotacji Retrofit)

| Metoda | Ścieżka | Cel |
|--------|---------|-----|
| POST | `payments/public/api/card_registrations` | utworzenie rejestracji karty → zwraca `access_key` |
| PUT | `payments/public/api/card_registrations/{card_registration_id}` | wysłanie zaszyfrowanej karty |
| POST | `payments/public/api/card_registrations/authorisation` | autoryzacja po 3DS |
| POST | `payments/public/api/card_registrations/failure` | zgłoszenie niepowodzenia |
| GET | `payments/public/api/card_registrations/brands` | wykrycie marki karty po BIN |

### Klucz publiczny Adyen

**[UDOWODNIONE]** Klucz NIE jest stały — pochodzi z pola `access_key` odpowiedzi
`POST card_registrations`. Format: `{eksponent}|{moduł}` (hex), dokładnie **518 znaków**.

---

## 🔐 Algorytm szyfrowania JWE

**[UDOWODNIONE]** Źródło: `DefaultGenericEncryptor.java`, `JSONWebEncryptor.java`,
`EncryptionPlainTextGenerator.java`

### Nagłówek JWE (statyczny)

```json
{"alg":"RSA-OAEP-256","enc":"A256GCM","version":"1"}
```

### Plaintext (JSON)

```json
{
  "number": "4111111111111111",
  "expiryMonth": "12",
  "expiryYear": "2026",
  "cvc": "123",
  "holderName": "Jan Kowalski",
  "generationtime": "2026-09-01T12:34:56.789Z"
}
```

- `generationtime` = czas UTC w formacie `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`
- `holderName` opcjonalne (usuwane whitespace'y, `\s{2,}` → pojedyncza spacja)

### Kroki kryptograficzne

```python
# 1. Losowy 32-bajtowy klucz AES (SecureRandom)
aes_key = os.urandom(32)

# 2. Szyfruj klucz AES przez RSA-OAEP-256
#    Cipher: RSA/ECB/OAEPWithSHA-256AndMGF1Padding
#    OAEP params: digest=SHA-256, MGF1=SHA-256, PSource=default (puste)
encrypted_key = rsa_oaep_sha256_encrypt(public_key, aes_key)

# 3. Szyfruj plaintext przez AES-256-GCM
iv = os.urandom(12)
cipher = AES-GCM(aes_key, iv, tag_length=128)
cipher.update_aad(base64(header))          # AAD = base64 nagłówka JWE
ciphertext_and_tag = cipher.encrypt(plaintext_utf8)
ciphertext = ciphertext_and_tag[:-16]      # całość minus ostatnie 16 bajtów
auth_tag   = ciphertext_and_tag[-16:]      # ostatnie 16 bajtów (tag GCM)

# 4. Wynik — złączony JWE
jwe = ".".join([
    base64(header),          # JSON header, base64 (URL-safe)
    base64(encrypted_key),   # klucz AES zaszyfrowany RSA
    base64(iv),              # 12 bajtów
    base64(ciphertext),      # dane
    base64(auth_tag)         # 16 bajtów
])
```

### Parsowanie klucza publicznego

```java
// Walidacja: regex ([A-F]|[0-9]){5}\|([A-F]|[0-9]){512}, długość 518
String[] parts = key.split("\\|");          // limit 6
BigInteger modulus  = new BigInteger(parts[0], 16);  // moduł
BigInteger exponent = new BigInteger(parts[1], 16);  // eksponent
RSAPublicKeySpec(modulus, exponent)
```

**Uwaga:** kolejność w parsowaniu — `parts[1]` = eksponent (5 znaków), `parts[0]` = moduł (512 znaków).

---

## 🗂️ Struktura danych wejściowych / wyjściowych

### `UnencryptedCard`
- `number`, `expiryMonth`, `expiryYear`, `cvc`, `cardHolderName`

### `EncryptedCard` (4 osobne JWE)
- `encryptedCardNumber`
- `encryptedExpiryMonth`
- `encryptedExpiryYear`
- `encryptedSecurityCode`

### `encryptFields` vs `encrypt`

- **`encryptFields`** — szyfruje każde pole **osobno** (osobny klucz AES i IV dla każdego).
  Używane do wysyłki `encrypted_card_details` w `PUT card_registrations`.
- **`encrypt`** — szyfruje wszystkie pola naraz w jeden JWE (single-shot).
  Używane do `token` w `updateCardRegistration`.

---

## 🔗 Ścieżka wywołania w aplikacji

```
AdyenCreditCardTokenizationService.tokenizeCard()
  └─ CardEncrypter.encrypt(unencryptedCard, accessKey)      → token (single JWE)
  └─ CardEncrypter.encryptFields(unencryptedCard, accessKey) → 4 pola JWE
       └─ DefaultGenericEncryptor.encryptFields(...)
            └─ JSONWebEncryptor (nagłówek + KeyFactory RSA)
```

---

## 📊 Status wiedzy

| Element | Status |
|---------|--------|
| Algorytm JWE Adyen | ✅ UDOWODNIONE |
| Format klucza publicznego `exp\|mod` | ✅ UDOWODNIONE |
| Endpointy `card_registrations` | ✅ UDOWODNIONE (Retrofit) |
| Źródło klucza publicznego (`access_key`) | ✅ UDOWODNIONE |
| Szyfrowanie bez emulatora (pure Python) | ⚠️ DOMNIEMANE — brak testu na żywo |
| Weryfikacja end-to-end (realny token → 3DS) | ❌ NIEPOTWIERDZONE |

---

## 🚀 Następny krok

1. Napisać skrypt Python odtwarzający `encryptFields` + `encrypt`
   (biblioteka `cryptography` lub `pycryptodome`).
2. Test integracyjny: `POST card_registrations → szyfrowanie → PUT` na żywej sesji.
3. Zweryfikować akceptację tokenu i przejście do 3DS.

---

**Źródła (jadx):**
- `com/adyen/checkout/cse/CardEncrypter.java`
- `com/adyen/checkout/cse/UnencryptedCard.java`
- `com/adyen/checkout/cse/EncryptedCard.java`
- `com/adyen/checkout/cse/internal/DefaultGenericEncryptor.java`
- `com/adyen/checkout/cse/internal/JSONWebEncryptor.java`
- `com/adyen/checkout/cse/internal/EncryptionPlainTextGenerator.java`
- `com/vinted/feature/creditcardadd/psp/AdyenCreditCardTokenizationService.java`
- `com/vinted/feature/creditcardadd/repository/CardRegistrationsRepositoryImpl.java`
- `com/vinted/feature/creditcardadd/impl/svcpaymentspublicapicentral/apis/CardRegistrationsCentralApi.java`