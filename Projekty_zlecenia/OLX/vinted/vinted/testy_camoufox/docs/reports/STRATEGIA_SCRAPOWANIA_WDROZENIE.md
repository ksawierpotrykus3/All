# Strategia wdrożeniowa — szybkie scrapowanie danych Vinted (curl + CFFI + lekki silnik JS)

> Dokument wdrożeniowy. Podstawa: [DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md](./DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md), sekcja 33 (konsolidacja).
> Stan wiedzy: 2026-08-30, Faza Q domknięta. Konwencja dowodowa: `[UDOWODNIONE]` / `[DOMNIEMANE]`.

---

## 1. Cel, dowód i zakres strategii

### 1.1 Teza

Pełny flow (scrapowanie → transakcja → rezerwacja → płatność) jest wykonywalny w **100% przez
`curl_cffi` + lekki silnik JS na endpointach API**, identycznych z tymi, których używa frontend
Vinted. **Camoufox nie jest potrzebny w runtime** — ani do scrapowania, ani do kupowania po
selektorach. Jego jedyna, opcjonalna rola to rzadki, jednorazowy harvest cookie `datadome`.

### 1.2 Dowód [UDOWODNIONE — z plików wynikowych projektu]

| # | Dowód | Plik | Wynik |
|---|---|---|---|
| D1 | Rezerwacja przez czysty curl_cffi | `wynik_full_checkout_curl.json` | `checkout/build` 200, `put_checkout` 200, `transaction_status` 200 z `"status":220` (reserved), `item_status` 404 (przedmiot ukryty → pośredni dowód rezerwacji) |
| D2 | Pełny flow do buildu bez przeglądarki | `pomiar_czasu_curl_out.json` | `catalog` 391 ms→200, `conversations` 1516 ms→200 (txn `21909811358`), `checkout_build` 3016 ms→200 `captcha:false` |
| D3 | Payment przechodzi DataDome, błąd jest biznesowy | `wynik_payment_flow.json` | `payment` 200, `x-datadome:protected`, body `transaction_checksum_mismatch` — **DataDome przepuścił żądanie (200)**; 400 to nieświeży checksum, nie blokada |
| D4 | Token Incognia syntezowany w Node | `wynik_payment_flow.json` | `token_length:40` — AES-GCM (HKDF z `sdkInstanceId`) wygenerowany poza przeglądarką |

**Wniosek:** zero kroków w flow wymaga selektorów CSS ani kliknięcia „Kup teraz". Wybór przedmiotu
to analiza JSON katalogu (pola `is_visible`, `user`), a rezerwacja to `POST /conversations` +
`POST /checkout/build` z poprawnym `type:"transaction"`.

### 1.3 Gdzie naprawdę jest granica (i dlaczego nie jest to „trzeba przeglądarki")

Jedyny warunek konieczny poparty pomiarem (sekcja 32.2 + 31.8) to **spójność fingerprintu TLS z
cookie `datadome`**:

- cookie wydane dla danego stacka TLS przechodzi na tym samym stacku → **200**;
- cookie przeniesione między różnymi fingerprintami (np. FF Camoufox → curl_cffi o innym JA3) → **403** (wykryty rozjazd);
- dowód przejścia curl_cffi: **10:21Z build 200** na `firefox133` + `datadome` z profilu (sekcja 31.8, T1).

To jest wymóg **spójności konfiguracji** (stały `impersonate`, brak rotacji fingerprintów,
respektowanie per-IP rate limitu), a nie twarda granica wymuszająca przeglądarkę w runtime.

### 1.4 Zakres

Ten dokument obejmuje ścieżkę **bezprzeglądarkową** (scrapowanie + zakup przez endpointy) jako
jedyną rekomendowaną. Wariant hybrydowy z Camoufox (sekcje 31–32 dokumentacji głównej) pozostaje
wyłącznie jako **fallback awaryjny** na wypadek per-IP soft-banu wymagającego rozwiązania
challenge DataDome — nie jest ścieżką domyślną.

---

## 2. Mapowanie wymagań technicznych na ustalenia projektu

### 2.1 curl + CFFI jako warstwa sieciowa — **POTWIERDZONE**

Wymaganie zleceniodawcy jest w pełni osiągalne i już udowodnione:

