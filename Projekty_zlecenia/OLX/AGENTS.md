# AGENTS.md — Biblia agentów OLX Bot

Misja: zbudować autobuy OLX BuyWithDelivery przez metodę dowód → kod (jak Vinted).
Każdy agent pracujący nad tym repo MUSI przestrzegać poniższych zasad.

## Hierarchia prawdy (od najwyższej do najniższej)

1. dane/*.json — przechwycone odpowiedzi API (źródło prawdy)
2. dane/*.png, logs/* — wyniki testów i zrzuty
3. SYNTEZA_GLOWNA.md — aktualna zintegrowana prawda
4. recon/14_raport_autobuy_checkout.md — raport dowodowy autobuy
5. recon/0x_*.md — oryginalne raporty badawcze
6. AI research / niezweryfikowane — hipotezy (NIE UDOWODNIONE)

## Golden rule

> Jeśli nie ma w dane/*.json = NIE JEST UDOWODNIONE.

## Nakazy

1. Przed twierdzeniem o działaniu endpointu — pokaż przechwyconą odpowiedź (plik w dane/).
2. Oznaczaj każdą informację tagiem pewności: [UDOWODNIONE], [POTWIERDZONE], [DOMNIEMANE], [HIPOTEZA], [NIEPOTWIERDZONE].
3. Rozróżniaj numeryczne ID oferty od UUID delivery.rock.offer_id — to dwa różne identyfikatory.
4. Nowe odkrycia zapisuj w dane/ (surowy JSON) i aktualizuj SYNTEZA_GLOWNA.md.

## Zakazy

1. NIE twierdź, że checkout działa, dopóki nie przechwycono flow w dane/checkout_capture.json.
2. NIE używaj koncepcji z 08_autobuy_analiza_techniczna.md jako prawdy — jej endpointy delivery zwróciły 404.
3. NIE commitować dane/cookies.txt, tokenów, *.har, *.env.
4. NIE mylić access_token (krótki TTL ~15 min) z trwałą sesją — potrzebny refresh token.

## Kluczowe fakty (skrót)

- Detektor: przewidywanie sekwencyjnych ID + sliding window (bot/detector.py).
- HTTP: curl_cffi impersonate=chrome124 omija CloudFront 403.
- Sygnał dostawy: oferta ma delivery.rock = {offer_id: UUID, active: bool, mode: BuyWithDelivery|NotEligible}.
- Sesja: GET /api/v1/users/me/ → 200 gdy token ważny, 401 po wygaśnięciu (TTL ~15 min).
- Checkout: NIEZBADANY — wymaga świeżej sesji i przechwycenia w przeglądarce.