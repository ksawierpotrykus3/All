# Scenariusz weryfikacji MVP (konto testowe kontolastz@wp.pl)

## Warunki wstępne
- Backend wstał (`docker compose up -d`), Stripe w trybie testowym (klucze `sk_test_...`).
- Zainstalowany instalator PROD na czystej maszynie (lub VM) Windows 10/11.
- Konto testowe gry: `kontolastz@wp.pl` (logowanie kodem z e-maila; hasło skrzynki w `docs/klient_rozmowa_umowa.md`).

## Krok 1 — Rejestracja i logowanie
1. `POST /auth/register` z testowym emailem + hasłem 8+ znaków → 200 + access_token.
2. Ponowna rejestracja tego samego emaila → 400 "Email juz zajety".
3. `POST /auth/login` z poprawnymi danymi → 200 + token.
4. `POST /auth/login` z blednym hasłem → 401. Po 10 probach → 429 (rate limit).

## Krok 2 — Subskrypcja Stripe (test mode)
1. Utworz Checkout Session z `customer_email` = email z kroku 1.
2. Oplac testowa karta 4242 4242 4242 4242.
3. Odbierz `checkout.session.completed` webhook → licencja `is_active=True`.
4. Wywolaj `POST /license/validate` z kluczem licencji → `valid: true`.
5. Wywolaj symulowane `invoice.payment_failed` → licencja `is_active=False`, `validate` zwraca `valid: false`.
6. Wywolaj `invoice.paid` → licencja `is_active=True` ponownie.

## Krok 3 — Wiazanie HWID
1. `POST /license/validate` z `license_key` + `hwid` (pierwsze wywolanie) → `valid: true`, HWID zbindowany.
2. To samo z innym `hwid` (komputer B) → `valid: false`, "Licencja przypisana do innego komputera".
3. Admin wywoluje `/admin/licenses/reset-hwid` → ponowne wiazanie nowym `hwid` daje `valid: true`.

## Krok 4 — Start aplikacji PROD i logowanie
1. Uruchom LastZBot.exe (PROD) BEZ `backend_url`/`license_key` w config.json → bot NIE startuje, komunikat "Brak ważnej licencji".
2. Ustaw `backend_url` i `license_key` w config.json → bot startuje, log zawiera "Licencja zweryfikowana poprawnie".
3. Uruchom bota, gdy licencja nieaktywna (cofnij subskrypcje) → bot odmawia startu.

## Krok 5 — Funkcje bota (na koncie testowym)
1. Bot wykrywa okno gry "Survival.exe"; START/STOP dziala; podglad live pokazuje klatki.
2. Symulacja eventu helikoptera (lub realny event) → detekcja → OCR czatu → klikniecie → powrot do czuwania.
3. Logi zawieraja wpisy o wykryciu alertu, odczycie licznika i wykonanych kliknieciach (transparentnosc).

## Krok 6 — DEV vs PROD
1. DEV build (`build.ps1 -Dev` → `LastZBot-Dev-Setup.exe`) → bot startuje BEZ licencji (log "DEV mode: skipping license validation (build mode)").
2. PROD build (`build.ps1` → `LastZBot-Setup.exe`) → bot wymaga licencji (Krok 4).
3. Tryb jest zapieczony w exe w czasie kompilacji (`mvp/build_mode.py` z `BUILD_MODE = 'dev'|'prod'`, generowany przez build.ps1), a nie przez pliki w katalogu aplikacji — brak jakiegokolwiek `dev.key` w runtime.

## Kryteria akceptacji (wszystkie musza byc spelnione)
- [ ] Rejestracja/logowanie z JWT dziala; brute-force blokowany po 10 probach.
- [ ] Stripe webhooki idempotentne (powtorka eventu nie podwaja subskrypcji).
- [ ] Brak platnosci zawiesza licencje; platnosc ja wznawia.
- [ ] HWID blokuje uruchomienie na drugim komputerze; admin moze zresetowac.
- [ ] PROD nie startuje bez waznej licencji; DEV startuje bez licencji (tryb wybrany w build.ps1).
- [ ] Start backendu bez silnego JWT_SECRET nieudany; CORS tylko dozwolone originy.
- [ ] `docker compose up -d --build` stawia backend + Redis; `/docs` dostepny.