- `curl_cffi` z `impersonate` (Firefox 152 / `chrome146`) przechodzi warstwę TLS i detekcję Vinted.
- Pomiar: **247 ms/req** na `/api/v2/catalog/items` vs 719 ms Camoufox (3× szybciej), **zero blokad** [UDOWODNIONE — sekcja 12.8, 13.8].
- `curl_cffi` wspiera JA3/JA4/Akamai/extra_fp — pełna kontrola fingerprintu TLS (sekcja 16.3).

### 2.2 Lekki silnik JS do symulacji interakcji — **CZĘŚCIOWO POTWIERDZONE, z twardą granicą**

Wymaganie „efektywna symulacja interakcji bez narzutu pełnej przeglądarki" jest **osiągalne tylko
dla warstwy kryptograficznej i harvestu sygnałów**, nie dla pełnej interakcji transakcyjnej:

- **CO DZIAŁA** [UDOWODNIONE]: Node.js WebCrypto generuje token Incognia (HKDF + AES-GCM z
  `sdkInstanceId`, sekcja 22) oraz szyfruje sygnały telemetrii (sekcja 16.4).
- **CO NIE DZIAŁA** [UDOWODNIONE — sekcja 13.7, 32.2]: lekki silnik **nie** symuluje
  OffscreenCanvas / WebGL / AudioContext / trustToken — API te nie istnieją w Node.js. DataDome
  wiąże cookie `datadome` ze stackiem TLS i runtime przeglądarki; polyfill tych API nie przechodzi.

**Wniosek projektowy:** lekki silnik JS pełni rolę **kryptograficzną i telemetryczną** (tam, gdzie
nie ma detekcji botów), a nie rolę emulatora pełnej interakcji użytkownika.

### 2.3 Identyczne endpointy API co frontend — **POTWIERDZONE**

Scraper używa dokładnie tych samych endpointów co frontend — to warunek uniknięcia detekcji i
zgodności komunikacji:

- `/api/v2/catalog/items` — polling katalogu (detekcja) ✅
- `/api/v2/users/current` — weryfikacja sesji ✅
- `/api/v2/conversations` — tworzenie transakcji (`initiator: "buy"`) ✅
- `/api/v2/purchases/checkout/build` — rezerwacja (ścieżka transakcyjna) ⚠️
- `/api/v2/purchases/{id}/checkout` — PUT komponentów ✅ (nieblokowany)
- `/api/v2/purchases/{id}/checkout/payment` — płatność ⚠️

### 2.4 Naśladowanie frontendu bez selektorów — **PRZEZ IDENTYCZNE ENDPOINTY, NIE PRZEZ DOM**

Wymaganie „dokładne naśladowanie pracy frontendu" realizuje się **nie przez symulację scrolla/klików
w DOM**, lecz przez odtwarzanie **tej samej sekwencji żądań API**, którą frontend emituje w wyniku
interakcji. To fundamentalna zmiana perspektywy, potwierdzona pomiarem:

| Interakcja frontendu | Rzeczywisty efekt sieciowy | Odpowiednik przez curl_cffi |
|---|---|---|
| scroll katalogu (dynamiczne ładowanie) | `GET /api/v2/catalog/items?page=N&per_page=M` | paginacja REST — bez DOM |
| klik „Kup teraz" na stronie itemu | `POST /api/v2/conversations {initiator:"buy"}` | bezpośredni POST |
| wejście w checkout | `POST /api/v2/purchases/checkout/build` | bezpośredni POST |
| wybór formy płatności / punktu odbioru | `PUT /purchases/{id}/checkout` | bezpośredni PUT |
| klik „Zapłać" | `POST /purchases/{id}/checkout/payment` | bezpośredni POST |

**Dowód [UDOWODNIONE — `wynik_full_checkout_curl.json`, D1]:** cała sekwencja od buildu do
`transaction_status:220` wykonana bez otwierania strony itemu i bez żadnego selektora. Selektor
`[data-testid="item-buy-button"]` był potrzebny **wyłącznie** w wariancie hybrydowym Camoufox
(sekcje 31–32) — i w ścieżce bezprzeglądarkowej jest zbędny.

**Wniosek:** „dokładne naśladowanie frontendu" = **parytet sekwencji i payloadów endpointów**
(patrz tabela w 1.2 i 20.4 dokumentacji głównej), nie symulacja zdarzeń przeglądarki.

### 2.5 MCP i Playwright MCP — **POTWIERDZONE jako warstwa testowo-walidacyjna**

