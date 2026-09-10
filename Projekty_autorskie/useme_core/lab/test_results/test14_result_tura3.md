> ⚠️ WNIOSKI NIEAKTUALNE – patrz TEST 16 (2026-08-06): formularz wysyłki otwiera się w widocznej przeglądarce (headless=False) z cookies.

# TEST 14 – Formularz składania oferty z cookies.json

**Data:** 2026-08-06
**Runda:** 3
**Cel:** Sprawdzić, czy z cookies.json formularz na `/offer/start/` jest dostępny (ominiecie Turnstile) i zebrać aktualne selektory pól.
**Stack:** Chromium + playwright-stealth + cookies.json (`sessionid` + `csrftoken`), headless=True, `wait_until="domcontentloaded"` + `wait_for_timeout`
**Status testu:** ❌ **NIEUDANY — formularz niedostępny (Cloudflare "Just a moment...")**

---

## 1. Czy cookies ominęły Turnstile? → **NIE**

| Strona | URL | Wynik |
|--------|-----|-------|
| Lista ofert | `https://useme.com/pl/jobs/` | ✅ Dostępna (tytuł: "Praca Zdalna » Praca Online Oferty..."), brak blokady CF |
| Detal oferty (1. z listy) | `https://useme.com/pl/jobs/weryfikacja-niemieckiego-sklepu-internetowego-pod-katem-ux-i-jezykowym,142306/` | ❌ **"Just a moment..."** — blokada CF (nie zniknęła po 25 s czekania, reload i kolejnych 15 s) |
| **Formularz oferty** | `https://useme.com/offer/start/` | ❌ **"Just a moment..."** — blokada CF, potwierdzona **2×** (nie zniknęła po 25 s czekania, reload i kolejnych 15 s) |

**Warianty URL formularza (testowane):**
- `https://useme.com/offer/start/` → "Just a moment..." (CF block) — **to jest poprawny URL formularza**
- `https://useme.com/pl/offer/start/` → 404 "Strona nie znaleziona"
- `https://useme.com/pl/jobs/{slug},{id}/offer/start/` (wariant ze starego programu `offerSubmitter.ts`) → 404 "Strona nie znaleziona"

**Szczegóły blokady:** Na stronie formularza NIE wykryto widgetu `div.cf-turnstile` ani iframe `challenges.cloudflare.com` — to klasyczna strona challenge "Just a moment..." Cloudflare, która w headless **nie rozwiązuje się samoczynnie** (wymaga interakcji, np. kliknięcia w widget). Cookies sesyjne nie pomagają, bo blokada jest nakładana **przed** sprawdzeniem sesji.

**Konsekwencja:** Skoro detal jest zablokowany, nie można było też znaleźć linku "Dodaj ofertę" (`a:has-text("Dodaj ofertę")` itd. — liczba linków zawierających "ofer": 0) — link istnieje na stronie detalu, która jest niedostępna.

---

## 2. Tabela pól formularza

Formularz **nie był dostępny** — `document.querySelector('form')` nie istnieje na stronie blokady (0 formularzy, 0 pól). Poniższa tabela pokazuje pola, których szukano, oraz status:

| Pole | Selektor (typowy/stary program) | Istnieje? | Atrybuty (name/type/placeholder/id) |
|------|--------------------------------|-----------|--------------------------------------|
| textarea opisu (message/opis) | `textarea[name*="description"\|message\|content]` | ❌ NIE — formularz zablokowany przez CF | — |
| input ceny (budget/cena) | `input[name*="price"\|amount\|budget"], input[type="number"]` | ❌ NIE — formularz zablokowany przez CF | — |
| input dni (delivery/termin) | `input[name*="days"\|deadline\|duration\|time]` | ❌ NIE — formularz zablokowany przez CF | — |
| radio praw autorskich | `input[type="radio"][value*="transfer\|license\|none"]` | ❌ NIE — formularz zablokowany przez CF | — |
| przycisk wysyłki (submit) | `button[type="submit"]` | ❌ NIE — formularz zablokowany przez CF | — |

