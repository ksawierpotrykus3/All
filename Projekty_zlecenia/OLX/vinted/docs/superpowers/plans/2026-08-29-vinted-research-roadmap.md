# Harmonogram badań naukowo-inżynierskich — Bot Vinted (pełny cykl weryfikacyjny)

> **For agentic workers:** Ten dokument jest roadmapą badawczą, nie planem implementacji
> krok-po-kroku. Każdą fazę realizuje się jako osobny spike/eksperyment z twardym timeboxem
> i mierzalnym kryterium wycofania. Postęp zapisuje się w dokumentacji inżynierskiej
> (`DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md`, raporty `vinted/raporty/`) w ≤24 h od zamknięcia fazy.

**Cel:** Kompleksowo zweryfikować wszystkie niewiadome techniczne i biznesowe projektu, aby
móc obiektywnie rozstrzygnąć, które rozwiązania warto wdrożyć, a które odrzucić.

**Stan wyjściowy (2026-08-29):** warstwa detekcji zmierzona (RTT p50 ~719 ms, latencja
wewnętrzna <1 ms); warstwa zakupu **zablokowana** przez SDK Incognia, które nie inicjalizuje
się w headless Camoufox; rezerwacja end-to-end nieudowodniona; multikonto/proxy/WebUI/3DS
całkowicie niezbadane.

**Założenie czasowe:** wszystkie daty niżej zakładają start badań **2026-09-01**
(konieczne potwierdzenie ważności sesji `maksks0` po ~2 h od ostatniego harvestu wymaga
ręcznej interwencji — traktowane jako external założenie M0).

**Ścieżka krytyczna:** Faza 1 → 2 → 3 → 7 → 9. Faza 4 jest równoległa do Fazy 3.
Fazy boczne (5, 6, 8) biegną równolegle do ścieżki krytycznej.

---

## Struktura faz i zależności

| Faza | Nazwa | Zależy od | Zależność zewnętrzna | Typ |
|---|---|---|---|---|
| 0 | Infrastruktura badawcza i punkt odniesienia | — | ręczne logowanie maksks0 (~2h sesji) | wstęp |
| 1 | Rozwiązanie blokera Incognia/DataDome | 0 | brak | krytyczna |
| 2 | Realna rezerwacja `checkout/build` | 1 | wybrany silnik/tryb z F1 | krytyczna |
| 3 | Optymalizacja rezerwacji <3 s (pre-warm) | 2 | brak | krytyczna |
| 4 | Odwracalność rezerwacji | 2 | brak | krytyczna (równoległa do F3) |
| 5 | Płatność: karta bez 3DS vs BLIK | 0 | konto klienta z zapisaną kartą | boczna |
| 6 | Filtr kategorii przez SSR HTML | 0 | brak | boczna |
| 7 | Multikonto + proxy rezydencjalne + anty-ban | 3 | proxy rezydencjalne (koszt) | krytyczna |
| 8 | Architektura VPS + Web UI/CLI | 3 | VPS dostępny (ssh-assistant) | boczna |
| 9 | Benchmark porównawczy vs kops.gg + podsumowanie | 7 | 3 konta klienta | zamykająca |

### Brama decyzyjna (go / no-go)
- **Po M1 (Incognia):** jeśli init rate <100% → wstrzymanie ścieżki krytycznej, decyzja
  o headed-only (ekstremalny koszt operacyjny) lub rezygnacja z rezerwacji.
- **Po M3 (<3 s):** jeśli p50 >5000 ms przy rozgrzanym kontekście → projekt nie spełnia
  progu przebicia kopsa; rekomendacja redukcji zakresu lub przerwy (decyzja biznesowa).
- **Po M7 (anty-ban):** jeśli przeżywalność <50% okna testowego → redukcja do 1-2 kont lub
  rezygnacja z multikonta.

---

## Protokół aktualizacji dokumentacji (obowiązuje od Fazy 0)