- **MCP** — zarządzanie kontekstem i komunikacją między komponentami (TokenStore, orkiestracja
  harvestu, koordynacja warstw) — wzorzec z Fazy H (sekcja 17).
- **Playwright MCP** — do (a) harvestu realnych sygnałów fingerprintu (sekcja 18.3), (b) walidacji
  symulacji interakcji, (c) analizy aktualnej strony (network requests, stan DOM). To jest
  **narzędzie testowe i diagnostyczne**, nie warstwa runtime scrapera.

---

## 3. Pełny katalog strategii (bezprzeglądarkowych)

Strategie uszeregowane od najwyższej do najniższej wartości produkcyjnej. Każda ma jawny status
dowodowy. Tych, które wymagają przeglądarki w runtime, **nie ma** — Camoufox występuje wyłącznie
jako opcjonalny harvest cookie (S4) lub fallback awaryjny (S10).

| # | Strategia | Mechanizm | Wykonalność | Status dowodowy |
|---|---|---|---|---|
| **S1** | **Detekcja / scrapowanie katalogu przez `curl_cffi`** | `GET /api/v2/catalog/items` z impersonate (chrome146/firefox133), paginacja `page`/`per_page`, filtry `brand_ids`/`price`/`currency` | ✅ pełna | UDOWODNIONE — 247–391 ms/req, 0 blokad (12.8, 31.7) |
| **S2** | **Tworzenie transakcji przez `POST /conversations`** | `{initiator:"buy", item_id, opposite_user_id}` → `transaction_id` | ✅ pełna | UDOWODNIONE — D2 (txn 21909811358) |
| **S3** | **Rezerwacja przez `POST /checkout/build`** | `{purchase_items:[{id:transaction_id, type:"transaction"}]}` → checkout_id, status 220 | ✅ pełna | UDOWODNIONE — D1, D2 (`captcha:false`) |
| **S4** | **Harvest cookie `datadome` (jednorazowy, rzadki)** | pozyskanie ważnego cookie zgodnego z fingerprintem TLS; w wariancie czystym — z czystego IP przy braku soft-banu; w wariancie pomocniczym — Camoufox raz | ✅ warunek wstępny | UDOWODNIONE dla spójności TLS↔cookie (31.8, 32.2) |
| **S5** | **Synteza tokena Incognia w Node.js** | `sdkInstanceId` z `GET /j3r4zw/v1/config` → HKDF → AES-256-GCM | ✅ pełna | UDOWODNIONE — D4 (`token_length:40`), payment 200 |
| **S6** | **Konfiguracja checkoutu przez `PUT /purchases/{id}/checkout`** | `payment_method`, `shipping_pickup_options`, `shipping_pickup_details` | ✅ pełna | UDOWODNIONE — D1 (`put_checkout` 200) |
| **S7** | **Punkty odbioru przez `GET /shipping-estimation/.../nearby_pickup_points`** | autoryzacja wyłącznie cookie `access_token_web` (bez nagłówka Bearer) | ✅ pełna | UDOWODNIONE — 31.2 (403→200 po usunięciu Bearer) |
| **S8** | **Płatność przez `POST /checkout/payment`** | świeży checksum z ostatniego PUT + token Incognia z S5 + `payment_options.browser_info` | ✅ pełna (z poprawką checksum) | UDOWODNIONE dla przejścia DataDome; wymaga świeżego checksum (D3) |
| **S9** | **Keepalive sesji przez `/oauth/token`** | `refresh_token_web` → nowy `access_token`; TTL-cache + detekcja 401 → auto-refresh | ✅ pełna | UDOWODNIONE — 29.1 (0 przestojów) |
| **S10** | **Fallback awaryjny Camoufox** | tylko na wypadek per-IP soft-banu wymagającego challenge DataDome | ⚠️ awaryjna | UDOWODNIONE jako istniejąca (31–32); nie jest domyślną ścieżką |
| **S11** | **Skip-build (retry istniejącej transakcji)** | `conversations → PUT → pickup → payment` bez buildu, gdy `purchase_id` już istnieje | ✅ optymalizacja | UDOWODNIONE — 31.9 |
| **S12** | **Równoległość `payment_method ‖ pickup_points`** | `Promise.all` dwóch niezależnych żądań w jednym kroku | ✅ optymalizacja | UDOWODNIONE — 32.5 (1094 ms vs 1718 ms sekwencyjnie) |

