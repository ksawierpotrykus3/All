# Track — rejestr wyników ofert

## Cel
Logować każdą wysłaną ofertę, żeby nie wyciągać wniosków z pojedynczych sukcesów ani negatywów.

## Struktura rekordu
```
### [ID zlecenia] [Nazwa klienta]
- Data wysłania:
- Typ klienta:
- Strategia użyta:
- Cena lub stawka:
- Wynik: kontakt / brak odpowiedzi / odrzucono / wybrano
- Dobrze:
- Źle:
- Hipoteza:
- Alternatywa do testu:
```

## Zasady

1. Jeden rekord to za mało na wniosek.

2. Negatyw nie musi oznaczać, że strategia jest zła. Może wynikać z innej zmiennej: cena, termin, ton.

3. Regularnie testuj nową strategię, nawet gdy obecna działa.

4. Gdy strategia zawodzi na danym typie, spróbuj przeciwieństwa.

## Metryki
- Konwersja ogólna = liczba kontaktów i wyborów / liczba wysłanych
- Konwersja per typ = wynik dla typu / wysłane dla typu
- Konwersja per strategia = wynik strategii / wysłane strategią

## Rejestry

---