Każda faza kończy się aktualizacją dokumentacji **nie później niż 24 h** od zamknięcia etapu.

### A. Dokumentacja techniczna
- **Plik:** `vinted/testy_camoufox/DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md`
- **Zakres aktualizacji:** szczegóły implementacji testowanego rozwiązania, pełne wyniki
  testów z surowymi dowodami (JSON/log), specyfikacje komponentów, diagramy architektury
  (Mermaid), raporty błędów i sposoby ich rozwiązania.
- **Format:** każdy nowy wniosek oznaczony `[UDOWODNIONE]` (pomiar) lub `[DOMNIEMANE]`
  (hipoteza bez pomiaru). Żadna liczba bez dowodu.

### B. Dokumentacja procesowa
- **Pliki:** `docs/superpowers/plans/2026-08-29-vinted-research-roadmap.md` (ten plik) oraz
  raporty postępu w `vinted/raporty/`.
- **Zakres:** aktualizacja harmonogramu (odhaczanie kamieni milowych), przypisanie
  odpowiedzialności (autor fazy), metodyka pracy (spike + timebox), protokoły raportowania.

### C. Dokumentacja archiwizacyjna
- **Narzędzie:** git. Każda faza to osobny commit z konwencją
  `research(faza-N): <opis> [autor] <data>`.
- **Przechowywanie:** wersje robocze w gałęzi `research/faza-N`, merge do `main` po akceptacji.
- **Log zmian:** `vinted/raporty/CHANGELOG.md` — wpis z autorem, datą, opisem zmiany i
  identyfikatorem commita.

### D. Dostępność i spójność
- Wszystkie raporty w `vinted/raporty/` z jednoznaczną numeracją faz.
- Każdy raport zawiera sekcję "Status wiarygodności" spójną z konwencją UDOWODNIONE/DOMNIEMANE.
- Po każdej aktualizacji weryfikacja krzyżowa: brak sprzeczności z `00_POWTORZENIA_I_SPRZECZNOSCI.md`.

---

## Faza 0 — Infrastruktura badawcza i punkt odniesienia

**Okres:** 2026-08-30 → 2026-08-31 (2 dni)

### Cel badawczy
Ustalić powtarzalny, bezpieczny punkt odniesienia pomiarowego i przygotować środowisko do
eksperymentów na własnym przedmiocie testowym.

### Metody weryfikacji
- **Test kompatybilności środowiska:** Camoufox (`headless=True` i `headless=False`),
  `curl_cffi`, Playwright — sprawdzenie wersji i poprawnej inicjalizacji.
- **Test bezpieczeństwa (zasady operacyjne):** konfiguracja konta testowego `maksks0` +
  własny przedmiot testowy; potwierdzenie własności przez SSR HTML (`member/<id>`).
- **Narzędzia:** git (branch `research/faza-0`), DuckDB do analizy logów z `bench` (pliki JSON).

### Kryterium porównania
Wybór silnika stealth do Faz 1–3 na podstawie wskaźnika inicjalizacji SDK Incognia i pass-rate
DataDome w teście smoke — zapisany jako jednoznaczny wybór w dokumentacji.

### Wskaźniki sukcesu
- **Ilościowe:** środowisko odtwarzalne w 1 komendzie; 1 własny przedmiot testowy potwierdzony
  jako własny; baseline RTT detekcji p50 ∈ [650, 800] ms (zgodność z sekcją 10.7).
- **Jakościowe:** dokumentacja środowiska i zasad bezpieczeństwa zaktualizowana.

**Kamień milowy M0:** baseline pomiarowy zapisany w `vinted/raporty/`.

---

## Faza 1 — Rozwiązanie blokera Incognia/DataDome (KRYTYCZNA)

**Okres:** 2026-09-01 → 2026-09-05 (5 dni roboczych, timebox twardy)