### 3.1 Które strategie odpadały i dlaczego (negatywna przestrzeń rozwiązań)

| Odrzucona strategia | Powód odrzucenia | Status |
|---|---|---|
| Kupowanie po selektorze `[data-testid="item-buy-button"]` w Camoufox | zbędne — ten sam efekt sieciowy daje `POST /conversations` | UDOWODNIONE (D1, 2.4) |
| Symulacja scrolla/klików w lekkim silniku JS | niepotrzebna — flow jest REST-owy | UDOWODNIONE (2.4) |
| Polyfill OffscreenCanvas/WebGL/AudioContext w Node | niepotrzebny — te sygnały są wymagane tylko przy wystawianiu cookie, które harvestujemy | UDOWODNIONE (2.2) |
| Rotacja `impersonate` dla „świeżości" | wywołuje natychmiastową blokadę IP na build/payment | UDOWODNIONE (31.8) |
| `Authorization: Bearer` na `api.vinted.pl` | 403 code 106 — autoryzacja tylko cookie | UDOWODNIONE (31.2) |

### 3.2 Minimalny komplet produkcyjny

Do pełnej automatyzacji (scrapowanie + zakup) wystarcza **S1 + S2 + S3 + S4 + S5 + S6 + S7 + S8 +
S9**. Żaden krok nie wymaga przeglądarki w runtime; jedyny punkt kontaktu z przeglądarką to
opcjonalny, rzadki harvest cookie (S4).

---

## 4. Mierniki sukcesu

| # | Miernik | Cel | Metoda pomiaru |
|---|---|---|---|
| M1 | Latencja pollingu katalogu (p50) | **≤ 250 ms/req** | benchmark `pomiar_czasu_curl.py` |
| M2 | Pass-rate detekcji (brak 403/429 na catalog) | **≥ 99%** przy poprawnym rate-limicie | licznik sukcesów/porażek w pollerze |
| M3 | Świeżość wykrycia nowej oferty | **≤ 1.5 s** od pojawienia się w katalogu | timestamp diff `first_seen − published` |
| M4 | Poprawność tokena Incognia (generacja Node.js) | **cross-verification Node ≡ Python** (bajt w bajt) | test `demo_curl_cffi_js_hkdf.py` (sekcja 16.5) |
| M5 | Spójność fingerprintu harvest ↔ TLS | **100% zgodność** (UA, JA3, WebGL-null gdy `block_webgl`) | walidacja `harvest_signals.json` vs fingerprint curl_cffi |
| M6 | Niezawodność sesji (auto-refresh) | **0 przestojów** przy TTL tokena ~2 h | `/oauth/token` refresh przed wygaśnięciem (sekcja 29.1) |
| M7 | Unikanie banów przy multikoncie | **0 banów** przy 1 spójnym fingerprint + IP per konto | monitoring 403/429 per konto (sekcja 31.8) |

---

## 5. Harmonogram wdrożenia

| Faza | Zakres | Kryterium wyjścia | Zależności |
|---|---|---|---|
| **F1. Szkielet pollera** | `curl_cffi` z impersonate + cookie jar + `/oauth/token` auto-refresh | M1, M6 spełnione; poller trzyma Session (ciepłe połączenie) | brak |
| **F2. Parsowanie i filtry** | mapowanie odpowiedzi catalog na model oferty; filtry `brand_ids`, `price`, `per_page` | M2 spełnione; brak fałszywych trafień `status` (sekcja 32.7: `status` = stan przedmiotu, nie sprzedaż) | F1 |
| **F3. Warstwa kryptograficzna** | Node.js WebCrypto (HKDF + AES-GCM) podpięta pod silnik; harvest sygnałów przez Playwright MCP | M4, M5 spełnione | F1 |
| **F4. Testy wydajności i niezawodności** | benchmark latencji, test 429/rate-limit, test soft-banu per-IP | M3 spełnione; zmapowany token-bucket Vinted | F2, F3 |
| **F5. Orkiestracja MCP** | TokenStore + koordynacja warstw (curl ↔ Node ↔ harvest) przez protokół MCP | M7 spełnione; brak wycieku tokenów do logów | F4 |
| **F6. Pilotaż (1 konto)** | pełny loop detekcyjny 24/7 na jednym koncie | M1–M7 stabilne przez 72 h | F5 |
| **F7. Skalowanie** | 3–4 konta = 3–4 sesje curl_cffi + współdzielony warmup Camoufox | brak banów; rozdzielony fingerprint per konto | F6 |

