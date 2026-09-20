# TEST 13 – Parser detali oferty Useme (selektory dla HTML-a "z fetch")

**Data:** 2026-08-06  
**Runda:** 3  
**Cel:** Znaleźć selektory działające na surowym HTML detali z `page.evaluate` + `fetch` (domknięcie L2).  
**Status:** ⚠️ Częściowo – **założenie testu 10 obalone** (evaluate+fetch NIGDY nie zwraca detalu, tylko 403 Cloudflare), ale znaleziono działający zamiennik + komplet selektorów i działający parser.

---

## 1. KLUCZOWE USTALENIE (zweryfikowane empirycznie)

**`page.evaluate` + `fetch` na detalu oferty = ZAWSZE 403 Cloudflare challenge.**
`page.goto` (nawigacja) = DZIAŁA.

Dowód – ta sama sesja, ta sama przeglądarka (Firefox headless + networkidle, cookies.json):

| Metoda | Wynik | Rozmiar | Treść |
|--------|-------|--------|-------|
| `page.goto(detal, networkidle)` | ✅ 200 | **385 162 B** | prawdziwy detal (JSON-LD + jobs-summary) |
| `page.evaluate` + `fetch(detal)` (ten sam kontekst!) | ❌ **403** | 6 033 B | Cloudflare challenge |

To znaczy, że:
1. **Cloudflare rozróżnia nawigację od XHR/fetch** – top-level navigation przechodzi, same-origin fetch dostaje 403.
2. **Test 10 nigdy nie pobrał "surowego HTML" detalu** – pobrane tam 5 920–6 047 B to strony challenge (~5,9–6,4 KB = dokładnie rozmiar challenge; prawdziwy detal ma ~380 KB). Stąd wszystkie pola `"?"` w `detail_*.json` z testu 10.
3. **Wszystkie zapisane pliki w `test13_parser_surowe_html/` przed tym testem (`raw_detail.html`, `raw_detail_firefox.html`, `rendered_detail.html`, `rendered_detail_final.html`) to strony Cloudflare** ("Just a moment..." / "Performing security verification" z Turnstile) – żaden nie zawierał detalu.

### Dodatkowo sprawdzone warianty (probe, 2026-08-06 ~16:00–16:30):

| Wariant | Stack | Wynik |
|---------|-------|-------|
| A. goto detal 3s | Chromium + stealth + cookies, headless | ❌ CF („Just a moment…”) |
| B. goto detal 12s | jw. (czekanie na Turnstile) | ❌ CF |
| C. lista → evaluate+fetch detalu | jw. | ❌ **403** + `article.job` na liście też 0 (CF) |
| D. lista → goto detal 5s | jw. | ❌ CF |
| **E. goto detal** | **Firefox headless + `networkidle` (+cookies)** | ✅ **realny detal** |
| F. WebFetch (zewnętrzne renderowanie) | – | ✅ realna treść (markdown) |

> Wniosek: w chwili testu **Chromium+stealth NIE przechodził detali** (mimo że w teście 12 przechodził listę), a **Firefox (zwykły, bez stealth) z `networkidle` przechodził detale**. Cloudflare bywa niestabilny w czasie (test 03/06/12 miały różne wyniki). Stack do detali: **Firefox + headless + `networkidle` + retry przy CF**.

---

## 2. Struktura prawdziwego detalu (przeanalizowana na `rendered_detail_REAL.html`, 385 KB)

Deta jest **server-rendered (Django)**: kluczowe dane są w HTML-u już po stronie serwera, JS dodaje głównie oferty wykonawców i lazy-load obrazków. Dwa źródła danych:

### A. JSON-LD – `script[type="application/ld+json"]` (schema.org **JobPosting**)

```json
{
  "@type": "JobPosting",
  "title": "Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika",
  "description": "<p>Szukam programisty/freelancera, ...</p>",
  "hiringOrganization": {"@type": "Organization", "name": "RADI"},
  "baseSalary": {"@type": "MonetaryAmount", "currency": "PLN",
                 "value": {"@type": "QuantitativeValue", "value": 500.0}},
  "datePosted": "2026-08-06",
  "validThrough": "2026-09-05",
  "identifier": {"@type": "PropertyValue", "name": "Useme", "value": "142281"},
  "url": "https://useme.com/pl/jobs/...",
  "employmentType": ["CONTRACTOR", "TEMPORARY"],
  "jobLocationType": "TELECOMMUTE",
  "applicantLocationRequirements": {"@type": "Country", "name": "Poland"}
}
```
Uwaga: JSON-LD NIE zawiera kategorii ani umiejętności.

### B. DOM – `div.jobs-summary__item` (label → wartość)

