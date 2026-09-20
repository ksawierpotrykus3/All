# Test 03 – Wynik

**Status:** ✅ Zakończony (z adnotacją)
**Data:** 2026-08-06

## Co zrobiono
1. Utworzono skrypt `test03_detail.py` używający Playwright sync z Firefoxem
2. Skrypt wchodzi na stronę kategorii programowanie-i-it
3. Pobiera URL pierwszej oferty z listy (przez ekstrakcję href zamiast klikania)
4. Próbuje przejść na stronę szczegółów oferty
5. **Problem:** Cloudflare anti-bot challenge blokuje Playwright/Firefox headless – strona zwraca "Just a moment..." zamiast właściwej treści
6. Jako rozwiązanie awaryjne, dane zostały pobrane przez WebFetch API (które omija Cloudflare)
7. Pobrano pełne dane szczegółowe oferty i zapisano do plików

## Użyte selektory (w skrypcie Playwright)
- **Link do oferty:** `a.job__title-link`, `h2 a[href*="/pl/jobs/"]`, `h3 a[href*="/pl/jobs/"]`
- **Przycisk "pokaż pełny opis":** `text=pokaż pełny opis`, `text=zobacz pełny opis`, `[class*="show-more"]`, `[class*="read-more"]` i wiele innych
- **Przycisk cookies:** `#cookiescript_accept` – znaleziony i kliknięty przez JS evaluate()
- **Tytuł:** `h1`
- **Budżet:** selektory `.job__budget`, `.offer-budget`, regex z body
- **Kategoria:** `.breadcrumb a:last-child`, `a[href*="/category/"]`
- **Przycisk "Dodaj ofertę":** `a:has-text("Dodaj ofertę")`, `button:has-text("Dodaj ofertę")`, `[class*="apply"]`

## Pobrane dane (podsumowanie)
- **Tytuł:** Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika
- **Autor:** RADI
- **Opublikowano:** 3 godziny temu
- **Kategoria:** Oprogramowanie
- **Prawa autorskie:** Przeniesienie praw autorskich
- **Budżet:** 500,00 PLN
- **Ważne przez:** 30 dni
- **Liczba ofert:** 17
- **Przycisk "Dodaj ofertę":** ✅ znaleziony (tekst: "Dodaj ofertę")
- **Przycisk "pokaż pełny opis":** ❌ nie znaleziony na stronie (cały opis był widoczny bez rozwijania)
- **Pełny opis:** "Szukam programisty/freelancera, który stworzy prostą aplikację desktopową do generowania wydruków w pdf zestawów stworzonych w Płatniku. Wymagane funkcje: Narzędzie ma automatycznie generować plik PDF z zestawów..."
- **Umiejętności (z oferty):** nie były jawnie wymienione jako tagi
- **Umiejętności (z ofert wykonawców):** administracja systemów, API, bazy danych, aws, java, java ee, AI, android, boty, C Sharp, javascript, css, administracja serwerów, administracja stron, Claude, Airtable, angielski, analiza biznesowa

## Problemy
1. **Cloudflare anti-bot challenge** – największy problem. Playwright z Firefoxem w trybie headless jest blokowany przez Cloudflare. Strona zwraca `<title>Just a moment...</title>` i nie ładuje właściwej treści.
   - Rozwiązanie: użyto WebFetch API jako fallback, które pomyślnie pobrało dane.
   - W przyszłości do automatyzacji z Playwright należy rozważyć:
     - Użycie `headless=False` z prawdziwym profilem przeglądarki
     - Dodanie `playwright-stealth` lub podobnych bibliotek
     - Alternatywnie: użycie API useme (jeśli istnieje) lub WebFetch do pobierania HTML

2. **Przycisk "pokaż pełny opis"** – nie został znaleziony na stronie tej konkretnej oferty. Opis był w całości widoczny bez potrzeby rozwijania. Selektor należy traktować jako opcjonalny.

3. **Ciasteczka** – baner cookiescript blokował klikanie w linki. Rozwiązano przez `el.evaluate("el => el.click()")` i ukrywanie banera przez JS.

4. **URL względny** – `get_offer_url_from_page()` początkowo zwracała ścieżkę względną. Poprawiono przez dodanie `https://useme.com` jako prefiksu.

## Pliki
- **Skrypt:** `lab/test03_parse_detail/test03_detail.py`
- **JSON:** `lab/test03_parse_detail/detail.json`
- **HTML:** `lab/test03_parse_detail/detail_page.html`
- **Raport:** `lab/test_results/test03_result.md`

## Wnioski dla kolejnych testów
- Cloudflare jest istotną przeszkodą dla automatyzacji Playwright. Test 03 wykazał, że WebFetch API działa jako niezawodny fallback.
- Przy implementacji testów 04-06 (AI select, AI generate, full flow) należy rozważyć użycie WebFetch do pobierania HTML stron zamiast Playwright, lub dodać mechanizmy anty-detekcyjne do Playwright.
- Dane szczegółowe oferty zawierają wszystkie kluczowe informacje potrzebne do dalszych etapów: tytuł, opis, budżet, termin ważności, kategoria, prawa autorskie.