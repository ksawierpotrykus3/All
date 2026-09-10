# Format ofert na Useme — reguły techniczne

> STATUS: ZASADA dla treści oferty na Useme, nie dla tej dokumentacji.

## Problem
Useme nie renderuje markdown, tabel, pogrubień. AI bez tej wiedzy tworzy oferty jak umowę, z tabelami i listami.

## ZASADA BEZWZGLĘDNA
- ZERO myślników. Ani em-dash, ani minus, ani myślnik w zdaniu.
- ZERO nawiasów. W razie absolutnej konieczności minimalnie.
- Powód: AI nadużywa myślników i nawiasów, oferta wygląda maszynowo.

## Zasady techniczne (zawsze)
1. Czysty tekst. Zero markdown, zero gwiazdek, zero hashy, zero tabel.
2. Brak list punktowanych. Nie używaj gwiazdek ani myślników na początku zdań. Pisz zwykłymi zdaniami.
3. Bez nagłówków sekcji jak "Wycena:" czy "Opis:". Te pola są w formularzu osobno.
4. Nie powtarzaj słów klienta słowo w słowo. AI tak robi i to od razu widać. Sparafrazuj.

## Długość i struktura — NIE sztywna, zależy od typu klienta
- Oferta musi odzwierciedlać realny tekst, który klient napisał.
- Klient napisał jedno zdanie, odpowiadaj krótko.
- Klient napisał długi brief, możesz napisać dłużej.
- Każdy typ klienta ma inny styl i ilość tekstu. Patrz WIEDZA/typy i WIEDZA/strategie.
- Zasada: oferta nie może utracić wartości merytorycznej przez sztuczne skracanie.

## Link
- Wklej goły URL, jeśli oferta tego wymaga dla wartości merytorycznej.
- Nie ozdabiaj markdownem.

## Kwota i termin — twarda zasada
- Kazda oferta MUSI zawierac konkretna kwote. Nie wolno wyslac oferty bez ceny.
- Nie pytaj o szczegoly zamiast podawac cene. Cena najpierw, pytania potem.
- Nie zostawiaj pola ceny pustego ani "do negocjacji". Podaj liczbe.
- Sposob ustalenia wysokosci ceny: patrz WIEDZA/strategie.

## Przykład złej oferty (czego NIE robić)
```
## Moja oferta
- Aktualizacja PrestaShop
- Wdrożenie motywu
| Etap | Cena |
|------|------|
| Audyt | 1000 |
```
To się rozsypie na Useme, wygląda jak kod.