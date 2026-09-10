# Vinted Bot — przebudowa MVP na czysty curl_cffi (firefox135)

> Data: 2026-08-31 · Status: spec do zatwierdzenia

## 1. Cel

Przebudować moduł `vinted/bot/` tak, aby **cała ścieżka zakupowa była w 100%
przez `curl_cffi` (impersonacja `firefox135`)**, z wykorzystaniem nowo odkrytych
rozwiązań (nowy endpoint transakcji, karta jako metoda płatności), i **usunąć
przestarzałe podejście oparte o Camoufox** w ścieżce zakupowej.

Efekt: działające MVP = monitoring ofert + wykrycie + rezerwacja (build) +
opcjonalna próba payment, na **1 koncie**, przez **CLI**, bez przeglądarki
w krytycznej ścieżce.

## 2. Kontekst i nowo odkryte rozwiązania (udowodnione w `testy_camoufox/`)

Poniższe fakty są podstawą tej przebudowy (potwierdzone pomiarem w
`flow_optimized.py` oraz dokumentacji inżynierskiej):

1. **Stealth działa na `firefox135`** (wbudowany profil curl_cffi), nie na
   `chrome`. Flow przechodzi `checkout/build` z 200.
2. **Nowy endpoint transakcji** `POST https://api.vinted.pl/messaging/main/inquiries`
   zwraca `transaction_id`, zastępując `POST /api/v2/conversations` (unika 429).
3. **Metoda płatności: karta (`pay_in_method_id = "1"`)** zamiast Przelewy24
   (`"12"`). Mapa metod pochodzi z odpowiedzi `checkout/build`
   (`components.payment_method.pay_in_methods`).
4. **Token Incognia** (`x-incognia-request-token`) generowany przez Node.js
   (`generate_incognia_token.js`, AES-GCM z HKDF klucza `sdk_instance_id`
   pobieranego z `GET https://api.vinted.pl/j3r4zw/v1/config`).
5. **`checksum`** łapany rekurencyjnie z odpowiedzi (`_find_checksum`); wartość
   jest postaci `"a|b"` (jedna para, nie lista).
6. Sekwencja zakupowa działa w całości przez curl_cffi:
   `inquiries → build → [PUT payment_method ∥ GET pickup_points] → PUT pickup_details → payment`.

## 3. Co wywalamy (przestarzałe, wyparte)

| Element | Powód |
|---|---|
| `checkout.py`: `zarezerwuj()` przez Camoufox + `el.click()` (Faza A) | ścieżka zakupowa = 100% curl_cffi |
| `checkout.py`: cache kontekstów Camoufox (`_contexty`, `_get_context`, `_czy_prewarm_wymagany`, `cleanup_stale_contexts`, wątek czyszczenia) | jw. |
| `checkout.py`: `zarezerwuj_api()` — `impersonate="chrome"`, brak tokena Incognia, stary endpoint | nie przechodziło builda |
| `detection.py`: `impersonate="chrome"` | wyparte przez `firefox135` |
| `cli.py`: wybór `--engine api/browser` | zostaje tylko `api` (curl_cffi) |
| `measurement.py`: `CheckoutTimer` powiązany z wyborem silnika | zastąpiony pomiarem kroków checkoutu |
| zależność `camoufox` z `pyproject.toml` | nie jest już używana w ścieżce zakupowej |

## 4. Nowa struktura modułów

```
bot/src/vintedbot/
├── config.py        # stałe: CSRF, ANON, IMPERSONATE="firefox135", PAY_IN_METHOD="1",
│                    # ścieżki (cookies, node script), URL-e endpointów
├── models.py        # Filtry, Oferta, KonfiguracjaKonta, WynikCheckoutu
├── detection.py     # monitoring ofert (firefox135) + inquiries (nowy endpoint)
├── incognia.py      # token Incognia przez Node.js (subprocess)
├── checkout.py      # sekwencja zakupowa curl_cffi (build → payment)
├── measurement.py   # LatencyRecorder + StepTimings (czasy per krok checkoutu)
└── cli.py           # monitor / autocop / bench / keepalive
```

### 4.1 `config.py`

Stałe i ścieżki konfiguracyjne. Wartości wrażliwe (CSRF, anon_id, ścieżki cookies)
czytane z env lub stałych domyślnych, tak jak obecnie `_DEFAULT_CSRF`.

```python
IMPERSONATE = "firefox135"
PAY_IN_METHOD = "1"          # karta
CSRF_DEFAULT = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON_DEFAULT = "98c6af5a-87da-45f2-9be5-24cf9345b003"

INQUIRIES_URL = "https://api.vinted.pl/messaging/main/inquiries"
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CHECKOUT_BASE = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout"
PAYMENT_URL = "https://www.vinted.pl/api/v2/purchases/{checkout_id}/checkout/payment"
SDK_CONFIG_URL = "https://api.vinted.pl/j3r4zw/v1/config"
```

### 4.2 `models.py`

- `Filtry` — bez zmian (brand_ids, size_ids, status_ids, search_text, price_from/to).
- `Oferta` — bez zmian.
- **nowe** `KonfiguracjaKonta`: `csrf`, `anon_id`, `impersonate`, `cookies` (dict).
- **nowe** `WynikCheckoutu`: `purchase_id`, `checkout_id`, `transaction_id`,
  `status_build`, `status_payment_method`, `status_pickup_details`,
  `status_payment`, `payment_status`, `redirect_url`, `error_code`,
  `timings` (dict krok→ms).

### 4.3 `detection.py`

