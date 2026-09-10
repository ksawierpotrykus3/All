# Odpowiedź do klienta (smartcare) — WERSJA UCZCIWA

Data: 2026-08-25
Status: gotowa do wysłania. Opiera się WYŁĄCZNIE na zweryfikowanych faktach z sondy.
Nie obiecuje niczego, czego nie udowodniliśmy testem.

---

Cześć,

[UDOWODNIONE] Zanim cokolwiek wycenię, chcę Ci pokazać, co ustaliłem na żywo na API Vinted, bo część rzeczy z Twojej wiadomości wymaga doprecyzowania.

Sprawdziłem filtry i mam pewne wyniki. Marka, rozmiar, stan, cena i słowa kluczowe działają w API. Puściłem filtr po marce Nike i dostałem 96 ofert, wszystkie Nike, zero pomyłek. Rozmiar, stan i słowa kluczowe reagują tak samo, dla bzdurnego identyfikatora zwracają zero wyników. Cenę potwierdziłem, filtr od złotówki do dwóch zwrócił oferty dokładnie za złotówkę.

[UDOWODNIONE] Kategoria w API nie działa. Wybrałem wąską kategorię, która realnie nie może mieć 960 ofert, a serwer i tak zwrócił 960. To znaczy, że Vinted ignoruje ten filtr w API. Kategorię trzeba ogarnąć inną drogą i tego jeszcze nie rozwiązałem, więc nie obiecuję jej teraz.

Co do prędkości. Sprawdziłem kops i wiem, skąd wrażenie wolności. [POTWIERDZONE] Kops w marketingu pisze, że kupuje poniżej sekundy, ale jego własny podgląd pokazuje realną średnią około dwóch i trzech dziesiątych sekundy. Do tego pełna szybkość kopsa, tryb równoległy, jest zablokowana za najdroższym planem za osiemdziesiąt euro miesięcznie.

I rzecz, którą musisz wiedzieć. Vinted sam twardo ogranicza tempo do mniej więcej jednego zapytania na sekundę. Sprawdziłem to na koncie, przy szybszym tempie serwer zwraca błąd i blokuje. To znaczy, że sam Vinted narzuca dolną granicę, poniżej której żaden bot nie zejdzie.

Ale teraz uczciwie. Nie zmierzyłem jeszcze, o ile konkretnie prywatny bot będzie szybszy od kopsa w wykrywaniu ofert. Wiem, że kops ma kolejkę i chmurę, których prywatny bot nie ma, ale to hipoteza, nie pomiar. Nie testowałem też checkoutu ani tego, jak będą zachowywać się bany przy kilku kontach i proxy. Tego nie obiecuję, dopóki nie postawię działającego prototypu i nie zmierzę.

Więc mogę Ci teraz uczciwie powiedzieć tylko tyle. Wiem, które filtry działają w API, a które nie. Wiem, że Vinted tnie do około jednego zapytania na sekundę. Wiem, że kops realnie robi około dwóch i trzech dziesiątych sekundy, mimo że reklamuje poniżej sekundy. A resztę, czyli realną przewagę w szybkości, checkout i zachowanie przy multikoncie, muszę najpierw zbudować i zmierzyć, zanim cokolwiek obiecam.

Jeśli chcesz, robimy to tak. Najpierw postawię prototyp monitorowania z filtrami, które wiem że działają. Na nim zmierzę realną szybkość i pokażę Ci liczby. Dopiero na tej podstawie ustalimy cenę i resztę zakresu. Bez zmierzonego prototypu nie chcę Ci obiecywać rzeczy, których nie sprawdziłem.

Daj znać, czy wchodzimy w ten prototyp.

---

## Co można obiecać, a czego nie (ściąga do rozmowy)

### MOŻNA OBIECAĆ (zweryfikowane testem)
| Fakt | Dowód |
|---|---|
| [UDOWODNIONE] Marka działa w API | brand_ids=53 → 96/96 Nike |
| [UDOWODNIONE] Rozmiar działa | size_ids bzdurny → 0 |
| [UDOWODNIONE] Stan działa | status_ids bzdurny → 0 |
| [UDOWODNIONE] Cena działa | price_from=1&price_to=2 → 1.0 zł |
| Słowa kluczowe działają | search_text bzdurny → 0 |
| [UDOWODNIONE] Kategoria NIE działa w API | catalog_ids=2954 → 960 |
| Limit ~1 req/s | 429 po 6 requestach w 5.9s |
| Kops realnie ~2.3s, marketing <1s | jego własny feed vs strona |

### NIE MOŻNA OBIECAĆ (niesprawdzone)
| Rzecz | Dlaczego nie |
|---|---|
| "Kategorię zrobię przez stronę" | tylko odkryłem SSR, nie zbudowałem parsowania |
| "Wykrywanie szybsze niż kops" | zero benchmarku latencji, to hipoteza |
| "Checkout tak szybki jak pozwala Vinted" | checkout celowo nietestowany (ryzyko bana) |
| "Bany będą rzadsze" | zero testów proxy/fingerprintu/multikonta |
| "Panel webowy, VPS, 3-4 konta" | deklaracje implementacji bez prototypu |

### JEDYNA UCZCIWA DROGA
1. Najpierw prototyp monitorowania z filtrami, które wiemy że działają
2. Zmierzyć na nim realną szybkość i pokazać klientowi liczby
3. Dopiero wtedy wycenić resztę zakresu (checkout, multikonto, kategoria)