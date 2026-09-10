> ⚠️ URL formularza poprawiony w teście 16: prawidłowy to /pl/jobs/{ID}/offer/start/ (root /offer/start/ = 404).

# TEST 11 – Formularz /offer/start/ (DRY RUN) – RUNDA 2

## Status: ⚠️ CZĘŚCIOWO (Cloudflare blokuje formularz)

**Data:** 2026-08-06 15:36  
**Plik skryptu:** `lab/test11_formularz_dryrun/test11_form_dryrun.py`  
**Wyniki JSON:** `lab/test11_formularz_dryrun/form_structure.json`  
**Screenshot:** `lab/test11_formularz_dryrun/form_screenshot.png`  
**HTML formularza:** `lab/test11_formularz_dryrun/form_page.html`  

---

## 1. URL formularza

| Oczekiwany URL (stary program) | Rzeczywisty URL po goto | Działa? |
|---|---|---|
| `https://useme.com/pl/jobs/...,142281/offer/start/` | Ten sam URL | ✅ URL poprawny, NIE przekierowuje na logowanie |
| HREF z przycisku "Dodaj ofertę" | `/pl/jobs/142281/offer/start/` | ✅ ZGODNE ze starym programem `/offer/start/` |

**Wniosek:** URL formularza `/offer/start/` jest **POPRAWNY** – link na stronie detalu oferty prowadzi dokładnie tam.

---

## 2. Cloudflare – KLUCZOWE ODKRYCIE

Strona formularza `/offer/start/` jest chroniona przez **Cloudflare Turnstile**:

- **Tytuł strony:** `Just a moment...`
- **Treść HTML:** Wyłącznie kod Cloudflare z `challenges.cloudflare.com/turnstile/v0/b/.../api.js`
- **Żadne pola formularza nie są dostępne** – cały DOM to tylko Cloudflare challenge
- **Ray ID:** `a26e6d3f2bc3b19d`

**Oznacza to:** Formularz ofertowy `/offer/start/` jest chroniony przez Cloudflare przed dostępem bez sesji zalogowanego użytkownika. **Strona detalu oferty ładuje się normalnie** (bez challenge), ale formularz już nie.

---

## 3. Tabela pól formularza

Ponieważ Cloudflare zablokował ładowanie formularza, **NIE można było zweryfikować selektorów** ze starego programu. Wszystkie próby inspekcji DOM dały wynik negatywny:

| Pole | Selektor | Istnieje | Atrybuty |
|---|---|---|---|
| Textarea opisu | `textarea[name*="description"]` | ❌ | Cloudflare block |
| Textarea opisu | `textarea#offer-description` | ❌ | Cloudflare block |
| Textarea opisu | `textarea[name*="content"]` | ❌ | Cloudflare block |
| Textarea opisu | `textarea[name*="message"]` | ❌ | Cloudflare block |
| Textarea opisu | `textarea[placeholder*="opisz"]` | ❌ | Cloudflare block |
| Textarea fallback | `textarea` | ❌ | Cloudflare block |
| Input ceny | `input[name*="price"]` | ❌ | Cloudflare block |
| Input ceny | `input[name*="amount"]` | ❌ | Cloudflare block |
| Input ceny | `input[name*="budget"]` | ❌ | Cloudflare block |
| Input ceny | `input[type="number"]` | ❌ | Cloudflare block |
| Input dni | `input[name*="days"]` | ❌ | Cloudflare block |
| Input dni | `input[name*="deadline"]` | ❌ | Cloudflare block |
| Input dni | `input[name*="duration"]` | ❌ | Cloudflare block |
| Radio copyright | `input[value="transfer"]` | ❌ | Cloudflare block |
| Radio copyright | `input[value="license"]` | ❌ | Cloudflare block |
| Radio copyright | `input[value="none"]` | ❌ | Cloudflare block |
| Przycisk wysyłki | `button:has-text("Wyślij")` | ❌ | Cloudflare block |
| Przycisk wysyłki | `button:has-text("Złóż ofertę")` | ❌ | Cloudflare block |
| Przycisk wysyłki | `button[type="submit"]` | ❌ | Cloudflare block |
| Element `<form>` | `document.querySelector('form')` | ❌ | Cloudflare block – 0 pól, 0 buttonów |

---

## 4. Które selektory ze starego programu trzeba poprawić?

### ✅ Działające (potwierdzone):
- **Przycisk "Dodaj ofertę"**: `a:has-text("Dodaj ofertę")` – znaleziony na stronie detalu oferty
- **HREF formularza**: `/pl/jobs/{ID}/offer/start/` – zgadza się ze starym programem
- **URL formularza**: `{detail_url}/offer/start/` – POPRAWNY

### ❌ NIEZWERYFIKOWANE (Cloudflare blokuje):
Wszystkie selektory związane z polami formularza (`textarea`, `input`, `radio`, `button submit`) pozostają **NIEZWERYFIKOWANE**, ponieważ formularz jest chroniony przez Cloudflare i nie został załadowany.

### ⚠️ Rekomendacja:
Aby zweryfikować selektory, potrzebna jest **sesja zalogowanego użytkownika** (cookies z `cookies.json` z `useme-ai-automation/`). Alternatywnie można spróbować:
1. Użyć Chromium + playwright-stealth zamiast Firefoksa
2. Wczytać cookies z istniejącego `cookies.json`
3. Użyć trwałego profilu przeglądarki `browser_profile/`

---

## 5. CZY COKOLWIEK ZOSTAŁO WYSŁANE?

# ❌ NIE – ABSOLUTNIE NIC NIE ZOSTAŁO WYSŁANE

- Nie wypełniono żadnych pól formularza
- Nie kliknięto żadnego przycisku wysyłki
- Nawet formularz nie został załadowany (Cloudflare block)
- DRY RUN potwierdzony – inspekcja DOM tylko

---

## 6. Screenshot

Zapisany w: `lab/test11_formularz_dryrun/form_screenshot.png`  
(Na screenshocie widać stronę Cloudflare "Just a moment...")

---

## 7. Podsumowanie

| Aspekt | Wynik |
|---|---|
| URL `/offer/start/` działa? | ✅ Tak – poprawny URL |
| HREF z "Dodaj ofertę" prowadzi do `/offer/start/` | ✅ Tak – zgodne ze starym programem |
| Formularz dostępny bez logowania? | ❌ NIE – Cloudflare Turnstile blokuje |
| Selektory pól zweryfikowane? | ❌ NIE – nie było dostępu do DOM formularza |
| Coś wysłane? | ✅ NIE – DRY RUN potwierdzony |
| Przycisk "Dodaj ofertę" na detalu | ✅ Znaleziony: `a:has-text("Dodaj ofertę")` |

### Główny wniosek:
Formularz `/offer/start/` jest chroniony przez Cloudflare i dostępny tylko dla zalogowanych użytkowników. Aby przetestować selektory pól formularza, **konieczne jest zalogowanie** lub użycie istniejących cookies sesji z `useme-ai-automation/cookies.json`. Test należy powtórzyć z aktywną sesją.