Zachowuje `pobierz_oferty`, `monitoruj`, `wczytaj_cookies`, `odswiez_token`,
`utrzymuj_sesje`, `_nastepny_interwal`, `_sesja_aktywna`. Zmiany:
- wszędzie `impersonate = firefox135` (z config),
- nowa funkcja `utworz_transakcje(item_id, seller_id, konto)` →
  `POST /messaging/main/inquiries`, zwraca `transaction_id`.

### 4.4 `incognia.py`

```python
def sdk_instance_id() -> str: ...        # GET /j3r4zw/v1/config
def wygeneruj_token(sdk_id: str) -> str:  # node generate_incognia_token.js <sdk_id>
```

Wydzielone z checkout, bo to osobna odpowiedzialność (kryptografia Incognia
przez zewnętrzny proces Node.js) i łatwo mockować w testach.

### 4.5 `checkout.py`

Jedna publiczna funkcja spinająca sekwencję:

```python
def zrealizuj_zakup(item_id, seller_id, konto, *, proba_payment: bool = False) -> WynikCheckoutu
```

Sekwencja:
1. `utworz_transakcje` → `transaction_id`
2. `build(transaction_id, token)` → `checkout_id`, `checksum`, `rate_uuid`, `shipping_order_id`, koordynaty
3. równolegle (`ThreadPoolExecutor`): `PUT payment_method` (karta id=1) ∥ `GET nearby_pickup_points`
4. `PUT pickup_details` → nowy `checksum`
5. jeśli `proba_payment`: `POST payment` (checksum + browser_info) → status/redirect

`checksum` zbierany rekurencyjnie (`_find_checksum`). Każdy krok rejestruje czas
w `StepTimings`. Brak zależności od Camoufox.

### 4.6 `measurement.py`

- `LatencyRecorder` — bez zmian.
- **usunąć** `CheckoutTimer`.
- **nowe** `StepTimings`: rejestruje czas każdego kroku checkoutu (`dict[str,float]`
  ms) + `suma`.

### 4.7 `cli.py`

- `monitor` — bez zmian (filtry + cookies).
- `autocop` — **bez wyboru silnika**; zawsze curl_cffi. Opcje:
  - `--brand`, `--search`, `--max-iter`
  - `--cookies` (wymagany do zakupu)
  - `--no-checkout` (tylko wykrywaj)
  - `--payment` (flaga: spróbuj dojść do próby payment; domyślnie **wyłączone** = tylko rezerwacja)
- `bench` — bez zmian.
- `keepalive` — bez zmian.

## 5. Przepływ danych (`autocop`)

```
monitoruj(filtry) ─ wykryje nową ofertę → callback
  → utworz_transakcje(item_id, seller_id) → transaction_id
  → build(transaction_id, token) → checkout_id + checksum + rate_uuid + coords
  → [PUT payment_method(karta id=1) ∥ GET pickup_points]   (równolegle)
  → PUT pickup_details → checksum'
  → (tylko gdy --payment) POST payment → status/redirect
  → WynikCheckoutu (purchase_id, statusy, czasy per krok)
```

## 6. Obsługa błędów

- `build != 200` → przerywa, zwraca `WynikCheckoutu` z `status_build` i `error_code`.
- Brak `transaction_id` / `checkout_id` / `checksum` → przerywa z komunikatem.
- `payment` = 400 (code 99 / 114) → nie przerywa, zapisuje `status_payment`/`error_code`
  (znany stan niedomkniętego zakupu — karta wymaga rejestracji Adyen, P24 ma inny checksum).
- Token Incognia: błąd Node.js → `RuntimeError`, propagowany do CLI.

## 7. Testowanie

Zaktualizować istniejące testy w `bot/tests/` i dodać nowe. Zasada:
mockować **wyłącznie HTTP/sieć** (i subprocess Node.js), nigdy wewnętrzne klasy.

- `test_models.py` — `KonfiguracjaKonta`, `WynikCheckoutu` (bez zmian do Filtry/Oferta).
- `test_detection.py` — `monitoruj` deduplikacja, `utworz_transakcje` buduje poprawne body/URL.
- `test_checkout.py` — `zrealizuj_zakup` z mockowanym HTTP: weryfikuje kolejność kroków,
  parsowanie `checksum`, flagę `proba_payment` (payment wywołane tylko gdy True).
- `test_incognia.py` — `wygeneruj_token` wywołuje node z właściwym argumentem (mock subprocess).
- `test_cli_e2e.py` — `CliRunner` + mock HTTP: `autocop --no-checkout` i `--payment`.

## 8. Zakres jawnie wykluczony (poza tym MVP)

- Multikonto (3–4 konta) / proxy rezydencjalne / anty-ban (Faza M7 roadmapy).
- Filtr kategorii przez SSR HTML (Faza M6).
- Rejestracja karty Adyen / 3DS / finalizacja realnego zakupu.
- Losowe opóźnienia humanizacyjne.
- Web UI / panel (zostaje CLI).
- Screenshot dowodowy (Camoufox jako renderer) — obecny w `testy_camoufox/`, nie w `bot/`.

## 9. Definicja sukcesu

- `vinted/bot` działa bez zależności `camoufox`.
- `autocop --no-checkout` wykonuje pełną ścieżkę do `build` (200) przez czysty curl_cffi
  i zwraca `purchase_id` z czasami per krok.
- `autocop --payment` dochodzi do kroku `payment` i zapisuje jego status.
- Testy przechodzą bez mockowania wewnętrznych klas.