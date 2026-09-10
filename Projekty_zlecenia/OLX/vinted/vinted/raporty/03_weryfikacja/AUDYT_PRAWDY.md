# AUDYT PRAWDY — co jest zmierzone, a co zmyślone w materiałach Vinted [UDOWODNIONE]

Data: 2026-08-26
Metoda: konfrontacja trzech źródeł z jedynym twardym dowodem — rzeczywistym przechwyceniem ruchu
(`vinted/dane/captured_requests.json`) oraz raportem końcowym opartym na realnych skryptach pomiarowych.

## TL;DR (wniosek na start)

Mamy DWA rodzaje materiałów o zupełnie różnej wartości dowodowej:

1. **RAPORT_FINALNY.md** — oparty na realnych pomiarach (skrypty `probe_*.py` + przechwycony ruch). To jest PRAWDA, którą możemy bronić.
2. **research/Analiza Techniczna.txt + Blueprint.txt** — wygenerowane przez AI, z cytowaniami do plików, które NIE ISTNIEJĄ w repo. Zawierają **zmyślone endpointy checkoutu i zmyślone liczby** (<1s checkout, wallet omija 3DS). To jest FIKCJA podszyta pod inżynierię.

Odpowiedź na pytanie "czy Gemini pierdoli": **częściowo tak**. [POTWIERDZONE] Jego ogólny kierunek (kops wolny przez Discorda + kolejkę) jest prawdziwy, ale [HIPOTEZA] konkretne liczby "0.6–1.2s checkout" i "płatność z Portfela Vinted omija 3DS" to hipotezy zapisane jako fakt, nie nasze pomiary.

---

## SEKCJA A — FAKTY (zmierzone, udokumentowane w kodzie)

Te twierdzenia mają pokrycie w `probe_*.py` + `captured_requests.json`:

| # | Fakt | Źródło dowodu |
|---|---|---|
| A1 | [UDOWODNIONE] Endpoint katalogu `GET /api/v2/catalog/items` działa i zwraca JSON | raport_sonda_api.md, probe_api.py |
| A2 | `order=newest_first` realnie sortuje po najnowszych | RAPORT_FINALNY.md (probe_luki.py) |
| A3 | Filtry działają: brand_ids, size_ids, status_ids, search_text, price_from/to | RAPORT_FINALNY.md (test bzdurnym ID → 0 wyników) |
| A4 | [UDOWODNIONE] Filtr kategorii NIE działa w API (zwraca sztywne 960) | RAPORT_FINALNY.md (catalog[]=2954 → 960) |
| A5 | Kategoria dostępna TYLKO przez HTML SSR (Next.js flight data) | captured_requests.json (strona /catalog), RAPORT_FINALNY.md |
| A6 | ID ofert są losowe (43 rosnące / 52 malejące, rozstęp 121757) — brak predykcji jak na OLX | RAPORT_FINALNY.md (probe_luki.py) |
| A7 | Rate-limit twardy ~0.83 req/s (429 po 6 żądaniach w 5.9s) | RAPORT_FINALNY.md (probe_rate.py) |
| A8 | Maks per_page=96, total_entries=960, total_pages=10 | RAPORT_FINALNY.md |
| A9 | `/api/v2/items/{id}` → 404, `/details` → 403, `/items/{id}` HTML → 200 (~1.95MB) | RAPORT_FINALNY.md |

**To wszystko jest PRAWDA i możemy to pokazać klientowi bez ryzyka.**

---

## SEKCJA B — FIKCJA (w research/*.txt, niepotwierdzona NICZYM)

Poniższe twierdzenia pojawiają się w `Analiza Techniczna Architektury Vinted.txt`
i `Blueprint Techniczny Bota Vinted.txt`, ale **NIE mają pokrycia w żadnym przechwyceniu ani skrypcie**:

| # | Twierdzenie z research | Werdykt |
|---|---|---|
| B1 | `POST /api/v2/transactions` jako pierwszy krok checkoutu | **ZMYŚLONE** — brak w captured_requests.json; nigdy nie przechwyciliśmy tego endpointu |
| B2 | `POST /api/v2/transactions/{id}/shipment` | **ZMYŚLONE** — j.w. |
| B3 | `POST /api/v2/transactions/{id}/payment` | **ZMYŚLONE** — j.w. |
| B4 | `payment_method_type: "wallet"` — płatność z Portfela Vinted | **ZMYŚLONE** — brak dowodu, że Vinted ma portfel "balance" dla kupującego w ogóle |
| B5 | "Portfel omija 3DS, rozliczenie <300 ms" | **ZMYŚLONE** — liczba <300ms nigdy nie była mierzona |
| B6 | "Checkout 0.6–1.2 s" | **ZMYŚLONE** — to projekcja, nie pomiar |
| B7 | Adyen i Mangopay jako dostawcy płatności | **PRAWDOPODOBNE, ale niezmierzone** — to wiedza ogólna o Vinted, nie nasz dowód |

