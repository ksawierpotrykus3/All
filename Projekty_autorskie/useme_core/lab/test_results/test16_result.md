# TEST 16 – Formularz wysyłki (widoczna przeglądarka + cookies) ✅

> Data: 2026-08-06 | Stack: Chromium + playwright-stealth + cookies.json + **headless=False** | Status: **OK_FORM**
> Cel: znaleźć wszystkie pola formularza `/offer/start/` i zapisać schemat do planów. NIE wysyłano nic.

---

## Wynik w jednym zdaniu

**Formularz otwiera się w pełni w widocznej przeglądarce z cookies – NIE jest zablokowany Turnstile!**
Test 14 (headless=True) pokazywał "Just a moment...", ale w trybie widocznym formularz ładuje się normalnie.

## Kolejne kroki na żywo (potwierdzone)

1. Lista kategorii → OK (bez CF)
2. Klik w post (pierwsza oferta) → OK (bez CF)
3. Przycisk **"Dodaj ofertę"** na detalu → `href=/pl/jobs/142308/offer/start/`
4. **PRAWDZIWY URL formularza: `https://useme.com/pl/jobs/{ID}/offer/start/`** (konkretna oferta!)
5. Formularz → tytuł strony "Dodaj ofertę | useme.com" → 1 formularz widoczny

## SCHEMAT FORMULARZA (potwierdzony, z oferty etapowej)

### Pola do wypełnienia (3)
| Pole | Selektor | Typ | Uwagi |
|---|---|---|---|
| **Opis** | `input#id_description` (`name=description`, class `form__textarea`) | hidden (pod edytorem rich-text) | Treść AI #2; trzeba wpisać do edytora / ustawić wartość + event |
| **Wycena** | `input#id_payment` (`name=payment`, class `form__input form__input--payment`) | text | Kwota od AI #2 |
| **Dni pracy** | `input#id_work_days` (`name=work_days`, class `form__input`) | text | **minimum 7** |

### Waluta
| Pole | Selektor | Uwagi |
|---|---|---|
| Waluta | `select#id_currency` (`name=currency`) | PLN (domyślnie) |

### Prawa autorskie (radio `copyright_transfer`)
| Wartość | Etykieta | Kiedy |
|---|---|---|
| `license` | Licencja | klikamy TYLKO gdy jest napisane "decyzja freelancera" |
| `protocol` | Przeniesienie praw autorskich | j.w. |
| `without` | Bez przenoszenia praw autorskich | j.w. |

**Zasada użytkownika (potwierdzona na żywo):** jeśli na stronie NIE ma tekstu "decyzja freelancera" →
zleceniodawca już wybrał → NIE klikać żadnego radio (w teście: `protocol` było zaznaczone z góry).

### Etapy (TYLKO gdy zlecenie jest ETAPOWE – jak oferta 142308)
`stages-0-name` (Nazwa), `stages-0-description` (Opis – opcjonalne), `stages-0-copyright_transfer` (radio),
`stages-0-payment` (Wartość etapu), `stages-TOTAL_FORMS=5` (max. 1000). Przycisk "+ dodaj etap".

### Przycisk podsumowania
`button[type="submit"]` z tekstem **"Przejdź do podsumowania"** (class `button button--yellow-solid w-full`).
Następnie na stronie podsumowania → **"Wyślij"** (NIE otwierane w teście – zero wysyłki).

### Pola ukryte (nie dotykać)
`csrfmiddlewaretoken`, `_employer_*`, `_contractor_*`, `_amount`, `_currency`, `_copyright_transfer`,
`_show_copyright_transfer`, `_billing_*`, `license_duration` (15), `_subcategory` itd.

## WAŻNE ODKRYCIA
1. **URL z notatek był błędny:** root `https://useme.com/offer/start/` = **404**. Prawdziwy: `/pl/jobs/{ID}/offer/start/` (ID z linku "Dodaj ofertę").
2. **Formularz przywraca SZKIC (draft) z konta:** description="dddd", payment="1111", work_days="111".
   Mechanizm MUSI nadpisywać pola przed wypełnieniem (nie zakładać że są puste).
3. **Turnstile NIE blokuje formularza w widocznej przeglądarce z cookies** – test 14 był mylący (headless).
4. Formularz ma edytor rich-text: widoczne pole to contenteditable, treść trafia do `#id_description` (hidden).
5. Struktura zależy od oferty (etapowa / zwykła) – mechanizm powinien obsłużyć oba warianty.

## Pliki
- Skrypt: `lab/test16_formularz_schema/test16_formularz_schema.py`
- Wyniki JSON: `lab/test16_formularz_schema/test16_results.json`
- Pełny schemat JSON: `lab/test16_formularz_schema/form_schema.json` (216 pól, większość ukryta)
- Zrzut HTML: `lab/test16_formularz_schema/form_html.html`

**NIE wypelniono i NIE wysłano żadnej oferty (tylko inspekcja DOM).**
