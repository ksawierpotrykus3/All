# Mechanizm ze starego programu (useme-ai-automation)

> Wyciągnięte TYLKO to, co działa – sam mechanizm, bez etapów AI.
> Stary program to TypeScript + Playwright (Chrome). Został rozwiązany na części,
> żebyśmy mogli go odtworzyć w naszym Pythonie.

---

## Co było w starym programie (struktura)

```
useme-ai-automation/
├── src/
│   ├── index.ts                  # orkiestrator (flow)
│   ├── setup_login.ts            # logowanie (tylko AI Studio)
│   ├── scrapers/
│   │   ├── browserManager.ts     # przeglądarka + cookies + stealth
│   │   ├── listScraper.ts        # lista ofert + "Zasada Janusza" (marker)
│   │   ├── detailScraper.ts      # detale oferty
│   │   └── offerSubmitter.ts     # wysyłka formularza
│   ├── steps/                    # 10 kroków AI (NIE kopiujemy)
│   └── utils/
│       ├── sessionManager.ts     # zapis/odczyt JSON
│       ├── retry.ts              # ponawianie
│       └── logger.ts             # logowanie
├── cookies.json                  # sesja Useme (istnieje!)
├── browser_profile/              # trwały profil przeglądarki (istnieje!)
├── state.json                    # marker (lastTitle/lastAuthor)
└── data/all_scraped_jobs.json    # historia ofert
```

**Ważne:** stary program używał **Chromium + playwright-extra + puppeteer-stealth**,
a nie Firefoxa/Camoufox. Cookies z Useme już istniały w `cookies.json`.

---

## 1. Przeglądarka (browserManager.ts) – DZIAŁA

```ts
// Trwały profil (zachowuje logowanie!)
chromium.launchPersistentContext('browser_profile', {
  headless: false,                        // widoczne okno
  viewport: { width: 1920, height: 1080 },
  userAgent: 'Mozilla/5.0 ... Chrome/124.0.0.0 Safari/537.36',
  locale: 'pl-PL',
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-blink-features=AutomationControlled',
  ],
});

// Wstrzyknięcie cookies Useme z cookies.json
await context.addCookies(data.cookies);

// Ukrycie webdrivera
await context.addInitScript(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => false });
  window.chrome = { runtime: {} };
});
```

**Co wyciągamy:**
- `launchPersistentContext(profil)` – profil trwały, sesja logowania się zachowuje
- Cookies wstrzykiwane z `cookies.json` → **logowanie bez Cloudflare/Turnstile** (komentarz w kodzie wprost to mówi)
- `--disable-blink-features=AutomationControlled` + ukrycie `navigator.webdriver`
- default `headless: false`

---

## 2. Marker "Zasada Janusza" (state.json) – DZIAŁA

Zamiast porównywać wszystkie oferty, zapisuje się **ostatnią znaną ofertę** w `state.json`:

```json
{
  "lastAuthor": "RADI",
  "lastTitle": "Stworzenie narzędzia do...",
  "lastProcessedAt": "2026-08-06T14:00:00Z"
}
```

Podczas scrapowania: gdy tytuł == `lastTitle` → **przerwij** (to już było).

To dokładnie ten sam mechanizm co nasz marker w `LOGIKA_ITERACJI.md`, tylko
nazwa jest inna ("Zasada Janusza"). Nasza wersja jest poprawna.

---

## 3. Lista ofert (listScraper.ts) – DZIAŁA

```ts
const CATEGORY_URLS = [
  { url: 'https://useme.com/pl/jobs/category/programowanie-i-it,35/', name: 'IT' },
  { url: 'https://useme.com/pl/jobs/category/serwisy-internetowe,10/', name: 'Serwisy Internetowe' },
];
const MAX_PER_CATEGORY = 10;
```

- `page.goto(categoryUrl, { waitUntil: 'networkidle', timeout: 30000 })` + `waitForTimeout(2000)`
- Selektor kafelków (próba 1): `article.job-item, [data-testid="job-card"], .job-card, .offer-item`
- Selektor fallback (próba 2): wszystkie `a[href*="/pl/jobs/"]` (bez `/category/`, pomijanie tytułów <= 5 znaków)
- Limit: 10 nowych (pierwsze uruchomienie) / 25 nowych (gdy marker istnieje)
- Agregacja do `data/all_scraped_jobs.json` (tylko unikalne po `hashUrl`)

**Uwaga:** stary program miał ID kategorii Serwisy = `10`. W naszym lore mamy `34`
(nowsze ID). Aktualne ID weryfikujemy na stronie.

