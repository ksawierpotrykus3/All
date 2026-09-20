> ⚠️ WNIOSKI CZĘŚCIOWO NIEAKTUALNE – test 15 (2026-08-06) wykazał, że headless=True przestał działać (100% blokad tego samego dnia!). Ostateczny stack: headless=False (widoczna przeglądarka).

# TEST 12 – Co decyduje o ominięciu Cloudflare: przeglądarka czy cookies?

**Data:** 2026-08-06  
**Runda:** 3  
**Cel:** Rozstrzygnąć, czy za ominięcie Cloudflare odpowiada Chromium (stealth), cookies sesyjne, czy jedno i drugie.  
**Metoda:** Test krzyżowy: Chromium bez cookies vs Firefox z cookies.

---

## 1. Macierz testów (wszystkie dane z testu 09 i 12)

| Test | Przeglądarka | playwright-stealth | Cookies | wait_until | Próby | CF blokady | article.job | Śr. czas |
|------|-------------|-------------------|---------|------------|-------|-----------|-------------|----------|
| **09-stary** | Chromium | ✅ | ✅ | `networkidle` | 3 | **0** (1 timeout tech.) | ✅ (2/3) | ~30s |
| **09-nowy** | Firefox | ❌ | ❌ | `networkidle` | 3 | **1** (realna!) | ✅ (2/3) | ~15s |
| **12A** | Chromium | ✅ | ❌ | `domcontentloaded`+3s | 3 | **0** | ✅ 20 | 3583ms |
| **12B** | Firefox | ❌ | ✅ | `domcontentloaded`+3s | 3 | **0** | ✅ 20 | 3955ms |

---

## 2. Analiza porównawcza

### Chromium: cookies vs brak cookies

| Wariant | Test | CF blokady | Wynik |
|---------|------|-----------|-------|
| Chrome + stealth + cookies | 09-stary | 0/3 | ✅ |
| Chrome + stealth, BEZ cookies | 12A | 0/3 | ✅ |

**Wniosek cząstkowy:** Chromium z playwright-stealth przechodzi przez Cloudflare **niezależnie od cookies**. Cookies nie są potrzebne do ominięcia CF.

### Firefox: cookies vs brak cookies

| Wariant | Test | CF blokady | Wynik |
|---------|------|-----------|-------|
| Firefox BEZ cookies | 09-nowy | 1/3 | ⚠️ |
| Firefox Z cookies | 12B | 0/3 | ✅ |

**Wniosek cząstkowy:** Firefox z cookies przeszedł 3/3. Bez cookies miał 1 blokadę. **ALE** testy różniły się też `wait_until` (`networkidle` vs `domcontentloaded`+3s), co mogło wpłynąć na wynik.

### Chromium vs Firefox (bez cookies)

| Przeglądarka | Test | CF blokady |
|-------------|------|-----------|
| Chromium + stealth | 12A | 0/3 |
| Firefox | 09-nowy | 1/3 |

**Chromium ze stealth wygrywa.** Firefox bez cookies i bez stealth jest bardziej wykrywalny.

---

## 3. WNIOSEK KOŃCOWY

### Co naprawdę decyduje o ominięciu Cloudflare?

```
┌─────────────────────────────────────────────────────────┐
│   KLUCZOWY CZYNNIK: playwright-stealth + Chromium       │
│                                                         │
│   Cookies NIE SĄ niezbędne do ominięcia CF.             │
│   Cookies SĄ niezbędne do ZALOGOWANIA na useme.          │
│                                                         │
│   Chromium + stealth = 0 blokad (6/6 prób łącznie)      │
│   Firefox bez stealth = ryzyko (1/3 lub 0/3)            │
│                                                         │
│   wait_until="domcontentloaded" + timeout 3s            │
│   jest stabilniejsze niż "networkidle"                   │
└─────────────────────────────────────────────────────────┘
```

### Dlaczego test 09 był nierówny?

Test 09 porównywał:
- **Stary:** Chromium + stealth + cookies + `networkidle`
- **Nowy:** Firefox + brak stealth + brak cookies + `networkidle`

Różniły się **trzy zmienne naraz** (przeglądarka, stealth, cookies), przez co nie można było stwierdzić, która odpowiada za ominięcie CF. Test 12 rozdziela te zmienne i pokazuje, że:
1. **Stealth (wbudowany w Chromium przez playwright-stealth) to główny czynnik** — nawet bez cookies, Chromium przechodzi 3/3
2. **Cookies pomagają** — Firefox z cookies przeszedł 3/3 (ale uwaga: inny `wait_until`)
3. **`domcontentloaded` + timeout** eliminuje problem timeoutów z `networkidle`

### Ograniczenia testu 12

- Test 12B (Firefox + cookies) używał `domcontentloaded` zamiast `networkidle` — nie wiemy na 100%, czy Firefox z cookies przeszedłby też na `networkidle`
- Test 09-nowy mógł być fluke (1/3 blokad to mógł być przypadek)
- Próba 3-testowa daje ograniczoną pewność statystyczną

---

## 4. REKOMENDACJA OSTATECZNEGO STACKU

### Stack produkcyjny:

| Warstwa | Wybór | Uzasadnienie |
|--------|-------|-------------|
| **Przeglądarka** | **Chromium** (Playwright) | Sprawdzona, 6/6 prób bez blokad CF |
| **Stealth** | **playwright-stealth** | Kluczowy komponent omijania detekcji headless |
| **Cookies** | **cookies.json** (sessionid + csrftoken) | Niezbędne do zalogowania, nie do ominięcia CF |
| **wait_until** | **`domcontentloaded`** | Szybsze i stabilniejsze niż `networkidle` |
| **Timeout po load** | **`wait_for_timeout(3000)`** | Daje czas na załadowanie dynamicznych elementów |
| **Headless** | **True** | Działa, nie ma potrzeby visible mode |

### Kod referencyjny:
```python
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    
    # Wczytaj cookies (do logowania)
    with open("cookies.json") as f:
        cookies = json.load(f)["cookies"]
    context.add_cookies(cookies)
    
    page = context.new_page()
    
    # Zastosuj stealth (do ominięcia CF)
    Stealth().apply_stealth_sync(page)
    
    # Nawiguj
    page.goto("https://useme.com/pl/jobs/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    
    # Gotowe - strona załadowana, sesja zalogowana
```

### Firefox jako fallback:
- Firefox może działać jako alternatywa, jeśli Chromium zostanie zablokowane
- Z cookies przeszedł 3/3 w teście 12B
- Bez stealth — ryzyko okresowych blokad (1/3 w teście 09)
- Rozważyć `headless: false` dla Firefoksa jeśli blokady się powtarzają

---

## 5. Dane techniczne

- **Środowisko:** Windows 10, Python 3.13, Playwright 1.58.0, playwright-stealth 2.0.2
- **Chromium:** Playwright Chromium (headless)
- **Firefox:** Playwright Firefox (headless)
- **URL testowy:** `https://useme.com/pl/jobs/`
- **Pliki testowe:**
  - `lab/test12_cookies_czy_chrome/test12_a_chrome_bez_cookies.py`
  - `lab/test12_cookies_czy_chrome/test12_b_firefox_z_cookies.py`
- **Pliki wynikowe:**
  - `lab/test12_cookies_czy_chrome/chrome_bez_cookies_results.json`
  - `lab/test12_cookies_czy_chrome/firefox_z_cookies_results.json`
- **Kopia cookies:** `lab/test12_cookies_czy_chrome/cookies.json`