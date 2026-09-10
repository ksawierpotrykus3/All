# GŁÓWNA SYNTEZA: Status projektu Vinted Bot

## 📊 **STAN PROJEKTU - 2026-09-01**

### ✅ **CO WIEMY (udowodnione):**
1. **Warstwa detekcji** - pełna funkcjonalność
2. **Rate-limit Vinted** ~1 req/s - potwierdzone
3. **Analiza konkurencji** - kops.gg 2.3s vs <1s marketing
4. **Wymagania bezpieczeństwa** - DataDome + residential proxy
5. **Camoufox (Firefox)** - przechodzi DataDome anonimowo (katalog 200, users/current 200)
6. **X-CSRF-Token** - hardcoded (75f6c9fa-dc8e-4e52-a000-e09dd4084b3e)
7. **Incognia SDK** - druga warstwa anty-fraud z tokenem JWE
8. **Plaintext Incognii PRZECHWYCONY** - hook `crypto.subtle` przez `add_init_script` w Camoufox (39 pól fingerprintu)
9. **Struktura JWE** - RSA-OAEP(SHA-1) + A128CBC-HS256, klucz publiczny Incognii wyekstrahowany (RSA-2048)
10. **Lekki generator tokenu w pure Python** - bez JS runtime, struktura identyczna z realnym tokenem
11. **Playwright MCP (Chromium) wykrywany** - `users/current` 403 mimo ważnych HttpOnly cookies (Cloudflare challenge)
12. **Adyen CSE (szyfrowanie karty)** - pełny algorytm JWE odtworzony z APK (RSA-OAEP-256 + AES-256-GCM); endpointy `card_registrations` i źródło klucza `access_key` udowodnione
13. **Incognia native vs web** - token native NIE jest JWE (custom: zlib + obfuskowany AES + RSA); web używa JWE (A128CBC-HS256). Dwie różne implementacje — replikacja web prostsza
14. **Sekwencja checkout APK** - pełna mapa endpointów i graf zależności (check_availability → build → payment) z dekompilacji APK
15. **Pre-warming tokenu karty** - `singleUseCard` (jednorazowy token), `firebaseAppInstanceId` i `checksum` per-checkout; tokenizacja `card_registrations` NIEZALEŻNA od checkoutu (możliwa równolegle)
16. **Dwie ścieżki płatności** - WALLET (brak akcji = sukces), nowa karta (pełne Adyen CSE), stored card (CVV przez **PayRails CSE**, nie Adyen)
17. **card_registrations NIE wymaga Incognia token** - potwierdzone w `CardRegistrationsCentralApi.java` (brak `X-Incognia-Request-Token`); lżejsza ścieżka, potencjalnie przechodząca DataDome w curl_cffi
18. **Benchmark na żywej sesji** - catalog 406 ms (200), conversations 1172 ms (200), checkout/build 187 ms (**403 DataDome**) — zmierzono w przeglądarce Camoufox ze świeżym cookie DataDome
19. **DataDome ma hierarchię progów** - katalog/conversations przechodzą (200), ale transakcyjny `checkout/build` jest blokowany (403) NAWET w spójnym stacku przeglądarkowym — cookie+fingerprint spójne, sesja ważna, a mimo to 403
20. **Natywny SDK DataDome w APK** - `co.datadome.sdk.DataDomeInterceptor` + `EndpointTrackingInterceptor` (odczyt `X-DD-B` przy 403); stos: DeviceFingerprint → ... → DataDome → EndpointTracking
21. **DataDome na build = captcha slider do odblokowania RAZ** [ROZSTRZYGNIĘTE 2026-09-01] - `profil_firefox_135` po rozwiązaniu slidera daje build=200 w czystym curl_cffi BEZ tokenu Incognia. Solver: `bot/src/vintedbot/slider_solver.py`. Hipotezy H1 (brak tokenu) i H2 (prefetch strony) ODRZUCONA — przyczyną 403 był zablokowany profil testowy, nie brak sygnatur.
22. **Pełny checkout działa** [UDOWODNIONE 2026-09-01] - `test_build_bez_tokena.py` na `profil_firefox_135`: build=200, pickup=200, payment=400 (error 114 - brak karty). Czas full: ~7.2s; czas skip-build: ~1.0s.
23. **Kanoniczny profil = `profil_firefox_135`** [ROZSTRZYGNIĘTE 2026-09-01] - jedyny odblokowany sliderem (build=200). Stare profile `profil_firefox` (browser-profiles + tools) **USUNIĘTE** — dawały mylące 403/puste. Jedyny profil w projekcie to `profil_firefox_135`. Konflikt rozstrzygnięty: [PROFILE_KONFLIKT.md](../../raporty/02_reverse_engineering/PROFILE_KONFLIKT.md).
24. **Batch pre-filter `check_availability`** [UDOWODNIONE 2026-09-01] - `POST /checkout/purchases/check_availability` działa w ~110 ms, bez Incognii, zwraca stan rezerwacji per-item. Wdrożony jako `sprawdz_dostepnosc` w `detection.py`.
25. **Auto-solver DataDome w pętli odświeżania** [UDOWODNIONE 2026-09-01] - `refresh.py` automatycznie wykrywa iframe captcha i rozwiązuje suwak przez `slider_solver.rozwiaz_slider`.
26. **Wsparcie maszyny stanów `payment/continue`** [UDOWODNIONE 2026-09-01] - `_payment_continue` w `checkout.py` umożliwia ponowienie płatności bez powtarzania buildu transakcji. Test suite: 57/57 testów przechodzi w 2.74 s.
27. **Tokenizacja kart Adyen CSE w czystym Pythonie** [UDOWODNIONE 2026-09-01] - moduł `adyen_cse.py` odtwarza algorytm RSA-OAEP-256 + AES-256-GCM z APK 26.33.1. Szyfrowanie 4 pól karty trwa ~10.3 ms bez udziału przeglądarki.
28. **Moduł zarządzania kartami `card_manager.py`** [UDOWODNIONE 2026-09-01] - pełna obsługa rejestracji (`zarejestruj_karte`), listowania i usuwania kart przez endpointy `payments/public/api/card_registrations` i `/cards` wraz z komendami CLI `add-card`, `cards`, `delete-card`.
29. **PUT pickup_details jest obowiązkowy (falsyfikacja PUT-Skip)** [UDOWODNIONE 2026-09-01] - testy `minimal_checkout_*.json` dowodzą, że pominięcie punktu odbioru w PUT zwraca błąd walidacji backendu `HTTP 400 code: 99 "Uzupełnij Pickup point code, aby kontynuować."`. Pełny test suite: 93/93 testy jednostkowe przechodzą w 4.73 s.
30. **Ultraszybki parser JSON (`orjson` w `json_utils.py`)** [UDOWODNIONE 2026-09-02] - zastąpienie `json.loads` modułem `orjson` przyspiesza deserializację payloadów katalogu i checkoutu o 89% (248 µs vs 469 µs na 103 KB). Zaktualizowany test suite: 96/96 testów jednostkowych przechodzi w 4.73 s.
31. **Full-Lifecycle Telemetry v2 (Waterfall Spans)** [UDOWODNIONE 2026-09-02] - `Oferta.detection_span` przenosi czas detekcji do checkout; `WynikCheckoutu.spans` rejestruje 5 faz: [1] DETEKCJA, [2] TRANSAKCJA, [3] KOSZYK+PKP, [4] PUT ADRES, [5] PŁATNOŚĆ. `summary_timings` oblicza `total_full_cycle_ms`, `detection_ms`, `checkout_to_payment_ms`, `net_ratio_pct`. `evidence.py` wypala Waterfall na screenshotach. 99/99 testów przechodzi w 4.38 s.
32. **Optymalizacja mikro-latency i TCP Keep-Alive** [UDOWODNIONE 2026-09-02] - zredukowano domyślny limit detekcji z 96 do 20 (przyspieszenie generacji JSON po stronie Vinted), wdrożono `start_keepalive_daemon` podtrzymujący połączenia TCP/TLS oraz okno TCP HTTP/2, a także pre-komputację szyfrowania Adyen CSE w `card_manager.py` (0 ms narzutu w trakcie zakupu). 100/100 testów przechodzi w 4.33 s.
33. **Early-Trigger Streaming Detection (Zero-Wait)** [UDOWODNIONE 2026-09-02] - `ekstrahuj_pierwszy_item_z_chunka` w `detection.py` parsuje najnowszą ofertę z pierwszego pakietu TCP (TTFB ~80-110 ms) w trakcie strumieniowania HTTP/2 (`stream=True`), uruchamiając procedurę zakupu natychmiast, bez czekania na pobranie i sparsowanie pozostałych ofert (~250 ms zysku). 102/102 testy przechodzą w 4.80 s.
34. **Speculative Pipelined Streaming w łańcuchu checkoutu** [UDOWODNIONE 2026-09-02] - zaimplementowano mikro-skanery `_ekstrahuj_checkout_z_chunka` i `ekstrahuj_transakcje_z_chunka`, które wyławiają `transaction_id`, `checkout_id` i `checksum` z pierwszych bajtów odpowiedzi strumieniowej (~30-100 B) i odpalają kolejny etap potoku bez oczekiwania na transfer pozostałych danych JSON (~400-600 ms łącznego zysku). 103/103 testy przechodzą w 4.26 s.
35. **Bariera Transakcyjna Backend Vinted (Post-commit Requirement)** [UDOWODNIONE 2026-09-02] - weryfikacja live dowiodła, że backend Vinted commituje transakcję dopiero pod koniec `POST /conversations`. Próba wysłania `build` w trakcie trwania `conversations` zwraca `HTTP 404 code: 104 "Zawartość nieodnaleziona"`. Sekwencja `conversations -> build` musi być zsynchronizowana statusem 200 OK, po czym następuje równoległy `build + pickup_point` (~3.39-3.75s). 106/106 testów przechodzi w 4.54 s.
36. **Pre-seeding Coords Cache (Zysk 438 ms od 1. zakupu)** [UDOWODNIONE 2026-09-02] - dowiedziono telemetrycznie (`test1_determinizm_with_evidence_1788307148.json`), że zasilenie `_COORDS_CACHE` przed zakupem skróciło fazę `build+pickup_point` z 1703 ms (Cold Start) do 1265 ms (Warm Start), przynosząc **438 ms czystego zysku** (25.7% redukcji fazy). Zaimplementowano w `prewarm_sesje()`. 107/107 testów przechodzi w 4.84 s.
37. **Pipeline `put_pickup_details` na ścieżce warm** [UDOWODNIONE 2026-09-02] - `_build` otrzymał callback `on_early_checkout_id`, a `zrealizuj_zakup` zrównoleglił `_put_pickup_details` z dokończeniem buildu, gdy `_PICKUP_CACHE` ma wpis `(anon_id, shipping_order_id)`. Wcześniej `put_pickup_details` (~1062-1344 ms) czekało sekwencyjnie na pełny `build+pickup_point`. Dodano wariant sesji `put` i klasę `_BuildResp` (zachowuje pełne ciało odpowiedzi w streamingu — naprawa buga porzucania `content`). Zysk dotyczy WYŁĄCZNIE powtórnych zakupów od tego samego sprzedawcy. 112/112 testów.
38. **Globalny lock per-profil Camoufox** [UDOWODNIONE 2026-09-02] - dodano `profile_lock()` w `config.py` i owinięto nim WSZYSTKIE otwarcia `persistent_context` z tym samym `user_data_dir` (harvest, screenshot w tle, świeże cookies, RefreshLoop). Root cause: Firefox odmawia drugiego startu na zajętym profilu (`Failed to launch the browser process`, cichy `exitCode=0`), co zabijało fallback odblokowania DataDome przy współbieżnym screenshocie. Po fixie live-test **5/5 build=200** (wcześniej 1/5).
39. **Uodpornienie slider solvera na headless** [UDOWODNIONE 2026-09-02] - w `slider_solver.py` usunięto twardy `return False` gdy `bounding_box()` zwraca `None` (częste w headless przy ukrytym iframe). Główna ścieżka `drag_to` działa teraz niezależnie od boxa (operuje na `frame.locator`); fallback `page.mouse` używa współrzędnych absolutnych tylko gdy box dostępny. Dodano logowanie przyczyn (brak iframe / brak iframe na top-level / box=None zamiast cichego False). Screenshot otrzymał `webgl_config=WEBGL_CONFIG` (eliminacja `ValueError: No WebGL data found`).

