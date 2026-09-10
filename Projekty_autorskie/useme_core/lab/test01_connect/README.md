# Test 01 – Połączenie i dostęp do Useme

## Status: 🔴 nie rozpoczęty
## Data: -

## Cel
Sprawdzić, czy Playwright + Camoufox + Firefox łączą się z Useme bez blokady Cloudflare,
oraz czy jesteśmy zalogowani przez cookies.

## Kroki
1. Zainstalować `playwright` + `camoufox`
2. Uruchomić Firefox przez Playwright z profilem zawierającym cookies
3. Wejść na URL kategorii
4. Sprawdzić, czy strona się ładuje
5. Zrobić screenshot (tylko do diagnostyki)
6. Sprawdzić, czy widać oferty (czy nie przekierowuje na login)

## Oczekiwany wynik
- Strona załadowana poprawnie
- Brak blokady Cloudflare (lub do przejścia)
- Widać listę ofert (zalogowani)

## Wyniki
*(do uzupełnienia po teście)*