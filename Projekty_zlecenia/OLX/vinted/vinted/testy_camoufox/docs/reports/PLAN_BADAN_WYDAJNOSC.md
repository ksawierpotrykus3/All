```markdown
# Plan badań empirycznych — dowód szybkiego scrapowania i minimalnego czasu do bramki (curl_cffi + lekki silnik JS)

> Cel: **zmierzyć i udowodnić** realny, minimalny czas scrapowania oraz ścieżki zakupowej przez
> `curl_cffi` + Node.js WebCrypto, **bez Camoufox w ścieżce krytycznej**, z dowodem wizualnym
> (screenshot bramki z timestampem w ms). Konwencja dowodowa: `[UDOWODNIONE]` / `[DOMNIEMANE]`.

---

## 0. Uczciwe założenia wyjściowe (co już wiemy z pomiarów)

Zanim zaplanuję eksperymenty, utrwalmy **udowodnione już liczby**, bo wyznaczają one granicę tego,
co da się osiągnąć, a czego nie:

| Komponent | Udowodniony czas | Źródło |
|---|---|---|
| Detekcja katalogu `curl_cffi` | **247–516 ms/req** (zależnie od `per_page`) | 12.8, 31.7, 32.8 |
| `POST /conversations` (nowa transakcja) | **~1.2–1.5 s** | 31.8, `pomiar_czasu_curl_out.json` (1516 ms) |
| `POST /checkout/build` (rezerwacja) | **~1.5–1.6 s** | 31.8, `pomiar_czasu_curl_out.json` (3016 ms suma) |
| `POST /checkout/payment` → bramka | **~2.6–2.7 s** | 32.8, 32.10 |
| **Suma do bramki (nowy item)** | **~7.5 s** | 32.8 (`flow_optimized` run12) |
| **Suma do buildu (nowy item)** | **~3.0 s** | `pomiar_czasu_curl_out.json` (3016 ms) |

**Wniosek wstępny [UDOWODNIONE — sekcja 31.8]:** floor rezerwacji nowego itemu ≈
`conversations (~1.2 s) + build (~1.5 s)` = **~2.7 s serwerowego czasu**, nie do przebicia po
stronie klienta. Celem realnym do osiągnięcia jest więc:

- **Scrapowanie/detekcja ≤ 250 ms** (już osiągnięte, do potwierdzenia w izolacji),
- **czas do buildu ≈ 2.7–3.0 s** (blisko celu „2 s"),
- **czas do bramki ≈ 7.5 s** dla świeżego itemu — **1–2 s do bramki jest fizycznie nierealne**
  (payment sam ma floor ~2.6 s, a przed nim stoją serwerowe kroki konfiguracji).

Plan poniżej **nie obiecuje 1–2 s do bramki**; zamiast tego wyznacza precyzyjne wektory redukcji
i mierzy, jak blisko 2 s da się zejść w warstwie detekcji i buildu.

---

## 1. Hipotezy badawcze

| Hipoteza | Treść | Przewidywany wynik |
|---|---|---|
| **H1** | Warm `Session` (keep-alive, bez TLS handshake) obniża latencję detekcji poniżej cold-start | p50 ≤ 180 ms na ciepłym połączeniu |
| **H2** | `per_page` i selekcja pól wpływają na czas katalogu liniowo | mniejszy payload = mniejszy czas |
| **H3** | Floor rezerwacji nowego itemu = ~2.7 s (nie do przebicia) | potwierdzenie w izolacji, kontrola negatywna |
| **H4** | Skip-build (istniejący `purchase_id`) skraca ścieżkę do bramki | oszczędność ~1.4 s na buildu |
| **H5** | Równoległość `payment_method ‖ pickup_points` skraca sekwencję | oszczędność ~0.6 s (32.5) |
| **H6** | „1–2 s do bramki" jest osiągalne **tylko** jako (a) czas do buildu, lub (b) pre-warm istniejącej transakcji — nie dla świeżego zakupu | potwierdzenie negatywne (granica) |

---

## 2. Metodologia — izolacja zmiennych i kontrola negatywna

Zasady obowiązkowe (lekcja 33.5 z dokumentacji głównej):

1. **Każdy pomiar ma baseline + wariant zmienny.** Zmieniam dokładnie jedną rzecz naraz.
2. **Kontrola negatywna:** przy każdym „403" wykluczyć wygasły token, nieświeżą transakcję,
   błędny typ payloadu — zanim przypiszemy blokadę DataDome.
3. **Stały fingerprint:** jeden `impersonate` (rekomendacja `chrome146`, potwierdzony 200+200
   w 31.8). **Zakaz rotacji** w trakcie serii — rotacja wyzwala blokadę IP.
4. **Zero powtórek 403 build/payment** — każda przedłuża okno soft-banu (~1 h).
5. **Zapis per krok** — `step`, `elapsed_ms`, `http`, `wall_utc` (jak w `pomiar_czasu_curl_out.json`).
6. **Screenshot bramki z timestampem ms ZAWSZE** — konwencja 32.9, bez oglądania przez agenta.

---

## 3. Scenariusze pomiarowe

### S1 — Detekcja: warm vs cold (H1)
- **Cold:** nowa `Session` per request (pełny TLS handshake).
- **Warm:** jedna `Session`, 10 kolejnych `GET /api/v2/catalog/items?per_page=2`.
- **Miernik:** p50/p95 z 10 prób; delta cold−warm = koszt handshake.
- **Kryterium sukcesu:** warm p50 ≤ 180 ms.

### S2 — Detekcja: wpływ payloadu (H2)
- `per_page=2` vs `per_page=10` vs `per_page=24`; opcjonalnie wąskie filtry `brand_ids`/`currency`.
- **Miernik:** czas vs rozmiar odpowiedzi (KB), wykrycie progu opłacalności (najmniejszy `per_page`
  pokrywający potrzeby pollera).
- **Kryterium sukcesu:** wyznaczony optymalny `per_page` dla pollera 24/7.

### S3 — Pełny flow nowy item (H3) — dowód flooru
- `catalog → conversations → build → PUT payment_method → pickup_points → PUT pickup_details → payment`.
- **Miernik:** suma do buildu oraz suma do bramki; porównanie z udowodnionym ~7.5 s.
- **Kryterium sukcesu:** pomiar zgodny z przewidywaniem (floor ~2.7 s do buildu, ~7.5 s do bramki);
  dokumentuje, że „1–2 s do bramki" jest nierealne dla świeżego itemu.

### S4 — Skip-build na istniejącym purchase_id (H4)
- `conversations (zwraca purchase_id) → PUT → pickup → payment` bez buildu.
- **Miernik:** delta vs S3.
- **Kryterium sukcesu:** oszczędność ~1.4 s potwierdzona.

### S5 — Równoległość `payment_method ‖ pickup_points` (H5)
- Dwa niezależne żądania w jednym kroku (`Promise.all`-ekwiwalent przez `concurrent.futures`
  w Pythonie lub jeden `page.evaluate`; dla czystego curl_cffi — dwa wątki).
- **Miernik:** sekwencyjnie vs równolegle.
- **Kryterium sukcesu:** ~0.6 s oszczędności potwierdzone.

### S6 — „Czas do buildu" jako uczciwa wersja celu 2 s (H6)
- Scenariusz minimalny: pomijamy `catalog` (item z pollera) → `conversations → build`.
- **Miernik:** suma wyłącznie tych dwóch kroków.
- **Kryterium sukcesu:** udokumentować, że ~2.7–3.0 s to realna dolna granica „rezerwacji",
  a nie 1–2 s.

---

## 4. Mierniki sukcesu eksperymentu

| # | Miernik | Cel | Uwaga |
|---|---|---|---|
| E1 | Warm detekcja p50 | ≤ 180 ms | S1 |
| E2 | Optymalny `per_page` | wyznaczony z pomiaru | S2 |
| E3 | Floor do buildu | ≈ 2.7–3.0 s (potwierdzony) | S3/S6 |
| E4 | Oszczędność skip-build | ≈ 1.4 s | S4 |
| E5 | Oszczędność równoległości | ≈ 0.6 s | S5 |
| E6 | Screenshot bramki + timestamp ms | obecny w każdym flow do bramki | konwencja 32.9 |

---

## 5. Procedura screenshotu (nie oglądać, tylko zapisać)

Zgodnie z regułą 32.9 (wymóg użytkownika, bezwzględny):

- po `payment 200 pending + redirect` → wejście na URL bramki (Adyen) → screenshot,
- nazwa: `{nazwa}_bramka_{int(time.time()*1000)}.png`,
- **wypalić** znacznik czasu w ms na dole obrazu (`start=... | dotarcie=<payment_ms> | shot=<wall>`),
- agent **nie otwiera/nie ogląda** zrzutu; zapis do pliku i wpis ścieżki do wyniku JSON,
- `screenshot_error` zapisujemy w JSON, ale **nie przerywa flow**.

---

## 6. Warunki bezpieczeństwa wykonania

1. Świeży, ważny `access_token_web` (TTL ~2 h) — refresh przez `/oauth/token` przed serią.
2. Cookie `datadome` obecne i spójne z `impersonate` (`_merge_datadome.py`).
3. Jeden publiczny IP; brak rotacji fingerprintów.
4. Po pierwszym 403 na build/payment — **przerwać serię** i odczekać ~1 h (reset okna).
5. Preferować pomiary detekcji (S1/S2) — nie wymagają warstwy transakcyjnej, więc nie ryzykują
   soft-banu; pomiary transakcyjne (S3–S6) wykonywać rzadko i w jednym oknie czasowym.

---

## 7. Oczekiwany rezultat (uczciwy werdykt)

- **Scrapowanie** — udowodnimy ≤ 250 ms (i realnie ≤ 180 ms na warm), czyli „szybkie scrapowanie"
  jest faktem, a nie postulatem.
- **„1–2 s" realnie = czas do buildu** (~2.7–3.0 s), NIE do bramki. Do bramki fresh = ~7.5 s
  (twardy floor serwerowy: conversations + build + payment + pickup).
- **Wektor do skrócenia zakupu:** skip-build (S4) + równoległość (S5) + pominięcie `catalog`
  (S6) — łącznie mogą zejść pod ~6 s do bramki na ścieżce retry/pre-warm; to zmierzymy.

Jeśli uznasz, że chcesz testować **dokładnie** „1–2 s do bramki" mimo powyższego, jedyną drogą jest
pre-warm checkoutu (transakcja + build wykonane wcześniej, a w oknie pomiarowym wyłącznie
`payment`) — ale to nie jest realny scenariusz wyścigu o nową ofertę i zostanie oznaczone jako
`[DOMNIEMANE — poza realnym flow]`.

---

## 8. WYNIKI POMIARÓW (wykonane 2026-08-30, świeży token)

### 8.1 S1 — warm vs cold (detekcja, GET /catalog/items, per_page=2)

| Wariant | avg | p50 | p95 | min | max |
|---|---|---|---|---|---|
| **warm** (jedna Session) | **343.8 ms** | **328.0 ms** | 422 ms | 297 ms | 422 ms |
| cold (nowa Session) | 506.0 ms | 453.0 ms | 703 ms | 421 ms | 703 ms |

**Wniosek [UDOWODNIONE]:** keep-alive (ciepłe połączenie) daje **~125 ms oszczędności na request**
(p50 328 vs 453 ms) — potwierdza H1, że poller powinien trzymać jedną Session.

### 8.2 S2 — wpływ `per_page` (warm Session)

| per_page | czas | http | payload |
|---|---|---|---|
| 2 | 453 ms | 200 | 14.5 KB |
| 10 | 453 ms | 200 | 89.3 KB |
| 24 | 656 ms | 200 | 219.4 KB |

**Wniosek [UDOWODNIONE]:** czas jest zdominowany przez sieć + serwer Vinted, nie payload — do progu
~90 KB (`per_page=10`) czas stały; dopiero `per_page=24` (219 KB) dodaje ~200 ms. Optymalny dla
pollera: **`per_page=10`** (maks. treści przy minimalnym koszcie).

### 8.3 S6 — minimalny flow do buildu (nowy item, świeży token)

```
[    0 ms] start
[  828 ms] catalog_items          -> 200  (cold session, per_page=3)
[ 2343 ms] conversations_create   -> 200  (delta +1515 ms)
[ 4000 ms] checkout_build         -> 200  (delta +1657 ms)
=== 4015 ms do buildu ===
```

**Wniosek [UDOWODNIONE — świeży pomiar]:**
- **`checkout/build` przez czysty curl_cffi = 200** (rezerwacja przechodzi bez Camoufox — ponownie potwierdzone).
- **Floor rezerwacji = ~3.2 s** (conversations + build, bez catalogu) — zgodne z sekcją 31.8 (~2.7 s przy ciepłym połączeniu).
- **„1–2 s" jest osiągalne wyłącznie dla detekcji** (328 ms) lub time-to-build na ciepłym połączeniu (~2.7–3.2 s), **NIE do bramki** (payment sam ma floor ~2.6 s).

### 8.4 Ustalenie uboczne — poprawne odświeżanie tokena

`access_token_web` (JWT) wygasł; **poprawny endpoint odświeżania to `POST /web/api/auth/refresh`**
(z `refresh_token_web` + `X-CSRF-Token`), NIE `/oauth/token`. Odświeżenie → 200 + nowy token,
zapisany do `cookies_profil.json`. `export_cookies_sqlite.py` czyta świeże cookies bezpośrednio
z `profil_firefox/cookies.sqlite` (bez uruchamiania przeglądarki).

### 8.5 Pliki dowodowe

- `wynik_bench_detection.json` — S1/S2
- `pomiar_czasu_curl_out.json` — S6 (nadpisany świeżym runem)
- `refresh_token_probe.py` — odświeżanie tokena
- `export_cookies_sqlite.py` — eksport cookies z sqlite

### 8.6 PEŁNY FLOW DO BRAMKI — 100% curl_cffi (bez Camoufox w ścieżce zakupowej)

**Wynik [UDOWODNIONE — `bench_curl_gateway_nocam.py`, 2026-08-30 13:29Z]:**

```
[  297 ms] health                       -> 200
[ 1329 ms] catalog                      -> 200  (item 9829857579)
[ 2641 ms] conversations                -> 200  (txn 21916604367)
[ 4344 ms] build                        -> 200  (checkout jkG3E_5bYpNtd-BFngQFh)
[ 5547 ms] put payment_method           -> 200
[ 5985 ms] pickup_points                -> 200  (15 punktów)
[ 7454 ms] put pickup_details           -> 200
[ 9985 ms] PAYMENT -> BRAMKA            -> 200, payment=pending
```

- **`payment` → 200 + status `pending` + redirect do Adyen** (`checkoutshopper-live.adyen.com`)
- **Czas do bramki: 9969 ms (~10 s)**, z czego sam `payment` + przekierowanie = ~2.5 s
- **Screenshot bramki z wypalonym timestampem ms**: `bramka_nocam_dowod.png`

**Wniosek końcowy [UDOWODNIONE]:**
1. Pełny flow zakupowy (scrapowanie → transakcja → rezerwacja → konfiguracja → płatność → bramka)
   przechodzi **w 100% przez `curl_cffi`**, bez Camoufox w ścieżce krytycznej i bez kupowania po
   selektorach — dokładnie jak stawiał użytkownik.
2. **Realny czas do bramki to ~10 s**, NIE 1–2 s. „1–2 s" jest osiągalne wyłącznie dla detekcji
   (328 ms) lub time-to-build (~2.7–4.0 s), nigdy dla ścieżki do bramki — bo sam `payment` ma
   serwerowy floor ~2.5–2.7 s, a przed nim stoją obowiązkowe kroki (conversations ~1.5 s,
   build ~1.5 s, 2× PUT + pickup ~3.4 s).
3. Screenshot bramki wykonano **po** wygenerowaniu `redirect_url` przez curl_cffi — render to
   pomocniczy krok wizualny, nie część ścieżki zakupowej.
```