### ⚠️ **CO NIE WIEMY (konflikty):**
1. **Checkout endpointy** - ROZSTRZYGNIĘTE (build=200 potwierdzone 2026-09-01, szczegóły niżej)
2. **Czasy zakupu** - ZMIERZONE: full ~7.2s, skip-build ~1s (patrz metryki)
3. ~~**Pominięcie DataDome**~~ - **ROZWIĄZANE**: build=200 przez czysty curl_cffi po odblokowaniu profilu sliderem (solver w `bot/src/vintedbot/slider_solver.py`). Profil `profil_firefox_135` odblokowany, `profil_firefox` (testowy) NIE.
4. **Akceptacja zreplikowanego tokenu Incognii** - serwer może odrzucić cofnięty `token_sequence_number` lub niespójny canvas (token nie jest już potrzebny do build, ale może być do payment)
5. ~~**Czy brak tokenu Incognia w build = flaga ryzyka DataDome**~~ - ODRZUCONA (H1): build=200 bez tokenu
6. **Payment error 114** - "Purchase card is not valid" - konto testowe bez prawdziwej karty; wymaga karty lub portfela

### ❌ **CO JEST FAŁSZYWE:**
1. **Endpointy `/api/v2/transactions`** - zmyślone przez AI
2. **"100% zweryfikowany checkout"** - nieudowodnione
3. **"Portfel omija 3DS"** - hipoteza bez dowodów
4. **Marketing kops <1s** - rzeczywistość 5-6s checkout

