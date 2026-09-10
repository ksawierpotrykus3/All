# Konta – zarządzanie (1 konto)

> Używamy tylko 1 konta. Użytkownik jest zalogowany na stałe.

---

## Stan obecny

- **1 konto** – Ksawier
- Użytkownik praktycznie nigdy się nie wylogowuje na swoim komputerze
- Przeglądarka ma zapisane cookies sesji Useme

---

## Jak działa logowanie (a właściwie jego brak)

Nie robimy logowania przez skrypt.

Zamiast tego:
1. Playwright ładuje cookies z pliku `cookies.json` (sesja Useme: `sessionid` + `csrftoken`)
2. Strona Useme widzi użytkownika jako zalogowanego – nie trzeba przechodzić przez formularz logowania ani Turnstile

---

## ⚠️ WAŻNE – cookies to teraz kluczowy element (z rundy 2 i tury 3)

Test 11 (runda 2) potwierdził: **formularz `/offer/start/` jest chroniony przez Cloudflare Turnstile.**
- Bez zalogowanej sesji (cookies) → strona pokazuje tylko "Just a moment..." (challenge)
- Z cookies → omijamy Turnstile i formularz jest dostępny
- ⚠️ **Korekta z testu 16 (2026-08-06):** z **widoczną przeglądarką (headless=False)** + cookies
  formularz otwiera się w pełni i **Turnstile w ogóle się nie pojawia** – patrz niżej.

**Aktualizacja z TURY 3 (test 12 + 14):**
- ✅ **Cookies NIE są potrzebne do ominięcia Cloudflare na listach** – decyduje playwright-stealth (Chromium+stealth przechodzi 6/6 prób z i bez cookies)
- ✅ Cookies są **niezbędne do bycia zalogowanym** (wysyłka ofert, pełne dane)
- ❌ **ALE: same cookies NIE omijają Turnstile na formularzu w headless** – test 14: formularz zablokowany mimo cookies (2× potwierdzone)
- ✅ **ZAKTUALIZOWANE testem 16:** w trybie **widocznej przeglądarki (headless=False) formularz otwiera się w pełni z cookies – bez blokady Turnstile!** Test 14 był mylący, bo działał w headless.

**Solver Turnstile od Bartka – ✅ NIE POTRZEBNY (stan po teście 16, 2026-08-06):**
- Plik: `tech/turnstile_solver.py` (1533 linie, dostarczony przez użytkownika)
- **NIE używamy go** – test 16 pokazał, że formularz wysyłki otwiera się normalnie
  w widocznej przeglądarce z cookies, bez Turnstile. Nie wymaga przerobienia ani testowania.
- Zostaje tylko jako **awaryjny backup** (gdyby kiedyś Cloudflare zaostrzył blokady).
  Dopiero WTEDY (nie teraz): wyciąć `zombie_utils`, część Camoufox/proxy, `networkidle`→`domcontentloaded`,
  domena cardmarket→useme, `headless=True`→`False`.
- **NIE traktować jako zadania do zrobienia.**

**Wniosek:** `cookies.json` z `useme-ai-automation/` (sesja: `sessionid` + `csrftoken`) jest
**NIEZBĘDNY** do logowania i wysyłki. Dopóki go nie mamy w naszym projekcie – nie kasować
starego folderu ani pliku cookies.

---

## Przechowywanie danych

Hasło NIE jest potrzebne w skrypcie – używamy cookies, nie loginu.

- Plik `cookies.json` – wyeksportowane ciasteczka sesji (do załadowania przez Playwright)
- Plik w `.gitignore` – nie wrzucamy do repozytorium

**Do zrobienia:** skopiować `cookies.json` ze starego programu do naszego projektu
(po zakończeniu rundy 3 testów).

---

## Brak rotacji kont

Na razie NIE planujemy wielu kont. Tylko 1 konto = prostsza architektura.

Gdyby w przyszłości była potrzeba → wtedy wrócimy do tematu.