```html
<div class="jobs-summary__item">
  <div class="jobs-summary__item-label">Kategoria</div>
  <div class="jobs-summary__item-value">
    <a href="/pl/jobs/category/coding-and-it,35/software,100/" class="c-dark text-underline">Oprogramowanie</a>
  </div>
</div>
```

---

## 3. TABELA PÓL – działające selektory

| Pole | Selektory (kolejność fallbacku) | Przykładowa wartość | Poprawna? |
|------|----------------------------------|---------------------|-----------|
| **title** | `ld["title"]` → `h1.jobs__page-title` → `meta[property="og:title"]` (− „ - sprawdź to ogłoszenie”) | „Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika” | ✅ |
| **full_desc** | `.jobs-summary__item` (label „Opis” → `.jobs-summary__item-text`) + (label „Wymagane funkcje” → `.jobs-summary__item-text`), sklejone `\n\n` → fallback `ld["description"]` (strip HTML) | „Szukam programisty/freelancera…\n\nNarzędzie ma automatycznie generować plik PDF…” | ✅ (pełny opis) |
| **budget** | `ld["baseSalary"]` (currency+value) → `.jobs-summary__item` (label „Budżet” → `.jobs-summary__item-value`) → regex „Budżet: X PLN” | „500 PLN” / „Do negocjacji” | ✅ |
| **category** | `.jobs-summary__item` (label „Kategoria”) → `a[href*='/jobs/category/']` (ostatni = najwęższa) | „Oprogramowanie”, „Projekty IT”, „Aplikacje webowe” | ✅ |
| **author** | `ld["hiringOrganization"]["name"]` → `.jobs-summary__item` (label „Zleceniodawca”) | „RADI”, „user042005” | ✅ |
| **published** | `.jobs-summary__item` (label „Opublikowano”) → `ld["datePosted"]` (ISO) | „4 godziny temu” / „2026-08-06” | ✅ |
| **copyright** | `.jobs-summary__item` (label „Prawa autorskie”) | „Przeniesienie praw autorskich” | ✅ |
| **expires** | `.jobs-summary__item` (label „Ważne przez”) / `ld["validThrough"]` | „30 dni” | ✅ |
| **offers_count** | regex `Wysłane oferty\s*\((\d+)\)` | 22 | ✅ |
| **skills** | **brak na detalu zlecenia** – umiejętności są tylko w ofertach wykonawców (`article.marketplace-offer`); `a[href*='/jobs/skill/']` = 0 na detalu | `[]` | ✅ (celowo puste) |

**Wynik na 5 ofertach** (`parsed_details_v3.json`): **5/5 sparsowane, 5/5 kompletne (0 pól `"?"`)** – tytuły, opisy (pełne), budżety, kategorie, autorzy, daty publikacji zgodne z danymi z listy.

---

## 4. Różnice: „surowy HTML z fetch” vs renderowany (page.content())

1. **Surowy HTML z evaluate+fetch w ogóle nie istnieje** – zamiast niego jest 403 Cloudflare challenge (~6 KB). To była prawdziwa przyczyna `"?"` w teście 10, a nie „inna struktura”.
2. **`page.content()` (renderowany) zawiera dane server-side**: JSON-LD JobPosting i `jobs-summary__item` są w HTML-u od serwera – struktura identyczna jak w prawdziwym surowym HTML (gdyby był dostępny).
3. Renderowany detal jest duży (~380 KB) – głównie inline JS/CSS; treść merytoryczna to ~10% dokumentu.
4. Sekcja „Wymagane funkcje” (rozszerzony opis) bywa w ukrytym kontenerze `div.offer-details[data-hideable="content"]` (`display:none`) – BeautifulSoup czyta ją mimo to, bez klikania „pokaż pełny opis”. (W teście 03 trzeba było klikać; teraz nie trzeba.)
5. Umiejętności: na liście ofert (`article.job`) są `a[href*='/jobs/skill/']`, ale **na detalu zlecenia ich nie ma** – selektor z listy nie działa na detalu.

---

## 5. GOTOWE SELEKTORY / KOD PARSERA (do mechanizmu testu 15)

Kompletny działający skrypt: `lab/test13_parser_surowe_html/test13_parser.py` (pobieranie + parsowanie + zapis `parsed_details_v3.json`). Najważniejsze funkcje:

