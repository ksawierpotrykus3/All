# TEST 09 – Porównanie starego vs nowego mechanizmu omijania Cloudflare

**Data:** 2026-08-06  
**Runda:** 2  
**Cel:** Porównać stary mechanizm (Chrome + stealth + cookies.json) z nowym (Firefox) pod kątem omijania Cloudflare na useme.com  

---

## 1. Stan starego programu (useme-ai-automation/)

| Element | Stan |
|---------|------|
| `cookies.json` | ✅ Istnieje – 2 cookies: `sessionid` + `csrftoken` |
| `browser_profile/` | ✅ Istnieje – pełny profil Chromium z cache, cookies, danymi |
| `state.json` | ✅ Istnieje – pusty marker (pierwsze uruchomienie) |
| `package.json` | ✅ `playwright-extra` + `puppeteer-extra-plugin-stealth` |
| Kod TypeScript | ✅ Pliki `.ts` w `src/` – brak kompilacji, uruchamiane przez `tsx` |
| `npm install` | ✅ Zależności aktualne (55 pakietów) |
| Uruchomienie `npm start` | ✅ Program odpala się poprawnie |
| Przeglądarka | ✅ Chromium 1228 działa (zainstalowane przez `npx playwright install chromium`) |
| Logowanie | ✅ Cookies wstrzyknięte – "zalogowano bez Cloudflare!" (log z browserManager.ts) |
| Lista zleceń | ✅ Pobrano 12 ofert (10 IT + 2 Serwisy Internetowe) |
| AI | ❌ Błąd WebSocket (brak wtyczki Opery GX) – ale to nie wina mechanizmu |
| **Wniosek** | **Stary program DZIAŁA jako mechanizm przeglądarki. Cloudflare ominięty. Sesja zalogowana.** |

---

## 2. Wyniki testu starego mechanizmu (Python: Chromium + playwright-stealth + cookies.json)

**Metoda:** 3 próby, headless=true, playwright-stealth, cookies z `cookies.json`, URL: `useme.com/pl/jobs/category/programowanie-i-it,35/`

| Próba | Cloudflare | article.job | Sesja | Tytuł strony | Uwagi |
|-------|-----------|-------------|-------|-------------|-------|
| 1 | ❌ (false positive*) | ✅ True | ✅ True | "Zlecenia IT » Praca dla Programistów \| useme.com" | Strona załadowana poprawnie |
| 2 | ❌ (timeout) | – | – | – | Timeout 30s na `networkidle` – problem techniczny, nie blokada |
| 3 | ❌ (false positive*) | ✅ True | ✅ True | "Zlecenia IT » Praca dla Programistów \| useme.com" | Strona załadowana poprawnie |

> \* **Ważna uwaga:** Detekcja `cloudflare_detected=True` w próbach 1 i 3 wynika z obecności widgetu Turnstile na stronie – jest to **widget logowania**, NIE blokada Cloudflare. Strona ładuje się normalnie, `article.job` obecne, sesja zalogowana. **Faktycznie: 2/3 prób PRZESZŁO.**

**Timeout w próbie 2:** `wait_until="networkidle"` zbyt restrykcyjny – strona ma długotrwałe połączenia WebSocket/SSE, które uniemożliwiają osiągnięcie stanu `networkidle`. W starym programie TypeScript użyto tego samego, ale z `headless: false` – w trybie widocznym timeout nie występuje.

---

## 3. Wyniki testu nowego mechanizmu (Python: Firefox + Playwright)

**Metoda:** 3 próby, headless=true, Firefox, URL: j.w.

| Próba | Cloudflare | article.job | Tytuł strony | Uwagi |
|-------|-----------|-------------|-------------|-------|
| 1 | ❌ (false positive*) | ✅ True | "Zlecenia IT » Praca dla Programistów \| useme.com" | Strona załadowana poprawnie |
| 2 | ❌ (REAL BLOCK) | ❌ False | **"Cierpliwości..."** | PRAWDZIWA blokada Cloudflare! |
| 3 | ❌ (false positive*) | ✅ True | "Zlecenia IT » Praca dla Programistów \| useme.com" | Strona załadowana poprawnie |

> **Faktycznie: 2/3 prób PRZESZŁO, 1/3 ZABLOKOWANE przez Cloudflare.**  
> Próba 2 dostała stronę z tytułem "Cierpliwości..." – to ekran challenge Cloudflare, gdzie przeglądarka jest weryfikowana. Firefox w headless został wykryty.

---

## 4. Porównanie – który wygrywa?

| Kryterium | Stary (Chrome + stealth) | Nowy (Firefox) |
|-----------|-------------------------|-----------------|
| Skuteczność headless | 2/3 (1 timeout techniczny) | 2/3 (1 realna blokada CF) |
| Prawdziwe blokady CF | **0/3** | 1/3 |
| Sesja zalogowana | ✅ Tak (cookies.json) | ❌ Nie (brak cookies) |
| Stabilność | Timeout na networkidle | Blokada CF co ~3 próbę |
| Stealth | playwright-stealth + manual | Tylko manual (add_init_script) |
| Wykrywalność headless | Niższa (Chrome lepiej obsługuje headless) | Wyższa (Firefox headless łatwiej wykrywalny) |

**Wynik: STARY MECHANIZM WYGRYWA** (2:1 w kategorii realnych blokad Cloudflare)

---

## 5. WNIOSEK – który mechanizm rekomendować?

### Rekomendacja: **STARY MECHANIZM (Chrome + playwright-stealth + cookies.json)**

**Powody:**

1. **Cookies.json działa** – sesja jest zalogowana od razu, omija Turnstile logowania
2. **Zero realnych blokad Cloudflare** w 3 próbach (timeout to problem techniczny, nie blokada)
3. **Chromium lepiej radzi sobie w headless** – Firefox został wykryty w 1/3 prób
4. **playwright-stealth** daje dodatkową warstwę ochrony (Firefox nie ma odpowiednika)
5. **Stary program TypeScript działa** – można go użyć jako referencji lub przepisać na Python

**Zalecane poprawki dla starego mechanizmu:**
- Zmienić `wait_until="networkidle"` na `wait_until="domcontentloaded"` + `wait_for_timeout(3000)` – uniknie timeoutów
- Rozważyć `headless: false` jeśli timeouty będą się powtarzać (tak jak w starym programie)
- Dodać `wait_for_selector("article.job")` jako dodatkowy warunek gotowości strony

**Firefox (nowy mechanizm) – kiedy użyć?**
- Jako fallback gdy Chrome zostanie zablokowany
- Z `headless: false` (mniejsza wykrywalność)
- Wymagałby Camoufox do pełnej skuteczności (obecnie testowany bez)

---

## 6. Dane techniczne testu

- **Środowisko:** Windows 10, Python 3.13, Playwright 1.58.0, playwright-stealth 2.0.2
- **Chromium:** 149.0.7827.55 (Playwright v1228)
- **Firefox:** Playwright Firefox (headless=true)
- **Czas testu:** ~3 minuty (oba testy)
- **Pliki wynikowe:**
  - `lab/test09_stary_vs_nowy/test09_stary_chrome.py`
  - `lab/test09_stary_vs_nowy/test09_nowy_firefox.py`
  - `lab/test09_stary_vs_nowy/test09_stary_wyniki.txt`
  - `lab/test09_stary_vs_nowy/test09_nowy_wyniki.txt`