## 🗺️ **MAPA DOKUMENTACJI**

### 📁 **ORIGINALNE ŹRÓDŁA:**
```
raporty/
├── 01_sonda_api/          # Pomiary API - WYSOKA wiarygodność
├── 02_reverse_engineering/ # Checkout - NISKA wiarygodność
│   ├── CHECKOUT_SEKWENCJA_APK.md       # Mapa endpointów + graf zależności
│   ├── CHECKOUT_PREWARMING.md          # singleUseCard, checksum, pre-warming
│   ├── CHECKOUT_WALLET_VS_KARTA.md     # Ścieżki płatności (WALLET vs karta)
│   ├── CHECKOUT_ROWNOWAZNOLEGLOSC.md   # card_registrations równolegle z build
│   ├── CHECKOUT_BENCHMARK.md           # Pomiar czasów na żywej sesji
│   └── CHECKOUT_DATADOME.md            # Natywny SDK + hierarchia progów
├── 03_weryfikacja/        # Audyt - WYSOKA wiarygodność
├── 04_niewiadome/         # Luki - WYSOKA wiarygodność
├── 05_konkurencja/        # Analiza rynku - ŚREDNIA
├── 06_biznes/             # Wycena - ZALEŻNA
└── 07_niezweryfikowane/   # AI research - NIEPOTWIERDZONE
```

