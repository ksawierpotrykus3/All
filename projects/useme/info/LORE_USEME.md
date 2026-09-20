# Lore Useme – mechanika platformy

> Podstawowa wiedza o tym, jak działa Useme. Dla AI, które nie zna tej polskiej strony.

---

## Czym jest Useme?

Useme to polska platforma dla freelancerów:
- Zleceniodawcy publikują oferty pracy/zleceń
- Wykonawcy (freelancerzy) przeglądają oferty i wysyłają swoje propozycje
- Platforma pobiera prowizję od zrealizowanych zleceń

---

## Jak działa przeglądanie ofert?

1. Wchodzisz na useme.com → zakładka "Jobs" → "Znajdź zlecenie"
2. Wybierasz kategorię (np. Programowanie i IT)
3. Widzisz listę ofert – najnowsze na górze
4. Każda oferta ma przycisk "Wyślij ofertę" (tylko po zalogowaniu)

---

## Struktura URL-i kategorii

URL kategorii ma stały format:

```
https://useme.com/pl/jobs/category/NAZWA_KATEGORII,ID_LICZBOWE/
```

Przykłady:
- `https://useme.com/pl/jobs/category/programowanie-i-it,35/`
- `https://useme.com/pl/jobs/category/serwisy-internetowe,34/`

**WAŻNE:** ID liczbowe na końcu (34, 35) może się zmieniać.  
Nie wiadomo kiedy i dlaczego – prawdopodobnie przy zmianach w bazie kategorii.  
Reszta URLa (nazwa kategorii) jest stała.

Aktualne ID (2026-08-06):
| Kategoria | ID |
|---|---|
| Programowanie i IT | 35 |
| Serwisy i strony internetowe | 34 |

---

## Zabezpieczenia platformy

### Cloudflare
- Strona jest chroniona przez Cloudflare
- Przy pierwszym wejściu może być sprawdzanie przeglądarki (JavaScript challenge)

### Turnstile (CAPTCHA Cloudflare)
- Pojawia się przy logowaniu
- To następca reCAPTCHA – weryfikuje, czy użytkownik to człowiek
- Bez przejścia Turnstile nie da się zalogować automatycznie

### Wymóg logowania
- **Bez logowania nie widać pełnej listy ofert** (lub widać tylko ograniczoną)
- Trzeba być zalogowanym, żeby przeglądać i wysyłać oferty

### Limity
- Prawdopodobnie limit ~5 wysłanych ofert na jednego zleceniodawcę / na zlecenie
- Stąd pomysł na rotację kont – więcej kont = więcej możliwych ofert do wysłania

---

## Kategorie (stan na 2026-08-06)

Interesują nas 2 kategorie:

1. **Programowanie i IT** – ID: 35
2. **Serwisy i strony internetowe** – ID: 34

W przyszłości można dodać więcej kategorii.