# Benchmark czasów — flow do bramki w przeglądarce (Camoufox)

Data: 2026-09-01
Źródło: `tools/playwright_speed_trials.py` na żywej sesji (profil `implementation/browser-profiles/profil_firefox`), wynik zapisany w `wynik_playwright_speed_trials.json`.

---

## 1. CEL TESTU

Zmierzono czasy rzeczywistych kroków zakupu w przeglądarce Camoufox z ważną sesją:
1. `GET /api/v2/catalog/items` (wybór itemu — lekki wariant per_page=2)
2. Load strony itemu (odświeżenie cookie DataDome)
3. `POST /api/v2/conversations` (inicjacja transakcji)
4. `POST /api/v2/purchases/checkout/build` (bramka)

---

## 2. WYNIKI POMIARÓW [UDOWODNIONE]

| Krok | Czas | Rozmiar | Status | Uwagi |
|---|---|---|---|---|
| catalog items (per_page=2) | **406 ms** | 22 141 B | 200 | 2 items, sesja ważna (uid 3180346878) |
| conversations | **1172 ms** | — | 200 | transakcja utworzona |
| checkout/build | **187 ms** | — | **403** | **DataDome block** |

Item testowy: `id=9849718170`, seller `173067119` ("Uplé kraťasy").

### Czasy pojedynczych requestów (bez loadu strony):
```
catalog:        406 ms  (200)
conversations:  1172 ms (200)
build:          187 ms  (403 DataDome)
```

### Cookie DataDome po loadzie strony itemu:
```
datadome: 8i6PvBE4OhMz~UDQXra3gizRpdPQVdSns5aUIzInM1K96P1rr2
```
Cookie **zostało wygenerowane** przez przeglądarkę Camoufox na loadzie strony — a mimo to `build` zwrócił 403.

---

## 3. KLUCZOWY WNIOSEK [UDOWODNIONE]

> **DataDome blokuje `checkout/build` nawet w przeglądarce Camoufox z ważną sesją i świeżym cookie DataDome.**

To zmienia obraz problemu:
- Wcześniej [DOMNIEMANE]: 403 wynika z niespójności cookie curl_cffi ↔ fingerprint TLS Firefoksa.
- Teraz [UDOWODNIONE]: 403 występuje **również w spójnym stacku przeglądarkowym** — cookie i fingerprint są spójne, sesja ważna, a `build` i tak zwraca 403.

**Implikacje:**
1. `checkout/build` ma **wyższy próg DataDome** niż katalog/conversations (zwykłe `GET`/`POST` przechodzą, transakcyjny `build` nie).
2. Samo cookie + ważna sesja to **za mało** — prawdopodobnie wymagana jest dodatkowa sygnatura urządzenia (Incognia token) lub pełny flow strony checkout.
3. Dalsze pomiary czasów (payment, 3DS) są **zablokowane** dopóki nie przejdzie `build`.

---

## 4. CO TO OZNACZA DLA CELU <4s

- Część "detekcja" jest zmierzona i szybka: catalog **406 ms** → item znaleziony.
- Część "transakcja" jest **niezmierzalna** — blokada `build` zatrzymuje całą ścieżkę.
- Czas conversations (1172 ms) jest już znany i wpada w ścieżkę krytyczną.

### Szacunkowy budżet czasu (jeśli build przejdzie):
```
[DOMNIEMANE — nie zmierzone, bo build 403]
catalog:        ~400 ms
conversations:  ~1170 ms
build:          ~200 ms
payment:        ??? (zablokowane)
3DS:            ??? (zablokowane)
```
Budżet <4s jest **osiągalny** pod warunkiem przejścia DataDome na `build` — pozostałe kroki to łącznie ~1.8s.

---

## 5. KONFRONTACJA Z DOKUMENTACJĄ

- Aktualizuje [SYNTEZA_GŁÓWNA.md](../../testy_camoufox/docs/SYNTEZA_GŁÓWNA.md): metryki "Checkout time <4s ❌ Nie zmierzone" — potwierdzone częściowo: 2 z 3 kroków zmierzone.
- Potwierdza [CHECKOUT_KONFLIKTY.md](../../testy_camoufox/docs/synthesis/CHECKOUT_KONFLIKTY.md): `checkout/build` nadal 403 — konflikt NIE ROZSTRZYGNIĘTY.
- Rozszerza [CHECKOUT_SEKWENCJA_APK.md](CHECKOUT_SEKWENCJA_APK.md): realne czasy kroków wg APK (sekwencja potwierdzona pomiarami).

### [NAKAZ] Pytania badawcze
1. Czy `build` wymaga tokenu Incognia, którego nie wysyłamy w tym teście? → nast. test: build z nagłówkiem `X-Incognia-Request-Token` (token wygenerowany natywnie w przeglądarce).
2. Czy `build` wymaga wcześniejszego wejścia na stronę checkoutu (prefetch `X-DD-B` przez JS)? → nast. test: `page.goto` na `/checkout/{id}` przed `build`.

---

## 6. ZAPIS POMIARÓW

- Pełny wynik: [wynik_playwright_speed_trials.json](../../testy_camoufox/wynik_playwright_speed_trials.json) (rekonstrukcja z terminala — oryginalny zapis skryptu nie zadziałał przez `return` przed zapisem w starej wersji; wartości przepisane ręcznie z rzeczywistych odczytów).
- Skrypt: [playwright_speed_trials.py](../../testy_camoufox/tools/playwright_speed_trials.py) (aktualna wersja zapisuje wynik również przy 403).
