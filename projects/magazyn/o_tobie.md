# SPECYFIKACJA PROFILU UŻYTKOWNIKA I SYSTEMU MAGAZYN

> **Status dokumentu:** Skonsolidowany fundament projektowy.  
> **Źródło pierwotne:** Nienaruszalne cytaty 1:1 oraz konteksty znajdują się w katalogu [`cytaty/`](file:///c:/Users/buchh/projects/magazyn/cytaty) oraz w pliku [`wywiad_1do1.md`](file:///c:/Users/buchh/projects/magazyn/wywiad_1do1.md).  
> **Zasady nadrzędne:** Przed jakąkolwiek pracą AI ma obowiązek zapoznać się z [`README.md`](file:///c:/Users/buchh/projects/magazyn/README.md).

---

## 1. Profil poznawczy i mechanika myślenia (Aksjomaty)

### Inżynieria reaktywna (brak pracy w próżni)
* **Zależność od bodźca:** Praca „z pamięci”, wymyślanie rozwiązań od zera lub pytania o abstrakcyjne ogólniki wywołują u użytkownika pustkę i paraliż decyzyjny.
* **Aktywacja analityczna:** Zmysł analityczny użytkownika uruchamia się natychmiast w kontakcie z konkretnym obiektem zewnętrznym (bodźcem: tezą, propozycją, zderzeniem faktów, błędem). Wtedy ocena jest natychmiastowa i precyzyjna („to jest dobre, to za blisko, tego nie chcę i dlaczego”).
* **Natura bodźca:** Bodziec to jakikolwiek impuls fizyczny podany przed oczy. Pytanie to tylko jedna, często najmniej efektywna forma bodźca. Bodziec zastępuje konieczność wewnętrznego przeszukiwania pamięci roboczej.

### Przeciążenie poznawcze i ucieczka myśli
* **Dynamika stresu:** W obszarach o dużej gęstości informacji brak zewnętrznego punktu oparcia sprawia, że nowe myśli zaczynają wypierać poprzednie. Ryzyko bezpowrotnej utraty wypracowanych koncepcji wywołuje natychmiastowy stres poznawczy.
* **Wymóg bufora:** System musi funkcjonować jako zewnętrzny rejestrator o zerowym oporze wejścia. Zrzut myśli musi być bezstratny i natychmiastowy, aby zdjąć obciążenie z głowy.

### Kryteria oceny i relacja z systemem
* **Użytkownik = Prawo:** Wszelkie rozstrzygnięcia, decyzje architektoniczne i kierunki należą wyłącznie do użytkownika. AI dostarcza materiał i propozycje, nie rozstrzyga samodzielnie.
* **Radar na iluzję pracy:** Odrzucenie działań pozorowanych (budowanie skomplikowanych struktur przed zebraniem danych, dopracowywanie nieistotnych detali). 
* **Zapis to praca:** Zbieranie danych wejściowych i przykładów przed rozpoczęciem budowy kodu jest fundamentem inżynieryjnym, a nie stratą czasu.

### Użytkownik jako Sędzia (Rozpoznawanie zamiast Odtwarzania)
* **Biegłość na szczegółach z zewnątrz:** Użytkownik nie potrafi wygenerować listy kryteriów z pamięci roboczej w głowie (brak technicznego aparatu), ale działa z chirurgiczną precyzją na szczegółach, gdy zostaną mu fizycznie wyłożone na stół.
* **Binarna selekcja:** Skonfrontowany z fizyczną listą obiektów/próbek, natychmiast dokonuje bezbłędnego, intuicyjnego osądu: *„TO CHCĘ” / „TEGO NIE CHCĘ”*.

---

## 2. Architektura wejścia i obieg danych

### Dwuetapowy proces zapisu (Ingestion Pipeline)
Wszelkie dane i myśli trafiają do Magazynu według ścisłego, dwuetapowego schematu:
1. **Etap 1: Bezstratne zabezpieczenie (Raw Capture)**  
   * Zapis 1:1, surowy, bez natychmiastowej interpretacji i kategoryzacji.  
   * Cel: stuprocentowa gwarancja przetrwania myśli i zdjęcie presji z użytkownika.
2. **Etap 2: Przypisanie do miejsca (Routing)**  
   * Odłożenie zabezpieczonej treści do właściwego obszaru magazynu.
3. **Zasada odroczenia (Deferred Processing):**  
   * Składowanie jest celem autonomicznym. Dane nie muszą być przetwarzane ani wykorzystywane od razu. Analiza może nastąpić w dowolnym późniejszym momencie.

### Dynamika i entropia danych
* **Czynna rola AI:** AI nie jest jedynie biernym czytnikiem. Posiada uprawnienia do pobierania danych, wydzielania z nich istotnych fragmentów, edycji, łączenia oraz generowania wniosków.
* **Granice Magazynu:** Wszelkie narzędzia zasilające (programy pobierające rolki, scrapery, integracje API) znajdują się poza architekturą Magazynu. Ich jedyną rolą jest zrzucenie surowych plików do odpowiedniej strefy wejścia.

---

## 3. Struktura Magazynu

### Elastyczna siatka miejsc na dane
* **Brak sztywnych ograniczeń:** Magazyn nie narzuca sztywnej liczby kategorii (np. 3 czy 4). Stanowi otwartą przestrzeń na dowolną liczbę wyspecjalizowanych miejsc (od kilku do setek).
* **Podstawowe obszary:**
  * **Surowe rozmowy:** Chronologiczny, nienaruszalny zapis sesji z AI (`rozmowy/`).
  * **Materiały zewnętrzne:** Pobrane pliki, artykuły, badania, multimedia uporządkowane według domen.
  * **Wiedza o użytkowniku:** Skondensowane zasady, styl poznawczy i preferencje.
  * **Czysty OUTPUT:** Dedykowane, odizolowane miejsce na gotowe opracowania i wyniki przygotowane do przeczytania.

### Niezależny mechanizm relacji (Linker)
* **Izolacja danych:** Materiały źródłowe (np. pliki PDF, zrzuty) nigdy nie są kopiowane bezpośrednio do profili ani notatek o użytkowniku.
* **Separacja połączeń:** Relacje i powiązania stanowią osobną warstwę referencyjną (link + uzasadnienie powiązania). Szczegółowa koncepcja: [`na_przyszlosc/mechanizm_relacji.md`](file:///c:/Users/buchh/projects/magazyn/na_przyszlosc/mechanizm_relacji.md).

### Zasada organizacji: 1 Temat = Opis + Cytaty
* Każde zagadnienie badawcze w `dane/` posiada własny, spójny mikro-obszar: `fakty.md` (zwięzła synteza reguł i stanu wiedzy) oraz `cytaty.md` (nienaruszalne, surowe wypowiedzi 1:1 przypisane do tematu).

---

## 4. Zasady współpracy i rola AI

### Zagadnienie „Bigger Picture”
* **Zasada:** Zmuszenie użytkownika do pilnowania całościowego planu podczas pracy nad szczegółami paraliżuje jego zdolności analityczne. AI ma za zadanie utrzymywać stan całości w tle i podawać wyłącznie wąskie bodźce do weryfikacji.
* **Zadanie badawcze:** Rozwój mechanizmu utrzymania kontekstu przez AI bez obciążania użytkownika opisano w [`na_przyszlosc/problem_bigger_picture.md`](file:///c:/Users/buchh/projects/magazyn/na_przyszlosc/problem_bigger_picture.md).
* **Zespoły AI w tle:** Wizja autonomicznego działania zespołów agentów opisana jest w [`na_przyszlosc/zespoly_ai_i_zadania_w_tle.md`](file:///c:/Users/buchh/projects/magazyn/na_przyszlosc/zespoly_ai_i_zadania_w_tle.md).

### Dwufazowy cykl budowy narzędzi (Anti-Jednorazówka)
* **Faza 1 (Przeszukiwanie / Inwentaryzacja 100% wartości):** AI przeczesuje dużą próbkę (np. 100 postów/filmów), wyciąga 100% obiektywnie przydatnych rzeczy i nazywa je w kompletną listę. Użytkownik w roli Sędziego dokonuje binarnej selekcji (*„TO CHCĘ” / „TEGO NIE CHCĘ”*).
* **Faza 2 (Ekstrakcja Produkcyjna):** Dedykowane, stałe narzędzie powstaje **dopiero po** Fazie 1 – dostaje twardą listę wyselekcjonowanych celów zamiast mglistego „wyszukaj co ciekawe”.

### Standard komunikacji
* **Konkret zamiast metatekstu:** Zakaz generowania długich wstępów, przeprosin, autorefleksji oraz pseudonaukowego żargonu.
* **Język rzeczowy:** Precyzyjne, zwięzłe formułowanie myśli.
* **Zasada prawdy:** Gdy AI identyfikuje błąd użytkownika – przedstawia twardy dowód lub zwięzłą argumentację, bez uległości, ale i bez bezpodstawnych tez.

### Architektura techniczna (Wytyczne dla przyszłego stacka)
1. **Maksymalna wydajność:** Priorytet numer jeden przy późniejszym doborze technologii. Błyskawiczny dostęp do plików i brak opóźnień.
2. **Niezależność od modeli:** Magazyn opiera się na lokalnych danych. Modele LLM są traktowane jako wymienne moduły obliczeniowe.
3. **Brak uwiązania w jednej aplikacji:** Dane muszą być czytelne i modyfikowalne z poziomu dowolnego narzędzia (edytor, terminal, zewnętrzne skrypty).