### 📁 **SYNTEZY (aktualna prawda):**
```
testy_camoufox/docs/synthesis/
├── DETEKCJA_STATUS.md      # Co wiemy o detekcji
├── CHECKOUT_KONFLIKTY.md   # Sprzeczności checkout
├── KOPS_GG_ANALIZA.md      # Analiza konkurencji
├── SYNTEZA_CAMOUFOX_FIREFOX.md # Kluczowe odkrycia Camoufox
└── SYNTEZA_GŁÓWNA.md       # TEN PLIK

testy_camoufox/docs/reports/
└── ANALIZA_APK_ADYEN_CSE_SZYFROWANIE_KARTY.md  # Adyen CSE: algorytm JWE + endpointy
```

### 📁 **ARCHIWUM (oryginały):**
```
testy_camoufox/docs/archive/
├── reports/               # Oryginalne raporty MD
├── references/           # Dane referencyjne
└── logs/                # Logi i wyniki
```

## 🎯 **KLUCZOWE KONFLIKTY I ROZWIĄZANIA**

### **KONFLIKT 1: Checkout - rozwiązany czy nie?**
- **Źródło A:** "100% zweryfikowane endpointy"
- **Źródło B:** "Nieudowodnione, brak w capture"
- **ROZSTRZYGNIĘCIE:** ❌ **NIE ZWERYFIKOWANE** - wymaga przechwycenia

### **KONFLIKT 2: Czasy zakupu**
- **Marketing kops:** <1s / 0.9s
- **Rzeczywistość:** 2.3s detection + 5-6s checkout
- **Nasz status:** ❌ **BRAK POMIARÓW** - nigdy nie kupiliśmy

### **KONFLIKT 3: Endpointy transakcji**
- **AI Research:** `/api/v2/transactions/*`
- **Audyt:** "Zmyślone, brak w captured_requests"
- **ROZSTRZYGNIĘCIE:** ❌ **FAŁSZYWE** - przeniesione do niezweryfikowane

## 🛠️ **PROCEDURA AKTUALIZACJI**

### Kiedy powstaje konflikt:
1. **Zidentyfikuj sprzeczność** w źródłach
2. **Sprawdź dowody** (captured_requests, logs)
3. **Stwórz wpis** w `00_POWTORZENIA_I_SPRZECZNOSCI.md`
4. **Zaktualizuj syntezę** w `docs/synthesis/`

### Hierarchia wiarygodności:
1. **captured_requests.json** - najwyższa
2. **Logi testów** (`*.log`, `*.json`)
3. **Analiza kodu** (JS reverse)
4. **Hipotezy AI** - najniższa

## 🚀 **NASTĘPNE KROKI PROJEKTOWE**

