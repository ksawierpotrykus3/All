# ZESPOŁY AI I ZADANIA W TLE (Wizja operacyjna)

> **Status:** Wymóg koncepcyjny na przyszłość.  
> **Kontekst nadrzędny:** Ten dokument jest potrzebny na kolejnym etapie do kontynuowania pracy nad wdrożeniem – **najpierw trzeba precyzyjnie wymyślić ten mechanizm, zanim zacznie się go budować w kodzie.**

---

## Kontekst użytkownika (Cytaty 1:1)

**O roli zespołów modeli, przykładach i stanie planowania:**
> „1. jak cos to nie model ale zespol modeli  
> 2. to jest przyklad zastosowania tylko 1 z wieku  
> tam samo  1. podlega jako przyklad do 2.  
> 3. wlasnie nie wymyslilem jeszczej jak bedzie wygladac ogolne ulozenie. wiem ze poczatkowo sie dane wrzuca i segreguje. potem nie mam zaplanowane nic dalej”

**O konieczności zaprojektowania przed budową:**
> „i daj kontekst ze np 2 i 3 sa potrzebne potem do kontyniowania pracy bo pierw trzeba wymyslic zeby zaczac pracowac”

**Żywy przykład operacyjny nr 1 (Rolki, defraudacja clickbaitów, przyswajanie nauki):**
> „zalozmy przyklad. mam na fb i na ig kolekcje skupione wobec rolek o jakis Ai. i np chcialbym moc sobie stworzyc 1 miejsce ktore sciaga te filmiki(tu juz progra inny nie jest on czescia samego podmiotu po prostu wrzuca pliki sciagniete) i filmiki tam ida do tego i np mam pelny zespol ktory robi to co im wczesniej zdefiniuje. np przeszukuje siec w poszukiwaniu tego co ktos tam reklamuje i mowi ze da to jak napiszesz w komentarzu 'twoja stara' np albo reklamuja cos co wuglada super ale realia moga byc inne. w skrocie defraudacja kontentu dla nietecjhnicznych NP. albo kontent naukowy ktory chce przyswoic. i tak samo zespol se zrobie w tym samym miejscu albo w innym miejscu obok. nie mowie ze Ai musi byc w tym smaym miejscu co miejsce do skladowania. i np wyznaczam prompt i daje miejsce temu AI. do miesca w ktorym sa zapisane to w jaki sposob ma mi byc cos tlumaczone. 
> i daje miejsce na output. czyli specjalne wyznaczone miejsce na gotowe rzeczy d oprzeczytania
> to tylko 1 ,2 przyklady moze byc ich multum ale no sam widzisz.”

**O obiegu danych (entropia):**
> „ten sam zespol co dostaje Daje daje output gdzies. troche jak entropia. Ai moze dostawac dane. tak samo jak je wydzielac. zmieniac edytowac. Potem kluczowe dla stacka jest jak najwieksza wydajnosc i moze jakies duperele dodatkowe.”

---

## 1. Granica obecnego planowania (Stan otwarty)

* **Co jest ustalone:** Początkowo dane się wrzuca i segreguje (Magazyn jako bezpieczne składowanie).
* **Co jest po segregacji:** **Na ten moment nie jest zaplanowane nic dalej.** Użytkownik nie wymyślił jeszcze ogólnego ułożenia dalszych procesów. Żadne AI nie ma prawa dopisywać tu kolejnych faz na siłę.

---

## 2. Architektura pętli zadaniowej (Zespoły modeli w tle)

Praca w tle opiera się na **zespołach modeli** (nie pojedynczym modelu), które realizują różne scenariusze operacyjne.

### Przykłady zastosowań (z wielu możliwych):
1. **Weryfikacja treści zewnętrznych (Przykład z rolkami):**
   * Pobrany materiał $\rightarrow$ Zespół modeli weryfikuje w sieci wiarygodność narzędzia $\rightarrow$ Czysty wniosek ląduje w miejscu na OUTPUT.
2. **Nadzorowanie stanu i Bigger Picture (Przykład z rozmowami):**
   * Zespół modeli analizuje surowe rozmowy $\rightarrow$ Wyłapuje gubienie wątku $\rightarrow$ Zrzuca hipotezy i pytania robocze (szczegóły: [`problem_bigger_picture.md`](file:///c:/Users/buchh/projects/magazyn/na_przyszlosc/problem_bigger_picture.md)).

### Stałe elementy pętli:
1. **Zasilanie zewnętrzne (Poza stackiem):** Niezależne programy zrzucają surowe pliki do wskazanego folderu.
2. **Trzy wejścia dla zespołu modeli:**
   * Dostęp do surowych danych.
   * Dostęp do pliku z zasadami tłumaczenia użytkownikowi.
   * Prompt zadaniowy.
3. **Dedykowany OUTPUT:** Odizolowane miejsce na gotowe opracowania do przeczytania.
4. **Entropia danych:** Zespół modeli może pobierać dane, wydzielać części, modyfikować je i generować nowe byty.
