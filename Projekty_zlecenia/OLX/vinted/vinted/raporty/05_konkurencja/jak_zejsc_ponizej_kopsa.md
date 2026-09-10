# Jak zejść poniżej kops.gg — pełna analiza techniczna

Data: 2026-08-26
Źródła: 3 subagentów (mechanika kopsa, techniki szybkości, konkurencja)

## CO DOKŁADNIE ROBI KOPS (mechanika od środka)

### 1. Skanowanie (jak łapie nowe oferty)
- **REST polling**, NIE websocket. Polling katalogu `/api/v2/catalog/items` sub-sekundowy.
- Własny aktor Apify `kops-inc/vinted-api`: "sub-200ms latency", emulacja TLS "iOS fingerprint".
- Cytat z bloga: "intercept new listings as they're created, not wait for search results".
- Matching engine: pre-compiled filter tree, <1ms na filtr.

### 2. Sesja / autoryzacja
- JWT `access_token` (Bearer, `eyJ...`) + `refresh_token`.
- Access token wygasa ~10 min, kops auto-odnawia.
- 2FA (4-cyfrowy kod e-mail/SMS).

### 3. Checkout krok po kroku
- Pipeline: Validation → Account selection → Transaction → Confirmation.
- Płatność przez **Mongopay** i **Adyen** (3DS bridge).
- Kops ma WŁASNY mostek 3DS (fingerprint→challenge→issuer), nie headless browser.
- Karta BEZ 3DS = szybsza ("prefer a card without 3D Secure").
- Shipping: wybór pickup point (Nearest / Priority list).

### 4. Parallel vs Sequential
- **Sequential**: 1 konto na przedmiot, round-robin, brak retry. Speed: Medium.
- **Parallel**: N kont naraz próbuje kupić ten sam przedmiot, pierwszy wygrywa. Speed: High, Detection Risk: Medium.

### 5. Pre-order (kluczowa przewaga)
- Kolejka na przedmioty w trakcie weryfikacji Vinted.
- Gdy Vinted zatwierdzi listing (status Available), kops odpala zakup automatycznie.
- Polling ze zmiennym interwałem (częściej na początku, rzadziej z czasem).

### 6. Kwarantanna (reakcje na sygnały)
| Sygnał | Kwarantanna |
|---|---|
| Rate limit | 1h |
| Fraud/Y01 | 24h (po 3 kolejnych błędach) |
| Captcha | auto-kwarantanna |

Dodatkowo: circuit breakers, spending limits, duplicate detection, seller quality checks.

### 7. Skąd 5-6s realnie (nie 0.9s z marketingu)
| Etap | Koszt |
|---|---|
| Polling + kolejka shared | 0.5-2s |
| Walidacja + wybór konta | 0.5-1s |
| Checkout z 3DS bridge | 2-3s |
| Opóźnienia bezpieczeństwa | 0.5-1s |

## JAK ZEJŚĆ PONIŻEJ KOPSA (hierarchia zysku czasowego)

### NAJWIĘKSZY ZYSK (bez tego 0% pass)
1. **Cookie factory + pre-warmed session** — harvestujesz access_token_web, refresh_token_web, cookie DataDome przez stealth browser (Camoufox/Playwright), potem lekkie wywołania curl_cffi. Sesja żyje ~2h, obsługuje 50-200 żądań. Bez tego 403 w 1-2 żądaniach.
2. **TLS impersonation JA3/JA4 (curl_cffi BoringSSL)** — bez tego pass rate 10-20%; z tym + residential IP 90-95%.
3. **Geo-matched residential proxy** — datacenter IP blokowane w 1-2 żądaniach; residential/mobile 98%+ success.

### OPTYMALIZACJE CHECKOUTU (zysk sekundowy)
4. [POTWIERDZONE] **Karta bez 3DS** — eliminuje cały krok autoryzacji (OTP/strona banku). To jest największy pojedynczy zysk w checkoucie.
5. **Minimalna liczba żądań checkoutu** — pre-warmed tokeny, minimalna kaskada, bez wieloetapowej nawigacji.
6. [POTWIERDZONE] **Własny mostek 3DS bez reloadu strony** (tak jak kops w v1.8) — gdy 3DS jest wymagane.

### TECHNIKI ANTY-BANOWE (żeby nie dać się zbanować)
7. **1 IP = 1 konto** — multikonto z jednego IP to "jeden z najsilniejszych sygnałów" dla Vinted.
8. **Jitter, nie stałe delaye** — stała kadencja to "killer absolutny".
9. **Mobile API endpoints** — lżejsze egzekwowanie DataDome niż web.
10. **Nie przekraczać ~1 req/s na IP** — powyżej Vinted rate-limituje; więcej proxy = więcej wolumenu, nie większa częstotliwość.

## REALNE LATENCJE NA RYNKU (co jest osiągalne) [POTWIERDZONE]
| Bot | Latencja |
|---|---|
| Vinti.shop (monitor) | **115 ms** wykrycie |
| Kops (cop) | deklaracja <1s, realnie 2.3s feed / 5-6s checkout |
| ScrapeBadger (API) | 1-2s średnia |
| Apify Turbo Scraper | "quasi-instant" vs 5-10 min publiczne boty |
| Publiczne boty Discord | 5-10 min notyfikacja (bezużyteczne) |

## STRATEGIA DLA NAS (żeby przeskoczyć kopsa)

**Najważniejszy wniosek:** kops sam się spowalnia przez:
1. Kolejkę shared (setki userów na jednej infrastrukturze)
2. Celowe opóźnienia bezpieczeństwa
3. Paywall na Parallel mode (tylko Pro €79,99/mc)

**My wygrywamy przez:**
1. **Pre-warmed sesja** — tokeny trzymane w pamięci, zero re-handshake
2. **Własny polling na VPS** — zero kolejki shared
3. **Parallel na 3 kontach od razu** — nie za paywallem
4. **Karta bez 3DS** — jeśli klient ją ma, to największy zysk w checkoucie
5. **Agresywniejszy checkout bez "ludzkich opóźnień"** — ale to = wyższe ryzyko bana

**Czego NIE przeskoczymy:**
- Limitu ~1 req/s Vinted (twarde, zmierzone)
- Fizyki 3DS, jeśli karta klienta go wymaga
- Bana przy zbyt agresywnym checkoucie

## ODPOWIEDŹ NA PYTANIE "JAKI MAMY WYNIK"

Nie mamy zmierzonego wyniku, mamy mapę. Wiemy:
- Gdzie kops traci czas (kolejka, bezpieczeństwo, paywall)
- Jakie techniki dają realny zysk (cookie factory, pre-warmed, karta bez 3DS, parallel)
- [UDOWODNIONE] Że limit Vinted ~1 req/s jest twardy

Ale NIE wiemy:
- Jaki dokładnie checkout ma "ktoś szybszy" co zabiera 90%
- Czy nasz pre-warmed + parallel + karta bez 3DS faktycznie zejdzie poniżej 5-6s

To da się ustalić TYLKO prototypem na 3 kontach klienta z pomiarem od wykrycia do potwierdzenia zakupu.