# Raport 01: Empiryczny Dowód Wygasania Tokena i Falsyfikacja Ręcznego Kopiowania

> Data: 2026-09-02T19:16:35+02:00
> Status: [UDOWODNIONE]

## 1. Cel eksperymentu
Sprawdzić, czy wklejone przez użytkownika ciasteczko `access_token` jest w stanie poprawnie autoryzować zapytania do endpointu profilu `/api/v1/users/me/`, oraz zbadać dokładny timestamp wygaśnięcia tokena.

---

## 2. Analiza kryptograficzna tokena JWT

Wklejony token JWT został zdekodowany do struktury JSON:

```json
{
  "sub": "06727a02-0312-4a9e-b6f6-e6b1fd331594",
  "email_verified": true,
  "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_dUjFuvTf4",
  "cognito:username": "4fa0d8d9-e79d-4e45-b836-7c9d46decb2a",
  "aud": "6j7elk01p32o648o1io8lvhhab",
  "token_use": "id",
  "auth_time": 1788368209,
  "iat": 1788368209,
  "exp": 1788369109,
  "email": "ksawierpotrykus3@gmail.com"
}
```

### Parametry czasowe:
- Czas wydania tokena (`iat`): `1788368209`
- Czas wygaśnięcia tokena (`exp`): `1788369109`
- Całkowity czas życia tokena: `exp - iat = 900 sekund (dokładnie 15 minut)`.
- Czas wykonania testu przez system: `1788369385`.
- Opóźnienie względem wygaśnięcia: `1788369385 - 1788369109 = +276 sekund (4 minuty i 36 sekund po czasie ważności)`.

---

## 3. Próba autoryzacji HTTP (curl_cffi)

Wykonano bezpośrednie zapytanie z nagłówkiem `Authorization: Bearer {token}`:
```python
requests.get("https://www.olx.pl/api/v1/users/me/", headers=headers, impersonate="chrome124")
```

### Wynik:
- **Kod statusu HTTP**: `401 Unauthorized`
- **Odpowiedź serwera**:
```json
{
  "error": "invalid_token",
  "error_description": "Invalid JWT token: Expired token"
}
```

---

## 4. Twarde wnioski inżynierskie

1. **Ręczne kopiowanie ciasteczek jest nieskuteczne [UDOWODNIONE]**:
   Token JWT wygasa już po 15 minutach. Zanim użytkownik przekopiuje dane, otworzy terminal lub uruchomi test, token jest martwy i API zwraca 401.

2. **Wymóg architektury trwałej sesji [UDOWODNIONE]**:
   System autobuy musi samodzielnie utrzymywać i odświeżać tokeny bez udziału człowieka. Wykorzystamy architekturę z projektu Vinted (`persistent_context`), w której przeglądarka utrzymuje sesję na stałe w dedykowanym profilu na dysku.
