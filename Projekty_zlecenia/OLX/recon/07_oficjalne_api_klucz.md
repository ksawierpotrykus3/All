# Recon OLX — OFICJALNE API partnerskie (klucz z rozmowy) — 2026-08-24

## Dowód 29: Klucz deweloperski DZIAŁA — token OAuth uzyskany ✅

Endpoint OAuth: `POST https://www.olx.pl/api/open/oauth/token`

Body (client_credentials):
```json
{
  "grant_type": "client_credentials",
  "client_id": "202745",
  "client_secret": "HucUsS3hhReAr5j5V4BN5I85rlOM0y2y5cFGoKjJbXuPO5YI",
  "scope": "v2 read write"
}
```

Odpowiedź: `200 OK` z prawidłowym `access_token` (JWT). Zdekodowany payload JWT:
- `aud`: `partner_api`
- `client_id`: `202745`
- `client_tier`: `0`
- `partner_code`: `4420`
- `scope`: `v2 read write`
- `exp`: ~24h (86374 s)

**Wniosek:** klucz NIE wygasł, OAuth działa, aplikacja ma dostęp partnerski.

## Dowód 30: Endpoint partnerski wymaga tokenu UŻYTKOWNIKA (nie aplikacji)

Test `POST /api/partner/adverts` z nagłówkiem `Version`:

| Version | Odpowiedź |
|---------|-----------|
| 2.0 | `400 Invalid user ID in token` |
| 1.0 | `400 Unsupported API version: 1.0` |
| (brak) | `400 Missing required 'Version' header!` |

**Wnioski:**
1. Poprawna wersja API to **2.0** (bo 1.0 odrzuca jako "unsupported").
2. Ale `/api/partner/adverts` wymaga **user ID w tokenie** — czyli tokenu wygenerowanego dla KONKRETNEGO KONTA UŻYTKOWNIKA OLX (OAuth authorization_code), nie `client_credentials`.
3. To jest endpoint do zarządzania **własnymi ogłoszeniami** partnera (konto klienta), a NIE do wyszukiwania cudzych ofert.

## Dowód 31: WNIOSEK — klucz NIE daje wyszukiwania ofert

Oficjalny klucz developerski (Client ID 202745):
- ✅ działa (token ważny)
- ✅ daje dostęp do API partnerskiego v2 (zarządzanie własnymi ogłoszeniami partnera)
- ❌ NIE daje wyszukiwania/monitoringu cudzych ogłoszeń (to by wymagało tokenu konta klienta z authorization_code)

**Co to znaczy dla metody przewagi:**
- Przewaga nad wyszukiwarką NIE pochodzi z tego klucza.
- Przewaga pochodzi z **publicznego API** `/api/v1/offers/{id}/` (odczyt po ID) + skanowania rosnących ID — co już potwierdziliśmy jako działające (dowód 16-22, 28).
- Klucz może ewentualnie dawać wyższy rate-limit przy wywołaniach API, ale samo źródło danych o ofertach jest publiczne.

## Dalszy plan
1. Skupić się na publicznym API + skanowanie ID (to jest źródło przewagi).
2. Klucz trzymać jako opcję (jeśli okaże się, że bez klucza są limity).
3. Nie tracić czasu na endpoint partnerski `/adverts` — wymaga tokenu użytkownika, którego nie mamy (i do monitoringu nie jest potrzebny).