### Cel badawczy
Rozstrzygnąć, czy SDK Incognia da się zainicjalizować w trybie headless, czy wymagany jest
`headless=False` (headed) lub inny silnik stealth. To warunek wstępny dla każdej dalszej
rezerwacji.

### Hipotezy do zweryfikowania (z sekcji 12.3 dokumentacji)
- **H1:** Incognia wykrywa headless i odmawia inicjalizacji → wymaga `headless=False`.
- **H2:** WebGL niedostępny mimo braku `block_webgl` (fingerprint_preset/profil GPU).
- **H3:** SDK wymaga pełnego zdarzenia `load`, a nie `commit`.

### Metody weryfikacji
- **Test kompatybilności silników:** Camoufox (headless/headed) vs Playwright+stealth
  (Chromium) vs patchright — pomiar `window.Incognia*` oraz `webgl_available`.
- **Test wydajności przechwycenia:** czy request `checkout/build` zawiera
  `x-incognia-request-token` przy `el.click()`.
- **Narzędzia:** Camoufox, Playwright, patchright, `page.on("request")` do przechwycenia
  nagłówków, sequentialthinking do rejestracji decyzji.
- **Kryterium porównania:** silnik z najwyższym wskaźnikiem `Incognia init rate` i
  `x-incognia-request-token presence rate`.

### Wskaźniki sukcesu
- **Ilościowe:** Incognia init rate = 100% na wybranym silniku; `x-incognia-request-token`
  obecny w 100% żądań `checkout/build`; DataDome pass rate (brak `geo.captcha-delivery.com`)
  = 100% na własnym przedmiocie.
- **Jakościowe:** jednoznaczna decyzja silnik/tryb wpisana do dokumentacji z dowodem.

**Kryterium wycofania (twarde):** brak 100% init rate po 5 dniach → decyzja o przejściu na
headed-only (akceptacja wyższego kosztu operacyjnego) lub wstrzymanie projektu.

**Kamień milowy M1:** Incognia rozwiązana, wybrany silnik/tryb.

---

## Faza 2 — Realna rezerwacja `checkout/build`

**Okres:** 2026-09-06 → 2026-09-08 (3 dni)

### Cel badawczy
Potwierdzić, że bot generuje realny `purchase_id` na własnym przedmiocie testowym przez
wybrany silnik.

### Metody weryfikacji
- **Test funkcjonalny E2E (bez mocka sieci):** pełny flow `goto → el.click() → purchase_id`
  na własnym przedmiocie; przechwycenie redirectu `/checkout?purchase_id=`.
- **Test niezawodności:** obsługa braku przycisku (przedmiot sprzedany), timeout `purchase_id`.
- **Narzędzia:** Camoufox (wybrany tryb), `page.on("response")`, `CheckoutTimer`.

### Kryterium porównania
Silnik/tryb wybrany w Fazie 1 jako zwycięzca przechwycenia `x-incognia-request-token` —
potwierdzenie, że wybór jest powtarzalny end-to-end.

### Wskaźniki sukcesu
- **Ilościowe:** liczba udanych rezerwacji / liczba prób = 100%; `purchase_id` przechwycony
  w 100% udanych prób; średni czas rezerwacji zapisany jako baseline (oczekiwany ~34–39 s
  przy zimnym kontekście).
- **Jakościowe:** struktura `purchase_id`/`order_id`/`order_type` potwierdzona z redirectu
  odpowiedzi (nie z `request`).

**Kamień milowy M2:** pierwszy w pełni zautomatyzowany `purchase_id`.

---

## Faza 3 — Optymalizacja rezerwacji <3 s (pre-warm)

**Okres:** 2026-09-09 → 2026-09-11 (3 dni)

### Cel badawczy
Obniżyć czas rezerwacji z ~34 s do progu <3 s (p50) przez pre-warmowaną sesję i minimalizację
nawigacji.