```python
# Pobieranie detalu – page.goto (nawigacja), NIE evaluate+fetch!
def fetch_detail_html(url, attempts=3):
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        # (opcjonalnie) context.add_cookies(cookies.json)
        page = context.new_page()
        html = None
        for i in range(1, attempts + 1):
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                h = page.content()
                if is_cloudflare(h):          # "Just a moment"/"cf_chl"/"cf-turnstile"
                    page.wait_for_timeout(3000)
                    continue
                html = h
                break
            except Exception:
                page.wait_for_timeout(2000)
        browser.close()
        return html

# Parsowanie – JSON-LD + jobs-summary
def parse_offer_detail(html, source_url=""):
    soup = BeautifulSoup(html, "html.parser")
    ld = get_ld_jobposting(soup)              # script[type="application/ld+json"] @type=JobPosting
    detail = {"status": "ok", "source_url": source_url, "offer_id": ld["identifier"]["value"]}

    detail["title"]    = ld.get("title") or txt(soup, "h1.jobs__page-title") or og_title(soup)
    detail["full_desc"] = join_nonempty(summary(soup, "Opis"), summary(soup, "Wymagane funkcje")) \
                          or strip_html(ld.get("description"))
    detail["budget"]   = ld_budget(ld) or summary(soup, "Budżet") or "Do negocjacji"
    detail["category"] = summary(soup, "Kategoria") or last(a[href*='/jobs/category/'])
    detail["author"]   = ld.get("hiringOrganization", {}).get("name") or summary(soup, "Zleceniodawca")
    detail["published"]= summary(soup, "Opublikowano") or ld.get("datePosted")
    detail["copyright"]= summary(soup, "Prawa autorskie")
    detail["expires"]  = summary(soup, "Ważne przez")
    detail["offers_count"] = int(re.search(r"Wysłane oferty\s*\((\d+)\)", html).group(1))
    detail["skills"]   = []                    # brak na detalu zlecenia (potwierdzone)
    return detail

# helper: wartość pola summary po etykiecie
def summary(soup, label_text):
    for item in soup.select(".jobs-summary__item"):
        label = item.select_one(".jobs-summary__item-label")
        if label and label_text.lower() in label.get_text(strip=True).lower():
            val = item.select_one(".jobs-summary__item-value") or item.select_one(".jobs-summary__item-text")
            return re.sub(r"\s+", " ", val.get_text(" ", strip=True)).strip() if val else ""
    return ""
```

---

## 6. WNIOSKI / REKOMENDACJE DLA MECHANIZMU (test 15)

1. **Detale: `page.goto` (nawigacja), NIE `evaluate+fetch`.** W testach 15 final_flow nadal używany jest `evaluate+fetch` na detalach – **należy go zastąpić `page.goto` z fallbackiem**, albo przyjąć Firefox+networkidle jako stack główny. `evaluate+fetch` na detalu zawsze dostanie 403.
2. **Stack do detali:** Firefox headless + `wait_until="networkidle"` + cookies + **retry 2–3× przy CF** (Cloudflare bywa kapryśny; test 06 i dzisiejsze próby pokazują, że to działa). Chromium+stealth był w chwili testu blokowany na detalach – traktować jako wariant, nie pewnik.
3. **JSON-LD JobPosting to najlepsze źródło** tytułu/opisu/budżetu/autora/dat; `jobs-summary__item` uzupełnia kategorię, prawa autorskie, „Ważne przez”, „Opublikowano” (względne).
4. **Lista (strona kategorii) nadal daje 90% danych** (title/author/category/budget/description) – detale są potrzebne głównie do pełnego opisu + budżetu dla AI #2.
5. Parser działa na HTML z `page.goto` (jedyny realnie dostępny); struktura server-side (JSON-LD + jobs-summary) jest identyczna w renderowanym i surowym HTML.

---

## 7. Pliki

| Plik | Opis |
|------|------|
| `lab/test13_parser_surowe_html/test13_parser.py` | **Gotowy parser + pobieranie (testowany)** |
| `lab/test13_parser_surowe_html/parsed_details_v3.json` | Wynik: 5/5 kompletnych detali |
| `lab/test13_parser_surowe_html/rendered_detail_REAL.html` | Prawdziwy detal (385 KB) – wzorzec struktury |
| `lab/test13_parser_surowe_html/raw_detail_REAL.html` | (zapis surowego fetch – challenge 403, dowód) |
| `lab/test13_parser_surowe_html/probe_report.json` | Raport wariantów probe |
| `lab/test13_parser_surowe_html/analyze_real_html*.py` | Skrypty analizy struktury |
| `lab/test13_parser_surowe_html/test13_probe*.py` | Skrypty probe (A–D + firefox + fetch) |
| `lab/test13_parser_surowe_html/probe2_firefox_netidle_a1.html` | Prawdziwy detal z retry (376 KB) |
| `lab/test13_parser_surowe_html/probe_C_evaluate_fetch.html` | Dowód: evaluate+fetch = 403 challenge |

**NIE WYSŁANO ŻADNYCH OFERT** – skrypt tylko czyta i parsuje (DRY RUN). ✅
