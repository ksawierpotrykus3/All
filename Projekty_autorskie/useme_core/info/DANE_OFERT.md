# Dane ofert – struktura i przykłady

> Co wyciągamy z ofert na Useme – zarówno z listy (krótkie), jak i ze strony szczegółów (pełne).

---

## A. Dane z listy ofert (krótkie – Krok 1)

To co widać na stronie kategorii, przed kliknięciem w ofertę.

| Pole | Opis | Przykład |
|---|---|---|
| Tytuł oferty | Główny tytuł | "Stworzenie narzędzia do drukowania w pdf zestawów z Płatnika" |
| Nazwa zleceniodawcy | Nick lub imię | "RADI", "user042005", "Anna" |
| Avatar | Czy ma avatar | false (no avatar) |
| Liczba ofert | Ile już wysłano | 15, 25, 26 |
| Czas do końca | Za ile dni wygasa | "Znika za 30 dni" |
| Kategoria szczegółowa | Podkategoria | "Oprogramowanie", "Projekty IT" |
| Budżet | Kwota lub "Do negocjacji" | "500,00 PLN" |
| Krótki opis | Pierwsze ~200 znaków | "Szukam programisty/freelancera, który stworzy prostą aplikację..." |
| Link do oferty | URL do szczegółów | `https://useme.com/pl/jobs/...` |

---

## B. Dane ze strony szczegółów (pełne – Krok 4)

Po kliknięciu w ofertę i kliknięciu **"pokaż pełny opis"**.

### Sekcja główna (lewa strona)

| Element | Przykład |
|---|---|
| Tytuł | "Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika" |
| Zleceniodawca | "RADI" (no avatar) |
| Opublikowano | "2 godziny temu" |
| Kategoria | "Oprogramowanie" |
| Prawa autorskie | "Przeniesienie praw autorskich" |
| Opis krótki | "Szukam programisty/freelancera, który stworzy prostą aplikację desktopową do generowani wydruków w pdf zestawów stworzonych w Płatniku" |
| Opis pełny | Po kliknięciu "pokaż pełny opis": "Wymagane funkcje: integracje z marketplace'ami, integracje z kurierami, integracja z KSeF, zarządzanie zamówieniami, obsługa magazynu, raportowanie i analityka" |
| Umiejętności | "javascript PHP" |

**WAŻNE:** Przycisk **"pokaż pełny opis"** / **"zobacz pełny opis"** trzeba kliknąć przed pobraniem danych – nie da się go zaznaczyć przez HTML (prawdopodobnie element JS). Playwright musi go fizycznie kliknąć.

### Menu po prawej stronie

| Element | Przykład |
|---|---|
| Budżet | "500,00 PLN" |
| Prawa autorskie | "Przeniesienie praw autorskich" |
| Ważne przez | "30 dni" |
| Przycisk **"Dodaj ofertę"** | ← najważniejszy przycisk na stronie |

**WAŻNE:** Przycisku "Dodaj ofertę" też nie da się zaznaczyć przez HTML – Playwright musi go znaleźć i kliknąć.

---

## Przykładowe oferty (z listy)

```
Oferta wysłana
no avatar
RADI
 15
 Znika za 30 dni
Stworzenie narzędzia do: drukowania w pdf zestawów z Płatnika
Szukam programisty/freelancera, który stworzy prostą aplikację desktopową do generowani wydruków w pdf zestawów stworzonych w Płatniku

category-others
Oprogramowanie

500,00 PLN
```

```
Oferta wysłana
user042005
user042005
 25
 Znika za 30 dni
Automatyzacja Make/n8n/Python: web scraping, OCR i AI
Szukam doświadczonego specjalisty, który zbuduje automatyzację (w Make, n8n lub napisze dedykowany skrypt) do odsiewania śmieciowych powiadomień z mojej skrzynki e-mail. Zadanie: - odbieranie powiadomień z Gmail (ok. 300 na dobę), - wejście w...

category-others
Projekty IT

Do negocjacji
```

---

## Uwagi techniczne

- Wszystkie dane wyciągamy jako tekst z HTML (BeautifulSoup)
- **Bez screenshotów** – DeepSeek V4 Pro nie obsługuje wizji
- Przycisk "pokaż pełny opis" wymaga kliknięcia przez Playwright (JavaScript)
- Przycisk "Dodaj ofertę" również wymaga kliknięcia przez Playwright
- Formularz wysyłki oferty – pola do ustalenia (do sprawdzenia na żywej stronie)