### Metody weryfikacji
- **Test wydajności (benchmark latencji):** pomiar `t(decyzja) → t(purchase_id)` przy zimnym
  i ciepłym kontekście; rozbicie na start przeglądarki, nawigację, klik, redirect.
- **Test funkcjonalny pre-warm:** podłączenie `_czy_prewarm_wymagany()` tak, by kolejne zakupy
  nie robiły `page.goto("/items/{id}")` od zera.
- **Narzędzia:** `LatencyRecorder` (percentyle p50/p95/p99), DuckDB do analizy próbek.

### Kryterium porównania
Ścieżka "ciepły kontekst bez pełnej nawigacji" vs "zimny kontekst" — wybór tej z niższym p50.

### Wskaźniki sukcesu
- **Ilościowe:** rezerwacja p50 < 3000 ms przy rozgrzanym kontekście; p95 < 5000 ms;
  pierwszy zakup (zimny) odnotowany osobno jako koszt jednorazowy.
- **Jakościowe:** usunięty martwy kod `_czy_prewarm_wymagany` (realnie użyty).

**Kamień milowy M3:** rezerwacja p50 <3 s zmierzona i udokumentowana.

---

## Faza 4 — Odwracalność rezerwacji

**Okres:** 2026-09-12 → 2026-09-13 (2 dni)

### Cel badawczy
Ustalić, czy rezerwację (`checkout/build`) można anulować przed płatnością — kluczowe dla
strategii "podejdź do przycisku bez finalizacji".

### Metody weryfikacji
- **Test bezpieczeństwa:** na własnym przedmiocie wywołać rezerwację, następnie próba
  anulowania (`PUT /purchases/{id}/checkout` z pustymi komponentami lub dedykowany endpoint
  cancel); obserwacja, czy przedmiot wraca do stanu dostępnego.
- **Narzędzia:** przechwytywanie ruchu `page.on("request"/"response")`, DuckDB do porównania
  stanów przed/po.

### Wskaźniki sukcesu
- **Ilościowe:** liczba udanych anulowań / liczba prób; czas do zwolnienia przedmiotu.
- **Jakościowe:** jednoznaczna odpowiedź tak/nie + zapisany flow (wymagane dla bezpiecznego
  dry-runu produkcyjnego).

**Kamień milowy M4:** odwracalność potwierdzona lub wykluczona z dowodem.

---

## Faza 5 — Płatność: karta bez 3DS vs BLIK (BOCZNA)

**Okres:** 2026-09-01 → 2026-09-05 (5 dni, równolegle do Fazy 1)

### Cel badawczy
Rozstrzygnąć, która metoda płatności umożliwia zakup bez interakcji człowieka (warunek
przebicia progu kopsa 5–6 s).

### Metody weryfikacji
- **Test kompatybilności PSP:** analiza, czy Vinted frontend przekazuje `payment_method`
  (karta/BLIK) do zewnętrznego PSP (Adyen/Mangopay) — czy 3DS zależy od banku, nie od Vinted.
- **Test użyteczności:** zmierzenie liczby kroków i czasu dla BLIK (kod 6-cyfrowy) vs karta
  tokenizowana.
- **Narzędzia:** analiza bundli JS (`grep` w chunkach), manualny dry-run w headed Camoufox.
- **Kryterium porównania:** metoda z zerową interakcją człowieka i najkrótszym czasem do
  potwierdzenia.

### Wskaźniki sukcesu
- **Ilościowe:** liczba kroków do zapłaty (karta vs BLIK); czas BLIK (oczekiwany 10–20 s) vs
  karta (cel <3 s).
- **Jakościowe:** rekomendacja "karta tokenizowana" lub "BLIK" z uzasadnieniem.

**Kamień milowy M5:** wybrana metoda płatności wpisana do specyfikacji.

---

## Faza 6 — Filtr kategorii przez SSR HTML (BOCZNA)

**Okres:** 2026-09-06 → 2026-09-07 (2 dni, równolegle)