---

## 4. Detale oferty (detailScraper.ts) – DZIAŁA

```ts
await page.goto(job.url, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(1500);

// Opis: próba przez selektor, fallback Ctrl+A / body.innerText
const descEl = page.locator('.job-description, .offer-description, [data-testid="job-description"], .description').first();
// fallback:
rawDescription = await page.evaluate(() => document.body.innerText);
```

Parsowanie czasu publikacji (regex):
- `/(\d+)\s*(minut|godzin|dni|tygodni)\s+temu|wczoraj/i`
- → konwersja do minut (minut → 1x, godzin → 60x, dni → 1440x, tygodni → 10080x)

Parsowanie praw autorskich (po tekście):
- `decyzja wykonawcy/freelancera/do uzgodnienia` → `DECYZJA_FREELANCERA`
- `przeniesienie praw autorskich` → `PRZENIESIENIE`
- `licencja` → `LICENCJA`
- `bez przenoszenia` → `BEZ_PRZENOSZENIA`
- domyślnie `DECYZJA_FREELANCERA`

**Ważne:** `retryWrapper` z 2 próbami i delay 3s.

---

## 5. Wysyłka formularza (offerSubmitter.ts) – POTWIERDZONE w teście 16 (2026-08-06)

**PRAWDZIWY URL formularza (z linku "Dodaj ofertę" na detalu):**
```
https://useme.com/pl/jobs/{ID}/offer/start/
```
⚠️ Root `https://useme.com/offer/start/` = **404** (stara notatka była błędna – test 11 był w CF).

**Stack wysyłki:** Chromium + stealth + cookies.json + **headless=False** (widoczna). W tym trybie
formularz otwiera się w pełni – Turnstile NIE blokuje (test 14 w headless mylił).

**Pola (POTWIERDZONE na żywo, test 16 – oferta etapowa):**
```python
# 2. Opis – ukryte pole pod edytorem rich-text (treść wpisujemy do edytora)
'input#id_description'            # name=description, class=form__textarea

# 3. Cena (Wycena)
'input#id_payment'                # name=payment, label "Wycena"

# 4. Liczba dni (Dni pracy) – minimum 7
'input#id_work_days'              # name=work_days, label "Dni pracy"

# Waluta
'select#id_currency'              # name=currency, domyślnie PLN

# 5. Prawa autorskie (radio name=copyright_transfer) – TYLKO gdy "decyzja freelancera"
#    value: license / protocol / without
'input[name="copyright_transfer"][value="without"]'   # Bez przenoszenia praw autorskich

# 6. Etapy (gdy zlecenie etapowe): stages-0-name / stages-0-description /
#    stages-0-copyright_transfer / stages-0-payment, stages-TOTAL_FORMS=5

# 7. Przycisk podsumowania (submit)
'button[type="submit"]'           # tekst "Przejdź do podsumowania"
# Potem na podsumowaniu: "Wyślij"
# Potwierdzenie: text "Oferta wysłana do zleceniodawcy"
```

**WAŻNE: formularz przywraca SZKIC (draft) z konta** – description="dddd", payment="1111",
work_days="111" były już wpisane. Mechanizm musi NADPISYWAĆ pola (czyścić przed wpisaniem).

**Protokół bezpieczeństwa (ze starego programu):** zlecenie < 5 min → czekaj 5 min + 15 s, potem reload.

---

## Wnioski / co zabieramy do Pythona

1. **cookies.json istnieje** – sesja Useme gotowa, logowanie omija Cloudflare
2. **browser_profile istnieje** – trwały profil przeglądarki
3. Marker → nasz `marker.json` / `last_offer.txt` (ten sam koncept)
4. Formularz oferty to URL `/pl/jobs/{ID}/offer/start/` (z linku "Dodaj ofertę" – test 16; root `/offer/start/` = 404!)
5. Selektor kafelków i detali – do weryfikacji na żywej stronie (ID kategorii się zmieniły)
6. Protokół bezpieczeństwa: zlecenie młodsze niż 5 min → poczekaj
7. Prawa autorskie: radio `transfer` / `license` / `none` w formularzu
8. Potwierdzenie wysyłki: tekst "Oferta wysłana do zleceniodawcy"

**Czego NIE kopiujemy:** wszystkie kroki AI (selekcjoner, wycena, rewident, redaktor,
audyt, knowledge evolution). To było połączone z Google AI Studio – my mamy DeepSeek.