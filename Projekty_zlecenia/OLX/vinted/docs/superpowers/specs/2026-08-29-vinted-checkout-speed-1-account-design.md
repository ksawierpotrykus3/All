# Design: pomiar i przebicie kopsa na 1 koncie (rezerwacja < 3 s, detekcja < 200 ms)

Data: 2026-08-29
Status: zaakceptowany kierunkowo — do przeglądu przed planem implementacji

## 1. Cel i zakres

Domknąć pierwotne ustalenie zlecenia („najpierw zmierz, potem obiecuj") na **jednym koncie**:
zmierzyć realną przewagę bota nad kops.gg i uzyskać mierzalne progi wydajności, zanim
podejmie się decyzję o multikoncie/proxy/WebUI.

**Poza zakresem (celowo):** multikonto 3–4 konta, proxy rezydencjalne, Web UI, kategoria (SSR),
płatność/3DS. Te elementy wracają dopiero po spełnieniu progów na 1 koncie.

## 2. Kluczowe decyzje (zatwierdzone z użytkownikiem)

1. **Cel:** przebić kopsa na 1 koncie.
2. **Próg agresywny:**
   - rezerwacja end-to-end p50 < 3 s,
   - detekcja wewnętrzna p95 < 200 ms.
3. **Checkout < 3 s dotyczy REZERWACJI** (detekcja → `purchase_id`), NIE płatności.
   Powód: brak karty bez 3DS; płatność (BLIK/3DS) to osobny, wolniejszy krok po zabezpieczeniu
   przedmiotu. Wyścig z innymi botami wygrywa się w kroku rezerwacji.
4. **Kolejność działań:** najpierw Faza C (czyste API), a przy braku wyniku w timeboxie 2–3 dni
   roboczych — automatyczna Faza A (pre-warmowana sesja). Kryterium wycofania jest twarde.
5. **Definicja detekcji (korekta wymuszona fizyką Vinted):**
   - **latencja wewnętrzna** (mierzalna, cel < 200 ms): od sparsowania odpowiedzi do callbacku,
   - **czas od wystawienia oferty** (limit fizyczny ~1 s): ≤ 1 interwał pollingu; nieprzekraczalny
     ze względu na twardy rate-limit Vinted ~1 req/s (zmierzony: 429 po 6. żądaniu w 5,9 s).

## 3. Architektura

Rozszerzamy istniejący `bot/src/vintedbot/`, nie tworzymy nowego projektu.

| Moduł | Rola | Zależności |
|---|---|---|
| `measurement.py` (NOWY) | repozytorium pomiarowe: timestampy, percentyle, raport JSON | — (czyste) |
| `detection.py` | monitoring + benchmark detekcji | models, measurement |
| `checkout.py` | dwie ścieżki rezerwacji: `api` (Faza C) i `browser` (Faza A) | models, measurement, camoufox |
| `cli.py` | orkiestracja + flagi wyboru ścieżki | detection, checkout, measurement |
| `models.py` | rozszerzenie `Filtry` (size/status/price — już w modelu, brak w CLI) | — |

Granice: `measurement` nie wie nic o Vinted; `detection` i `checkout` tylko emitują zdarzenia;
`cli` spina. Każdą warstwę testuje się niezależnie.

## 4. Faza 0 — framework pomiarowy (fundament)

Wykonywany najpierw; bez tego C ani A nie da się zweryfikować.

- **Detekcja:** punkt startowy = pierwsze pojawienie się `id` oferty w odpowiedzi
  `order=newest_first`. Pomiar = `t(callback) − t(pierwsze pojawienie id w API)`, rozbity na
  latencję wewnętrzną i czas od wystawienia (zgodnie z sekcją 2 pkt 5).
- **Rezerwacja:** `t(purchase_id przechwycony) − t(decyzja o zakupie)`.
- **Output:** raport JSON (nie `print`) zapisywany na dysk: p50/p95/p99, liczba prób, timestampy.

## 5. Faza C — spike czystego API (timebox 2–3 dni)

Cel: `POST /api/v2/purchases/checkout/build` przez `curl_cffi` (bez przeglądarki) zwraca
`200 + purchase_id`.

Do odtworzenia (źródło: [DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md](../../../vinted/testy_camoufox/DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md)):
- `X-CSRF-Token` (znany, hardcoded `75f6c9fa-...`),
- `x-anon-id`, `locale`, `priority`, `origin`, `referer` (znane z przechwycenia),
- **`x-incognia-request-token`** — JWE generowany dynamicznie z sensorów urządzenia
  (canvas, WebGL, audio), wiązany z sesją przeglądarki,
- ważne cookie `datadome` + sygnatura TLS/JA4.

**Bloker główny (znany z góry):** `curl_cffi` nie ma SDK Incognia, więc nie ma z czego
wygenerować tokenu JWE. Prawdopodobieństwo sukcesu C jest niskie — stąd twardy timebox.

**Kryterium wycofania (twarde):** po 2–3 dniach roboczych bez `200 + purchase_id` →
**automatyczne przejście na Fazę A**. Bez negocjacji.

## 6. Faza A — pre-warmowana sesja (fallback)

1. **Trwała, pre-warmowana sesja Camoufox** — jeden długożyjący kontekst na zalogowanej stronie,
   DataDome rozwiązany, SDK Incognia załadowane. Singelton już istnieje w `checkout.py`;
   rozszerzamy go o „trzymaj stronę ciepłą".
2. **Wyzwalacz zakupu bez pełnej nawigacji** — zamiast `goto(/items/{id})` (~34 s) wywołujemy
   `initiateSingleCheckout`/klik na już otwartej stronie.
3. **Fallback B (watchlist)** — dla wąskiego, znanego zbioru przedmiotów trzymamy
   pre-renderowane przyciski; uzupełnia A, nie zastępuje.

## 7. Obsługa edge case'ów

| # | Przypadek | Wykrycie | Reakcja | Mierzalność |
|---|---|---|---|---|
| E1 | Sesja wygasa (~2 h) | `users/current` brak `login` | auto-refresh; przy anonimowym refresh → alert + ręczne re-logowanie | licznik, alarm |
| E2 | 429 rate-limit | kod 429 | backoff wykładniczy + jitter; NIE szybszy retry | licznik backoffów |
| E3 | 403 DataDome (detekcja) | 403/`x-datadome` | rotacja ścieżki, alert | licznik 403 |
| E4 | 403 na checkout/build | 403 | przejście na ścieżkę A, alert | licznik |
| E5 | Captcha interstitial | redirect `geo.captcha-delivery.com` | wstrzymanie + alert człowieka | alarm |
| E6 | Ban konta | brak `login` + blokada | zatrzymanie operacji, alert | alarm krytyczny |
| E7 | Refresh token rotacja | `set-cookie` | obsłużona w `odswiez_token()` | log |
| E8 | Rotacja Incognia/CSRF | zmiana w bundlu | konfigurowalny `VINTED_CSRF_TOKEN` | log |
| E9 | WebGL/fingerprint | ostrzeżenie `block_webgl` | losowy preset WebGL (do rozwiązania) | log |
| E10 | Awaria przeglądarki | `ctx.close()` exception | restart kontekstu + odtworzenie sesji | licznik restartów |
| E11 | Przedmiot sprzedany | brak `item-buy-button` | przerwij, nie duplikuj | licznik |
| E12 | `purchase_id` nie przechwycony | timeout `response` | log; NIE duplikuj zakupu | alarm |
| E13 | Konkurencja szybsza | 404/zmiana statusu | pomiar straty, przejście dalej | metryka |
| E14 | Wiele ofert naraz (race) | >1 nowa oferta | kolejka priorytetowa, timeout per zakup | metryka |

## 8. Testowanie i weryfikacja

- **Unit** (`measurement`, modele, parser `purchase_id`, backoff): czyste, bez I/O.
- **E2E** przez `CliRunner`, mockując **wyłącznie** warstwę HTTP — pełny flow od monitoringu
  do decyzji.
- **Benchmark** (Faza 0): realny test wydajności detekcji i rezerwacji, wynik do JSON.
- **Kryterium sukcesu = liczby:** detekcja wewnętrzna p95 < 200 ms, rezerwacja p50 < 3 s,
  0% blokad DataDome w detekcji.

## 9. Wymóg aktualizacji dokumentacji inżynierskiej

Podczas każdego zadania aktualizowana jest właściwa dokumentacja inżynierska, zgodnie z jej
charakterem i przyjętym podziałem dowodowym:

- [DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md](../../../vinted/testy_camoufox/DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md) —
  warstwa zakupu/detekcji; każdy nowy pomiar dodaje wpis oznaczony `[UDOWODNIONE]` lub
  `[DOMNIEMANE]`.
- raporty pomiarowe (`vinted/raporty/`) — nowy raport per faza (C, A) z liczbami i dowodami.

Zasada: żadna liczba bez dowodu; żaden wniosek bez oznaczenia wiarygodności.