### Dowód, że research to fikcja

Dwa niezależne sygnały:

**(1) Cytowania do nieistniejących plików.** Research cytuje m.in.:
- `05_raport_sonda_api.md` → w repo jest `raport_sonda_api.md` (bez numeru)
- `01_RAPORT_FINALNY_VINTED.md` → w repo jest `RAPORT_FINALNY.md`
- `10_probe_losowosc_id_vinted.py` → NIE MA takiego pliku (jest `probe_luki.py`)
- `06_wymagania_klienta.md`, `04_wycena_i_architektura.md` → NIE MA tych plików

AI wygenerowało własną, zmyśloną bibliografię, żeby wyglądała wiarygodnie. To klasyczny sygnał halucynacji.

**(2) Przechwycony ruch NIE zawiera checkoutu.** `captured_requests.json` (52 requesty) zawiera
WYŁĄCZNIE: stronę katalogu `/catalog`, banery, statystyki, reklamy (Prebid/DFP), Google Analytics/GTM,
logi. [UDOWODNIONE] **Zero** endpointów transakcyjnych. To znaczy: na dzień dzisiejszy checkout Vinted jest dla nas
**całkowicie niezmapowany** — i to jest dokładnie to, co RAPORT_FINALNY pisze uczciwie jako "muszę zmierzyć".

---

## SEKCJA C — PRAWDA o checkoucie (jedyne, co wiemy na pewno)

1. Checkout Vinted jest **nieudokumentowany**. Nie mamy ani jednego przechwyconego requestu transakcyjnego.
2. Limit ~1 req/s dotyczy również checkoutu (twarde, zmierzone na katalogu).
3. Kops.gg robi 5–6s (dane od klienta, spójne z analizą mechaniki kopsa).
4. **Nie wiemy**, czy prywatny bot zejdzie poniżej — to ustali dopiero prototyp na kontach klienta.

To oznacza, że obietnica "schodzimy do 0.6–1.2s" z plików research **nie ma podstaw** i NIE wolno jej
pisać klientowi. Uczciwa wersja brzmi: "kops traci czas na Discorda i kolejkę; my te dwa czynniki
eliminujemy, ale o ile konkretnie będzie szybciej — to zmierzymy, zanim cokolwiek obiecam".

---

## SEKCJA D — odpowiedź dla seniora (na dowodach, uczciwa)

> Gdzie najszybciej pojawia się oferta?

**W API katalogu:** `GET /api/v2/catalog/items?order=newest_first`. To jedyne miejsce, gdzie mamy
[UDOWODNIONE] twardy dowód, że sortowanie po najnowszych DZIAŁA (zmierzone). ID są losowe, więc trik z predykcją ID
z OLX odpada — przewaga musi pochodzić wyłącznie z szybkości reakcji, nie z przewidywania.

> Ile realnie zejdziemy poniżej kopsa?

**Nie wiem, i nikt uczciwie tego nie wie bez pomiaru.** Wiemy, że kops traci 2s na Discorda/kolejkę
i 2–3s na autoryzację. My te dwa czynniki usuwamy (pre-warmed sesja + bez Discorda). Ale checkout
[NIEPOTWIERDZONE] nie jest zmapowany, więc każda konkretna liczba ("<1s") to teraz wróżenie, nie inżynieria.

> Co zrobić dalej?

Prototyp pomiarowy na 1 koncie (dry-run checkoutu bez finalnego kliku + benchmark wykrycia).
Dopiero po nim podajemy twardą liczbę. Dopiero potem 3 konta przez osobne proxy.

---

## SEKCJA E — co z tym zrobić (rekomendacja)

1. **Nie używać plików research/** do wyceny ani do obietnic klientowi — zawierają zmyślone liczby.
2. Oprzeć komunikację wyłącznie na RAPORT_FINALNY.md (fakty) + jawnym przyznaniu "checkout do zmierzenia".
3. Prototyp pomiarowy jest JEDYNYM źródłem prawdy o czasie checkoutu — to uzasadnia wycenę "płacisz za pomiar".
4. Zaplanować dry-run checkoutu jako pierwszy konkretny krok (przechwycenie realnych requestów transakcyjnych w DevTools).

## Źródła w repo (prawdziwe, zweryfikowane)

- RAPORT_FINALNY.md — raport końcowy z pomiarów (FAKTY A1–A9)
- raport_sonda_api.md — surowe wyniki sondy API
- jak_zejsc_ponizej_kopsa.md — analiza mechaniki kopsa (bez zmyślonych liczb checkoutu)
- dane/captured_requests.json — 52 przechwycone requesty (dowód, że checkout niezmapowany)
- wycena_vinted.md — wycena oparta na strategii "najpierw pomiar, potem cena"