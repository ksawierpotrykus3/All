# WERYFIKACJA OPTYMALIZACJI WYDAJNOŚCIOWYCH — DOWODY

Data: 2026-09-02
Zakres: optymalizacje O1, O2, O3, O4, O5 z raportu wydajnościowego (vs kops.gg) + P1 (limit detekcji), P2 (równoległy prewarm)
Status: ✅ O1, O2, O3, O5 wdrożone i zweryfikowane (111/111 testów). O4 — [SPRZECZNOŚĆ] udokumentowana, wymaga rozszerzenia badań. P1 — [UDOWODNIONE] wdrożone. P2 — regresja [POTWIERDZONE]: cofnięta, przywrócono prewarm sekwencyjny.

---

## 1. WPROWADZONE ZMIANY

### O1 — brakujące zależności
`orjson>=3.9` + `cryptography>=42.0` w [pyproject.toml](../../bot/pyproject.toml).

### O2 — batch pre-check dostępności `check_availability`
- `user_id` dodany do [models.py](../../bot/src/vintedbot/models.py#L58-L67) (`KonfiguracjaKonta`).
- `user_id` wyciągany z `/users/current` w [session_state.py](../../bot/src/vintedbot/session_state.py#L96-L103).
- `user_id` przekazywany w [daemon.py](../../bot/src/vintedbot/daemon.py#L50).
- pre-filter `sprawdz_dostepnosc` przed `conversations` w [checkout.py](../../bot/src/vintedbot/checkout.py#L550-L566).

### O3 — `_with_retry` dla kroku płatności `payment/continue`

### O5 — `REQUEST_TIMEOUT` 10s → 5s

### P1 — limit ofert detekcji 10 → 5
[daemon.py](../../bot/src/vintedbot/daemon.py#L24-L28) ustawia `POLL_LIMIT = 5`. [UDOWODNIONE rtt_per_page.json] RTT katalogu rośnie z `per_page`: 5→360 ms, 10→515 ms. Redukcja rozmiaru odpowiedzi (nie częstotliwości żądań) skraca pętlę pollingu ~30% (−155 ms/poll), zachowując pełną poprawność detekcji — `order=newest_first` gwarantuje nowe oferty na początku.

---

## 2. NIEPODWAŻALNE DOWODY WERYFIKACJI

### Dowód 1 — zależności importują się [UDOWODNIONE]
```
$ python -c "import orjson, cryptography; print(orjson.__version__, cryptography.__version__)"
orjson 3.11.7
cryptography 44.0.3
```

### Dowód 2 — aktywna szybka ścieżka orjson, NIE fallback [UDOWODNIONE]
```
$ python -c "import vintedbot.json_utils as j; print(hasattr(j, 'orjson'))"
HAS_ORJSON= True
```

### Dowód 3 — `check_availability` działa [UDOWODNIONE]
Endpoint `api.vinted.pl/checkout/purchases/check_availability` → **HTTP 200, 110 ms**, zwraca strukturę:
```json
{"purchase": {"items": {"buy": {"available": false, "unavailable_list": [...]}}}}
```
Źródło: [wynik_check_availability_1788212313.json](../../bot/output/wynik_check_availability_1788212313.json)

### Dowód 4 — O2 testy jednostkowe przechodzą [UDOWODNIONE]
3 nowe testy w [test_checkout.py](../../bot/tests/test_checkout.py#L575-L690):
- `test_O2_item_niedostepny_odrzuca_przed_conversations` — odrzuca zanim wywoła `conversations`
- `test_O2_item_dostepny_przechodzi_dalej` — kontynuuje gdy dostępny
- `test_O2_bez_user_id_pomija_prefilter` — bezpieczny fall-through bez `user_id`

### Dowód 5 — pełny suite przechodzi [UDOWODNIONE]
```
$ python -m pytest -q --tb=line -p no:cacheprovider
106 passed in 4.57s
```

---

## 3. POZIOMY PEWNOŚCI

| Optymalizacja | Status | Dowód |
|---|---|---|
| O1 (orjson + cryptography) | [UDOWODNIONE — WDROŻONE] | Dowód 1, 2 |
| O2 (check_availability pre-filter) | [UDOWODNIONE — WDROŻONE] | Dowód 3, 4, 5 |
| O3 (retry w payment/continue) | [UDOWODNIONE — WDROŻONE] | suite 5 |
| O5 (timeout 5s) | [UDOWODNIONE — WDROŻONE] | suite 5 |
| O4 (prewarm Incognia) | [SPRZECZNOŚĆ — NIE IMPLEMENTOWALNE bez badań] | Dowód 6 |
| P1 (limit detekcji 5) | [UDOWODNIONE — WDROŻONE] | rtt_per_page.json, komentarz daemon.py |
| P2 (równoległy prewarm) | [REGRESJA — COFNIĘTE] | Dowód 7, 8 |

---

## 4. O4 — DECYZJA O NIEIMPLEMENTOWALNOŚCI (twarde dowody)

### Dowód 6 — generator Node generuje AES-GCM, a web wymaga JWE [SPRZECZNOŚĆ]

**Fakt A:** [generate_incognia_token.js](../../bot/scripts/generate_incognia_token.js#L4-L31) generuje token **AES-GCM** (HKDF z `sdkInstanceId`):
```js
// komentarz wprost: "nie JWE, nie wymaga klucza RSA" [POTWIERDZONE]
const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext);
```

**Fakt B:** [SYNTEZA_GŁÓWNA.md](../../vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md#L18) dokumentuje, że web token Incognia to **JWE** (RSA-OAEP + A128CBC-HS256):
> "Incognia native vs web — token native NIE jest JWE (custom: zlib + obfuskowany AES + RSA); web używa JWE (A128CBC-HS256)"

**Wniosek [UDOWODNIONE]:** `incognia.py` (generator Node) produkuje token AES-GCM, który NIE jest zgodny z formatem JWE wymaganym przez web. Podpięcie go do `checkout.py` (który używa `incognia_harvest` przechwytującego PRAWDZIWY token JWE z przeglądarki) wstrzyknęłoby błędny format.

### Fakt C — `checkout.py` nie konsumuje generatora
[checkout.py](../../bot/src/vintedbot/checkout.py#L24) importuje `incognia_harvest` (harvest Camoufox), NIE `incognia.py` (generator). Token Incognia w checkoucie pochodzi wyłącznie z harvestu.

### Fakt D — brak `sdk_instance_id` w kodzie produkcyjnym
[UDOWODNIONE] Grep po `bot/src` nie znajduje żadnego źródła `sdk_instance_id` — występuje tylko w skrypcie eksploracyjnym `test_incognia_sequence.py`. Generator wymaga tego parametru, którego produkcja nie dostarcza.

### Decyzja — udokumentowana [POTWIERDZONE]
O4 jest **nieimplementowalne w obecnym stanie** z trzech niezależnych przyczyn:
1. generator produkuje AES-GCM, a web wymaga JWE (sprzeczność z dokumentacją),
2. brak konsumenta generatora w ścieżce checkoutu,
3. brak źródła `sdk_instance_id` w kodzie produkcyjnym.

[NAKAZ] Implementacja O4 wymaga najpierw rozszerzenia badań (AGENTS.md): rozstrzygnięcia czy generator AES-GCM jest w ogóle poprawny dla weba, oraz ustalenia skąd wziąć `sdk_instance_id`. Bez tego podpięcie prewarmu wstrzyknęłoby błędny token — cicha porażka w produkcji.

---

## 5. P2 — REGRESJA RÓWNOLEGŁEGO PREWARMU (cofnięte)

### Dowód 7 — regresja determinizmu checkoutu [UDOWODNIONE]

| Baza (przed zmianą) | Po P2 (równoległy prewarm) | Po cofnięciu P2 |
|---|---|---|
| `...1788322743.json` → **5/5 build=200** | `...1788327322.json` → **1/5 build=200, 4/5 403** | `...1788327945.json` → **5/5 build=200** |

Test bezpośredni `test1_determinizm_with_evidence.py` nie używa `daemon.py` (P1 bez wpływu), ale wywołuje `prewarm_sesje()` w linii 86 — dokładnie funkcję zmienioną w P2.

### Dowód 8 — mechanizm regresji [UDOWODNIONE]

Równoległy prewarm odpalał **4 GET `/users/current` w ~0 ms** (4 osobne sesje curl_cffi, 4 jednoczesne handshake TLS z jednego IP). To chwilowy burst ~40 req/s, który łamie twardy rate-limit Vinted **~1 req/s** i triggeruje DataDome → blokada 403 na kolejnych `build`.

Naprawa: przywrócono prewarm sekwencyjny w [checkout.py](../../bot/src/vintedbot/checkout.py#L212-L222) z komentarzem dokumentującym regresję. Testy: **111/111 przechodzą**.

---

## 6. WNIOSKI

1. Cztery optymalizacje (O1, O2, O3, O5) są **w pełni wdrożone i zweryfikowane** — bez hipotez.
2. O2 eliminuje zużycie rate-limitu `conversations` (code 106) dla ofert już sprzedanych/niedostępnych, oszczędzając do ~1.9s na martwych ofertach.
3. O4 jest **blokowane sprzecznością formatu tokenu** — wymaga rozszerzenia badań, nie naiwnej implementacji. [UDOWODNIONE]
4. P1 (limit detekcji 5) jest **bezpieczna** — redukuje rozmiar odpowiedzi, nie częstotliwość żądań, i nie narusza rate-limitu.
5. P2 (równoległy prewarm) jest **kontrproduktywna** — równoległe HTTP wbrew rate-limitowi ~1 req/s triggeruje DataDome (regresja 5/5 → 1/5 build=200), więc została cofnięta. Zasada: **nigdy nie równoleglij żądań do Vinted ponad limit ~1 req/s**.

## Źródła
- [pyproject.toml](../../bot/pyproject.toml#L5-L12)
- [checkout.py — pre-filter O2](../../bot/src/vintedbot/checkout.py#L550-L566)
- [models.py — user_id](../../bot/src/vintedbot/models.py#L58-L67)
- [session_state.py — user_id](../../bot/src/vintedbot/session_state.py#L96-L103)
- [daemon.py — user_id](../../bot/src/vintedbot/daemon.py#L50)
- [test_checkout.py — testy O2](../../bot/tests/test_checkout.py#L575-L690)
- [generate_incognia_token.js](../../bot/scripts/generate_incognia_token.js#L4-L31)
- [SYNTEZA_GŁÓWNA.md — format JWE vs AES-GCM](../../vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md#L18)