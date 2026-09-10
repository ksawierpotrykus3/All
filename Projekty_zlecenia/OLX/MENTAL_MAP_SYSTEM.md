# MENTAL MAP SYSTEM — Mapa wiedzy OLX Bot

## Drogowskaz dla agentów AI — „Gdzie co jest, co zbadane, gdzie zacząć"

## CEL SYSTEMU

Eliminacja pytań: „co zbadane, gdzie to jest, czy wiarygodne, gdzie zacząć".

## SYSTEM SKOJARZEŃ — Mental Triggers

[AGENT MENTAL TRIGGER: "checkout", "zakup", "autobuy", "BuyWithDelivery", "przesyłka"]
→ PRIMARY: recon/14_raport_autobuy_checkout.md
→ SECONDARY: dane/oferty_z_dostawa.json (pole delivery.rock)
→ SOURCE: dane/probe_session_live.json
→ FACT: delivery.rock.offer_id to UUID, nie numeryczne ID. Endpointy z koncepcji 08 są błędne (404).
→ WARNING: flow checkoutu NIEZBADANY — wymaga świeżej sesji.

[AGENT MENTAL TRIGGER: "sesja", "login", "token", "cognito", "access_token"]
→ PRIMARY: dane/probe_session_live.json
→ FACT: GET /api/v1/users/me/ → 200 przy ważnym tokenie, 401 po wygaśnięciu.
→ FACT: access_token ma TTL ~15 min (JWT exp - iat = ~900s).
→ WARNING: brak refresh tokena w cookies — sesja umiera po ~15 min.

[AGENT MENTAL TRIGGER: "detektor", "ID", "sekwencja", "przewaga", "wyszukiwarka"]
→ PRIMARY: bot/detector.py, bot/http_client.py
→ FACT: przewidywanie sekwencyjnych ID + sliding window + hole-sweeper.
→ FACT: curl_cffi impersonate=chrome124 omija CloudFront 403.
→ FACT: przewaga 9-14 min nad wyszukiwarką.

[AGENT MENTAL TRIGGER: "dostawa", "delivery", "rock", "BuyWithDelivery"]
→ PRIMARY: dane/oferty_z_dostawa.json
→ FACT: oferta ma delivery.rock = {offer_id, active, mode}.
→ FACT: mode = BuyWithDelivery (można kupić) lub NotEligible (nie można).

## HIERARCHIA PRAWDY

1. dane/*.json — przechwycone odpowiedzi API
2. SYNTEZA_GLOWNA.md — aktualna prawda
3. recon/14_raport_autobuy_checkout.md — raport dowodowy
4. recon/0x_*.md — oryginalne raporty
5. koncepcje niezweryfikowane — hipotezy

## PROTOKÓŁ DZIAŁANIA AGENTA

1. Sprawdź MENTAL_MAP (ten plik) — znajdź trigger.
2. Zweryfikuj w dane/*.json — czy jest twardy dowód.
3. Oznacz pewność tagiem [UDOWODNIONE]/[HIPOTEZA].
4. Zapisz nowe odkrycie w dane/ i zaktualizuj SYNTEZA_GLOWNA.md.

## ALERTY

- CHECKOUT: NIEZBADANY — nie twierdź, że działa.
- SESJA: TTL ~15 min — planuj testy natychmiast po uzyskaniu cookies.
- KONCEPCJA 08: endpointy błędne — nie używaj jako prawdy.

## QUICK REFERENCE

- Detektor: bot/detector.py (działa)
- HTTP: curl_cffi chrome124 (omija 403)
- Sesja: dane/cookies.txt + recon/probe_session_live.py
- Dostawa: dane/oferty_z_dostawa.json (delivery.rock)
- Checkout: NIEZBADANY (recon/capture_checkout_live.py czeka na sesję)