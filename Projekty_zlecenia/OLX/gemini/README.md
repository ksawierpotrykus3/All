# Repozytorium Badań i Dokumentacji: GEMINI

> Zasada naczelna: Pesymistyczna inżynieria dowodowa.
> Dopóki nie ma deterministycznego dowodu w postaci surowego JSON/kodu statusu HTTP — informacja jest traktowana jako [NIEPOTWIERDZONE] lub [HIPOTEZA].

## Struktura folderu

- `gemini/README.md` — niniejszy indeks i mapa wiedzy
- `gemini/KOMPENDIUM_OLX.md` — centralny, nadrzędny dokument łączący całą wiedzę od A do Z
- `gemini/raporty/` — raporty inżynierskie z badań i testów
  - `00_SYNTEZA_STARTOWA.md` — stan wiedzy startowej i obalonych mitów
  - `01_DOWOD_WYGASANIA_I_SESJI.md` — empiryczny dowód wygasania tokena JWT (TTL 15 min / 401)
  - `02_ARCHITEKTURA_VINTED_DLA_OLX.md` — wdrożenie architektury trwałego profilu wzorowanej na projekcie Vinted (`persistent_context`)
  - `03_ODKRYCIE_PRAWDZIWEGO_API_CHECKOUT.md` — Odkrycie i empiryczne potwierdzenie produkcyjnego API `pl.ps.prd.eu.olx.org` oraz maszyny stanów zamówienia
- `gemini/skrypty/` — powtarzalne, deterministyczne narzędzia testowe
  - `login_headed.py` — jednorazowe logowanie z trwałym profilem
  - `test_session_refresh.py` — headless auto-refresh i test API `/users/me/`
  - `test_purchase_order_pure_api.py` — test czystego API curl_cffi bez przeglądarki (`POST purchase-order` -> 201)
  - `probe_checkout.py` — badanie flow na checkout/
  - `probe_buy_options.py` — badanie bramki `/buy-options/{adId}`
  - `probe_buy_next_step.py` — symulacja przejścia do formularza dostawy i przechwycenie ruchu API
- `gemini/dane/` — przechwycone surowe odpowiedzi API, logi sieciowe i zrzuty ekranu stanowiące źródło prawdy

## Kluczowe Fakty [UDOWODNIONE]
1. `POST https://pl.ps.prd.eu.olx.org/order/v1/purchase-order` z `{"adId": ID}` i Bearer tokenem tworzy zamówienie w stanie `Draft` i zwraca kod `201 Created` (potwierdzone w `gemini/dane/purchase_order_api_proof.json`).
2. Stan `Draft` **NIE blokuje jeszcze oferty** przed innymi (`delivery.rock.active` nadal = `True`). Blokada zapada na dalszym etapie.
3. Trwały profil przeglądarki (`profiles/olx_profile`) omija konieczność ponownego logowania i rozwiązuje problem wygasania tokena (TTL 15 min) oraz wyzwań slider puzzle (DataDome / AWS WAF).
