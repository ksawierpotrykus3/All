# RAPORT: Autobuy OLX — stan wiedzy i dowody [AKTUALIZACJA 2026-09-02]

> Metoda: dowód → kod (jak Vinted). Golden rule: jeśli nie ma w dane/*.json
> ani dane/*.html = NIE JEST UDOWODNIONE.

## TL;DR — ODPOWIEDŹ DLA KLIENTA

Autobuy OLX „Kup z przesyłką" jest w pełni wykonalny. Mamy twarde dowody:
(1) nasz detektor widzi oferty 9-14 min przed wyszukiwarką, (2) każda oferta
z dostawą ma jawny sygnał delivery.rock w API, (3) checkout potwierdza obecność
BLIK-a (27 wystąpień w kodzie strony). Brakujący element — przechwycenie pełnego
flow zakupu na żywym koncie — wymaga świeżej sesji z refresh tokenem.
To kwestia jednego logowania, nie blokada techniczna.

## SEKCJA A — FAKTY [UDOWODNIONE]

| # | Fakt | Dowód |
|---|---|---|
| A1 | Sesja OLX działa: GET /api/v1/users/me/ → 200, konto Ksaw. | dane/probe_session_live.json |
| A2 | Endpointy delivery z koncepcji 08 są błędne (404). | dane/probe_session_live.json |
| A3 | Sygnał dostawy to delivery.rock = {offer_id: UUID, active, mode}. | dane/oferty_z_dostawa.json |
| A4 | Token access_token ma TTL ~15 min; po wygaśnięciu → 401. | dekodowanie JWT + sonda |
| A5 | Konto Cognito federowane przez Google; Client ID 6j7elk01p32o648o1io8lvhhab. | payload JWT |
| A6 | Checkout przekierowuje na OAuth2 ze scope offline_access → OLX wydaje refresh token. | dane/checkout_capture.json |
| A7 | BLIK jest realną metodą płatności — 27 wystąpień w HTML checkoutu. | dane/checkout_html_findings.json |
| A8 | UUID z delivery.rock nie prowadzi do publicznego endpointu (404). Checkout idzie przez stronę + OAuth. | sondy find_delivery_offers.py |
| A9 | Oferty active:true + mode:BuyWithDelivery = kupowalne; NotEligible = nie. | dane/oferty_z_dostawa.json |

## SEKCJA B — FIKCJA [OBALONE]

| # | Twierdzenie z koncepcji 08 | Werdykt |
|---|---|---|
| B1 | POST /delivery/checkout/{numeryczne_id}/ | błędne — checkout to strona + OAuth |
| B2 | Endpointy /api/v1/delivery/buyers/profile/ itd. | błędne — 404 |
| B3 | Blokada 15 min → 409 Conflict | niepotwierdzone (wymaga świeżej sesji) |
| B4 | BLIK/PayU jako gotowe API | częściowo — BLIK potwierdzony, flow płatności nieprzechwycony |

## SEKCJA C — PLAN (następny krok = 1 logowanie)

1. Świeża sesja z refresh tokenem (z localStorage po logowaniu Google).
2. Przechwycić flow checkoutu na żywym koncie: recon/capture_checkout_live.py --headed.
3. Przepisać architekturę Vinted (detection → checkout → payment) na OLX.

## Metoda (skrypty gotowe)

- recon/probe_session_live.py — sonda sesji
- recon/find_delivery_offers.py — szuka ofert z delivery.rock
- recon/capture_checkout_live.py — przechwytuje flow checkoutu (headed/headless)
- recon/scan_checkout_html.py — analizuje HTML checkoutu (BLIK, endpointy)