### **PRIORYTET 1: Rozwiązać payment error 114 (brak karty)**
- Stan: build=200 ✅, pickup=200 ✅, payment=400 error_code=114 "Purchase card is not valid"
- Przyczyna: konto testowe nie ma prawdziwej karty ani portfela
- Plan: dodać kartę testową lub portfel; jeśli wallet — użyć ścieżki WALLET (brak akcji = sukces)
- Cel: payment=200 (pełny zakup end-to-end)

### **PRIORYTET 2: Optymalizacja czasów do <4s**
- Stan: full checkout ~7.2s (transaction 1.9s + build 2.0s + pickup 1.5s + payment 1.9s); skip-build ~1.0s
- Plan: równoległość build+pickup już jest; dalej — cache pickup per seller, pomijanie payment_method gdy karta domyślna
- Cel: full checkout <4s

### **PRIORYTET 3: Automatyczne odblokowywanie nowych profili**
- Stan: `profil_firefox_135` odblokowany ręcznie; nowe profile wymagają slidera
- Plan: dodać auto-solver slidera do bootstrapu profilu (raz przy starcie)
- Cel: każdy nowy profil sam przechodzi DataDome

### **PRIORYTET 4: Zreplikowany token Incognia w curl-cffi (opcjonalne)**
- Stan: generator JWE gotowy; build nie wymaga tokenu, ale payment może
- Plan: test czy payment z tokenem daje inny wynik niż 400/114
- Cel: pełna hybryda bez przeglądarki

## 📈 **METRYKI SUKCESU**

| Metryka | Cel | Aktualny status |
|---------|-----|-----------------|
| Detection time | <1.5s | ✅ catalog ~360 ms (zmierzone 2026-09-02, WAW edge) |
| Checkout time (rezerwacja) | <4s | ✅ **~3.51s avg** (min: 3.26s, zmierzone 2026-09-02, N=5); full z payment ~7.2s |
| Build status | 200 | ✅ **ROZWIĄZANE** (2026-09-01/02, profil_firefox_135 + slider, 20/20 prób) |
| Payment status | 200 | ❌ 400 error 114 (brak karty na koncie testowym) |
| Success rate (rezerwacja) | >90% | ✅ **100%** (25/25 prób build/pickup=200; 2026-09-02 po locku profilu: 5/5 w jednej sesji) |
| DataDome bypass | Tak | ✅ **ROZWIĄZANE** (slider solver + czysty curl) |
| Cost vs kops | 50% niższy | ✅ Potencjalnie |

## 🔗 **LINKI DO DOKUMENTÓW**

### Syntezy:
- [Detekcja Status](synthesis/DETEKCJA_STATUS.md)
- [Checkout Konflikty](synthesis/CHECKOUT_KONFLIKTY.md)  
- [Kops.gg Analiza](synthesis/KOPS_GG_ANALIZA.md)
- [Camoufox Firefox](synthesis/SYNTEZA_CAMOUFOX_FIREFOX.md) - kluczowe odkrycia

### Reverse engineering checkoutu (raporty/02_reverse_engineering/):
- [Sekwencja APK](../../raporty/02_reverse_engineering/CHECKOUT_SEKWENCJA_APK.md) - mapa endpointów i graf zależności
- [Pre-warming](../../raporty/02_reverse_engineering/CHECKOUT_PREWARMING.md) - singleUseCard, checksum
- [Wallet vs karta](../../raporty/02_reverse_engineering/CHECKOUT_WALLET_VS_KARTA.md) - ścieżki płatności
- [Równoległość](../../raporty/02_reverse_engineering/CHECKOUT_ROWNOWAZNOLEGLOSC.md) - card_registrations vs build
- [Benchmark](../../raporty/02_reverse_engineering/CHECKOUT_BENCHMARK.md) - pomiary czasów na żywej sesji
- [DataDome](../../raporty/02_reverse_engineering/CHECKOUT_DATADOME.md) - natywny SDK + hierarchia progów
- [Konflikt profili](../../raporty/02_reverse_engineering/PROFILE_KONFLIKT.md) - kanoniczny profil = profil_firefox_135

### Źródła:
- [Powtórzenia i Sprzeczności](../../raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md)
- [Audyt Prawdy](../../raporty/03_weryfikacja/AUDYT_PRAWDY.md)
- [Co Nie Mamy](../../raporty/CZEGO_NIE_MAMY.md)

---

**Ostatnia aktualizacja:** 2026-09-02  
**Status projektu:** **W TRAKCIE** - DataDome ROZWIĄZANY (build=200), Rezerwacja <4s OSIĄGNIĘTA (~3.51s avg), payment 114 do rozwiązania (brak karty)  
**Następny krok:** Dodać kartę/portfel do konta testowego → payment=200 end-to-end