### Cel badawczy
Dostarczyć 6. filtr (kategoria), który nie działa w API (`catalog[]` → sztywne 960).

### Metody weryfikacji
- **Test funkcjonalny parsera SSR:** pobranie `/catalog?catalog[]=ID`, parsowanie Flight Data
  Next.js, wyciągnięcie `catalog_id` z ofert.
- **Test wydajności:** czas parsowania SSR vs API.
- **Narzędzia:** `playwright_capture.py`, `parse_flight.py`, DuckDB do walidacji pokrycia.

### Kryterium porównania
Parsowanie SSR Next.js Flight Data vs alternatywna identyfikacja kategorii przez tagi/heurystykę —
wybór tej z wyższym pokryciem i niższą liczbą fałszywych pozytywów.

### Wskaźniki sukcesu
- **Ilościowe:** pokrycie ofert pasujących do kategorii ≥95% **(fallback: jeśli <95% —
  mapowanie przez reguły + whitelist markowych słów kluczowych, z podziałem 'pełna kategoria' /
  'kategoria rozszerzona')**; czas parsowania <500 ms; fałszywe pozytywy = 0.
- **Jakościowe:** filtr kategorii integrowalny z `Filtry` modelu.

**Kamień milowy M6:** kategoria działa end-to-end przez SSR.

---

## Faza 7 — Multikonto + proxy rezydencjalne + anty-ban (KRYTYCZNA)

**Okres:** 2026-09-14 → 2026-09-20 (7 dni)

### Cel badawczy
Zmierzyć przeżywalność kont i skuteczność anty-banu przy 3–4 kontach, proxy rezydencjalnych,
spoofingu fingerprintu i losowych opóźnieniach.

### Metody weryfikacji
- **Test bezpieczeństwa (anty-ban):** 1 IP = 1 konto + dedykowane proxy rezydencjalne;
  rotacja fingerprintu; jitter zamiast stałych opóźnień.
- **Test wydajności parallel:** N kont próbuje kupić ten sam przedmiot; pierwszy wygrywa.
- **Test niezawodności:** pomiar czasu do bana (liczba zakupów do blokady) na kontach
  testowych.
- **Narzędzia:** proxy rezydencjalne, Camoufox multikonto, `LatencyRecorder`,
  sequentialthinking do rejestracji decyzji architektonicznych.
- **Kryterium porównania:** 1 IP=1 konto+proxy vs bez proxy (datacenter) — wskaźnik
  przeżywalności i pass-rate.

### Wskaźniki sukcesu
- **Ilościowe:** przeżywalność kont (dni lub liczba zakupów do bana); DataDome pass rate
  ≥98% przy residential proxy; liczba równoległych kont bez banów w oknie testowym.
- **Jakościowe:** mapa ryzyka banów; rekomendacja skali (3 vs 4 konta).

**Kamień milowy M7:** zmierzona przeżywalność kont i pass-rate proxy.

---

## Faza 8 — Architektura VPS + Web UI/CLI (BOCZNA)

**Okres:** 2026-09-09 → 2026-09-14 (4 dni robocze, równolegle)

### Cel badawczy
Zweryfikować, czy bot działa w całości na VPS bez Discorda, z panelem Web UI lub CLI.

### Metody weryfikacji
- **Test kompatybilności wdrożenia:** deploy na VPS (Linux), uruchomienie CLI `monitor/autocop`.
- **Test użyteczności:** ocena CLI vs Web UI dla zarządzania filtrami, kontami, logami.
- **Narzędzia:** ssh-assistant (VPS), FastAPI (Web UI), `click` (CLI).

### Kryterium porównania
CLI (click) vs Web UI (FastAPI+ minimal frontend) — ocena kosztu utrzymania, prostoty
instalacji na VPS oraz użyteczności zarządzania (filtry, konta, logi).