**Żadnych atrybutów pól nie udało się zebrać — DOM formularza nie został załadowany.**

---

## 3. Selektory ze starego programu — co wymaga poprawy/weryfikacji

Nie można było zweryfikować selektorów (brak dostępu do DOM formularza). Selektory, których używał stary program (`useme-ai-automation/src/scrapers/offerSubmitter.ts`), **pozostają do weryfikacji po odblokowaniu formularza**:

**textarea opisu:**
```
textarea[name*="description"], textarea#offer-description, textarea[name*="content"],
textarea[name*="message"], textarea[placeholder*="opisz"]
```

**input ceny:**
```
input[name*="price"], input[name*="amount"], input[name*="budget"], input[type="number"]
```

**input dni (termin):**
```
input[name*="days"], input[name*="deadline"], input[name*="duration"], input[name*="time"]
```

**radio praw autorskich:**
```
input[type="radio"][value*="transfer"], input[type="radio"][id*="transfer"]  (analogicznie license/none)
```
Fallback: kliknięcie `label` zawierającego `/przeniesien|licencj|bez\s*przen/i`

**przycisk wysyłki:**
```
button:has-text("Przejdź do podsumowania"), button:has-text("Wyślij"), button:has-text("Złóż ofertę"), button[type="submit"]
```

**Uwaga do poprawy (znaleziona statycznie):** stary program otwierał formularz jako `${jobDetails.url}/offer/start/`, ale ten URL zwraca obecnie 404 — poprawny URL to `https://useme.com/offer/start/` (lub link "Dodaj ofertę" ze strony detalu, gdy będzie dostępna).

---

## 4. Czy COKOLWIEK WYSŁANO: **NIE**

- Żaden skrypt nie wypełniał pól ani nie klikał przycisków wysyłki/submit.
- Test wykonał wyłącznie: `page.goto`, `wait_for_timeout` i odczytowe `page.evaluate`/`locator.count()`.
- Skrypt inspekcji (`test14_form_cookies.py`) zawierał wyłącznie logikę odczytu DOM; w `test14b`/`test14c` — tylko nawigacja i liczenie elementów.
- Do formularza nigdy nie doszło (blokada CF), więc fizycznie nie było możliwości wysłania oferty.

---

## 5. Artefakty

- `lab/test14_formularz_z_cookies/test14_form_cookies.py` — główny skrypt (lista → detal → formularz, inspekcja DOM)
- `lab/test14_formularz_z_cookies/test14b_retry.py` + `form_retry_results.json` — retry + warianty URL
- `lab/test14_formularz_z_cookies/test14c_offer_start_per_job.py` + `form_retry_c_results.json` — wariant `{detal}/offer/start/`
- `lab/test14_formularz_z_cookies/form_structure_with_cookies.json` — struktura wyników (form: null, CF block)
- `lab/test14_formularz_z_cookies/cookies.json` — kopia cookies (oryginał w `useme-ai-automation/cookies.json` nietknięty)

## 6. Rekomendacja

Chromium + stealth + cookies przechodzi **tylko strony publiczne** (lista). Detal i formularz są chronione dodatkowym challenge Cloudflare, którego **headless nie rozwiązuje**. Aby dostać się do formularza, potrzebny jest jeden z kierunków:
1. `headless=False` (widoczny Chromium) — challenge może wymagać realnego renderowania/widgetu,
2. solver Turnstile/challenge (np. capsolver/2captcha) wstrzyknięty w stronę,
3. trwały profil przeglądarki z już rozwiązanym challenge (`browser_profile` — plik istnieje w `useme-ai-automation/browser_profile`), użyty przez `launch_persistent_context` zamiast czystych cookies,
4. sprawdzić, czy challenge znika przy dłuższym czekaniu w widocznej przeglądarce (CF potrafi "pamiętać" rozwiązanego challenge przez `cf_clearance` — którego nie ma w cookies.json).