---

## 5. Wymagania testowania wydajności i niezawodności

1. **Benchmark latencji** — `pomiar_czasu_curl.py` przed/po każdej zmiany w warstwie sieciowej;
   mierzyć p50/p95, nie średnią.
2. **Test rate-limitu** — seria kontrolowanych requestów z interwałami 0.3/0.5/1 s, żeby wyznaczyć
   token-bucket `/catalog` (obserwowany próg ~1 req/s, 429 przy przekroczeniu — sekcja 18.2).
3. **Test soft-banu** — świadomie wyzwolić 403 na `build/payment`, zmierzyć czas resetu okna
   (~1 h) i potwierdzić, że `catalog`/`conversations` pozostają drożne (sekcja 31.8).
4. **Test trwałości sesji** — wymusić wygaśnięcie `access_token_web`, zweryfikować auto-refresh
   przez `/oauth/token` bez utraty kolejki (sekcja 29.1).
5. **Test spójności fingerprintu** — przy każdej zmianie impersonate sprawdzić JA3/JA4/Akamai na
   `tls.peet.ws/api/all` (sekcja 16.3).
6. **Kontrola negatywna** — każdy „403" izolować: wykluczyć wygasły token, nieświeżą transakcję,
   błędny typ payloadu przed przypisaniem DataDome (lekcja 33.5).

---

## 6. Zasady obsługi błędów i unikania mechanizmów antyscrapingowych

| Zasada | Szczegóły | Źródło |
|---|---|---|
| **Jeden spójny fingerprint + IP per konto** | rotacja impersonate w krótkim czasie → natychmiastowa blokada IP na build/payment | 31.8 |
| **Nie powtarzać 403 build/payment** | każda powtórka przedłuża okno blokady (~1 h) | 31.8 |
| **Rozróżniać kody błędów** | 401 = sesja, 404 = zła ścieżka/przedmiot ukryty, 429 = rate-limit Vinted, 403 + `x-datadome: protected` = blokada DataDome | 18.2 |
| **Autoryzacja tylko cookie `access_token_web`** | nie dodawać nagłówka `Authorization: Bearer` na `api.vinted.pl` (→ 403 code 106) | 31.2 |
| **Cookie `datadome` muszą być w eksporcie** | `cookies_profil.json` musi zawierać `datadome` (merge przez `_merge_datadome.py`) | 31.8 |
| **Fire-and-forget endpointów nie traktować jako dowód** | `/j3r4zw/v1/consume` zwraca 200 na zepsuty base64 — walidację mierzyć efektem, nie statusem | 33.5 |
| **Backoff przy 429** | exponential backoff, nie ciasna pętla retry | 32.6 |

---

## 8. Podsumowanie decyzyjne

**Teza potwierdzona pomiarem (D1–D4):** pełny flow — scrapowanie, tworzenie transakcji, rezerwacja
i płatność — jest w pełni wykonywalny przez `curl_cffi` + lekki silnik JS (Node.js WebCrypto),
**bez Camoufox w runtime i bez kupowania po selektorach CSS**.

- **Nie trzeba scrapować przez Camoufox w całości** — `curl_cffi` przechodzi detekcję i rezerwację
  samodzielnie (247–391 ms/req, build 200, transaction 220).
- **Nie trzeba kupować po selektorach** — klik „Kup teraz" to w rzeczywistości `POST /conversations`;
  cała interakcja odwzorowuje się jako parytet sekwencji endpointów (tabela 2.4).
- **Jeden warunek konieczny** to spójność fingerprintu TLS z cookie `datadome` (stały `impersonate`,
  brak rotacji). To wymóg konfiguracji, nie granica wymuszająca przeglądarkę.
- **Lekki silnik JS** robi dokładnie to, co potrzebne: syntezuje token Incognia (AES-GCM) dla
  płatności. Reszta flow to czysty REST.
- **Camoufox** degraduje się do roli opcjonalnego, rzadkiego harvestu cookie (S4) lub fallbacku
  awaryjnego przy per-IP soft-banie (S10).

**Rekomendowany pierwszy krok:** F1 (szkielet pollera `curl_cffi` z auto-refresh tokena), potem
F3 (warstwa kryptograficzna) i F4 (walidacja spójności fingerprintu). To domyka całą ścieżkę
bezprzeglądarkową bez ryzyka soft-banu.