### Wskaźniki sukcesu
- **Ilościowe:** bot działa na VPS w 100% testowanych komend; czas odpowiedzi panelu <500 ms.
- **Jakościowe:** wybór Web UI vs CLI uzasadniony kosztem i użytecznością.

**Kamień milowy M8:** działający bot na VPS z wybranym interfejsem.

---

## Faza 9 — Benchmark porównawczy vs kops.gg + podsumowanie

**Okres:** 2026-09-21 → 2026-09-22 (2 dni)

### Cel badawczy
Zmierzyć realną przewagę bota nad kops.gg (5–6 s checkout) na 3 kontach i przygotować
podsumowanie.

### Metody weryfikacji
- **Test wydajności porównawczy:** pomiar end-to-end (detekcja → rezerwacja → decyzja o
  płatności) na 3 kontach; porównanie z udokumentowanym progiem kopsa 5–6 s.
- **Narzędzia:** `LatencyRecorder`, DuckDB do agregacji, `CheckoutTimer`.

### Kryterium porównania
Prywatny bot (moduł `bot/`) vs kops.gg Pro (udokumentowane 5–6 s realnie) — p50 end-to-end
(detekcja → rezerwacja → decyzja o płatności) na 3 kontach klienta.

### Wskaźniki sukcesu
- **Ilościowe:** rezerwacja p50 <3 s przy 0% blokad DataDome w detekcji; czas end-to-end
  p50 <5 s (przebicie kopsa).
- **Jakościowe:** jednoznaczna odpowiedź "bot przebija kopsa" / "nie przebija".

**Kamień milowy M9:** benchmark + draft podsumowania końcowego.

---

## Podsumowanie końcowe (obowiązkowe)

**Termin:** **7 dni od zamknięcia Fazy 9** (do 2026-09-29).
**Właściciel dokumentacji:** autor ostatniej fazy (KA = odpowiedzialny za zamknięcie cyklu).
Dokumenty aktualizowane w ramach SLA ≤24h przez autora zamkniętej fazy.

### Zakres podsumowania (wymagany)
1. **Obiektywna ocena zgodności** każdego testowanego rozwiązania z wymaganiami F1–F5
   (macierz wymaganie → rozwiązanie → wynik).
2. **Analiza wad i zalet** każdego podejścia (Camoufox vs Playwright vs patchright; Faza A vs
   Faza C; karta vs BLIK; Web UI vs CLI; 1 IP=1 konto+proxy vs datacenter).
3. **Rekomendacje uszeregowane priorytetem** (P0=wdróż natychmiast, P1=wdróż po X, P2=odrzuć),
   z uzasadnieniem liczbowym.

### Włączenie do dokumentacji
- Podsumowanie zapisane jako `vinted/raporty/08_podsumowanie/RAPORT_KONCOWY.md`.
- Przedstawione do akceptacji kierownictwa projektu z metryką decyzji (akceptacja/odrzucenie/
  poprawki) w terminie 7 dni.

---

## Macierz raportowania postępów

| Moment | Raport | Kanał |
|---|---|---|
| Co 3 dni robocze | krótki status: ukończone kamienie, blokery, ryzyka | `vinted/raporty/` |
| Koniec każdej fazy | pełny raport fazy z dowodami (≤24 h) | `DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md` + `raporty/` |
| Koniec cyklu | podsumowanie końcowe + rekomendacje (≤7 dni) | `raporty/08_podsumowanie/` |

## Zasoby wymagane
- Konto testowe z ważną sesją (ręczne logowanie 1×) + własny przedmiot testowy.
- Dostęp do VPS (ssh-assistant) dla Fazy 8.
- Proxy rezydencjalne (koszt operacyjny) dla Fazy 7.
- Konto klienta z zapisaną kartą (decyzja biznesowa) dla Fazy 5.
- Biblioteki: `curl_cffi`, `camoufox`, `playwright`, `patchright`, `pydantic`, `pytest`,
  `duckdb`, `fastapi`.