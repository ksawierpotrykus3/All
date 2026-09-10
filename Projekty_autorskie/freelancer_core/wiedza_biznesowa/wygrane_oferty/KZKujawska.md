# MVP aplikacji webowej do screeningu danych względem list referencyjnych

## Zleceniodawca
- Imię: KZKujawska
- Avatar: tak

## Budżet
Do negocjacji

## Prawa autorskie
Decyzja freelancera

## Opis zlecenia
Szukam wykonawcy do stworzenia MVP aplikacji webowej typu SaaS umożliwiającej screening produktów względem różnych list referencyjnych oraz generowanie gotowych odpowiedzi dla użytkowników biznesowych.

System ma być prosty, intuicyjny i zaprojektowany tak, aby mogły z niego korzystać również osoby nietechniczne.

Aplikacja ma umożliwiać:

wgrywanie zbiorów danych,
porównywanie zbiorów z wybranymi listami referencyjnymi,
generowanie prostego wyniku („match / no match / verification required”),
wyświetlanie gotowych komentarzy/odpowiedzi przypisanych do wyniku,
ograniczenie dostępu do szczegółowych danych dla wybranych użytkowników.
Aplikacja webowa działająca w przeglądarce:

logowanie użytkowników,
role i uprawnienia,
centralna baza danych,
możliwość obsługi wielu firm (multi-tenant),
oddzielone dane klientów.
Role użytkowników

SuperAdministrator - Globalne zarządzanie systemem: -upload i aktualizacja list referencyjnych, -definiowanie pytań,
definiowanie automatycznych odpowiedzi/komentarzy,
konfiguracja prostych reguł warunkowych,
zarządzanie firmami i użytkownikami.
Administrator firmy - Użytkownik po stronie klienta:
dodawanie zbiorów danych
upload danych
zarządzanie użytkownikami swojej firmy.
Administrator widzi wyłącznie dane swojej firmy.

Użytkownik Standardowy - Użytkownik wykonujący screening:
wybór katalogu
wybór zakresu danych
wybór listy referencyjnej
uruchomienie screeningu,
otrzymanie wyniku i gotowej odpowiedzi.
Bez dostępu do pełnych danych produktowych.

Mechanizm działania Administrator firmy dodaje produkt i dane produktowe. SuperAdministrator wgrywa listy referencyjne. Użytkownik wybiera produkt i listę/pytanie. System wykonuje matching. System zwraca wynik oraz przypisany komentarz. Matching

W MVP matching może odbywać się głównie po:

numerach identyfikacyjnych, nazwach ORAZ dodatkowym kryterium w zależności od listy referencyjnej.

Dodatkowe mechanizmy dopasowania mogą zostać rozbudowane w kolejnych etapach.

Wymagane funkcje: 
Ważne wymagania Każda firma musi mieć oddzieloną przestrzeń danych. Firmy nie mogą widzieć swoich danych nawzajem. Listy referencyjne są wspólne/globalne. System powinien być prosty, czytelny i intuicyjny. UI powinno być nowoczesne i biznesowe. Na tym etapie zależy mi głównie na: działającym MVP, dobrej architekturze, prostym i stabilnym rozwiązaniu, możliwości dalszego rozwoju w kolejnych etapach. Posiadam już: wstępnie rozpisaną logikę systemu, przykładowe mockupy/dashboardy, opis workflow i ról użytkowników.

## Nasza oferta

### Wycena
14000,00 PLN

### Prawa autorskie
Przeniesienie praw autorskich

### Dni pracy
30

### Opis oferty
Przy SaaSach B2B z taką logiką matchingu, na 90% wyłożycie się na dwóch rzeczach, jesli nikt tego nie przemyśli na start. Po pierwsze - matching po nazwach to nigdy nie jest prosty select w bazie, bo ludzie robia podwojne spacje i literowki. Musimy od razu wdrożyć algorytm fuzzy search (np. odległość Levenshteina), zeby system mial jakas tolerancje bledu i nie wyrzucał "no match" przy byle literówce. Po drugie, ten multi-tenant - trzeba na poziomie bazy zalozyc twarde zabezpieczenia Row Level Security, żeby przez pomyłkę w kodzie w przyszłości jeden klient nie zobaczyl katalogow drugiego.

Co do wyceny. Kwota w rubryce to orientacyjny budżet za całe MVP i wypuszczenie tego na produkcję (żebyście wiedzieli, w jakich rzędach wielkości się obracamy przy dobrym kodzie). Natomiast fix-price w ciemno za caly system bez dokumentacji to samobojstwo dla obu stron.

Wspolprace przy takich dużych aplikacjach zaczynamy zawsze od Blueprintu Architektonicznego (sztywny koszt 1500 zł). Rozrysowujemy pełną architekturę bazy, endpointy i logike matchingu pod te wasze mockupy. Jak to bedziecie miec, mozemy wycenic prace koderskie co do zlotowki. Dajcie znac czy mozemy sie zgadac na Google Meet - wspolnik programista odpowie na wszystkie techniczne pytania.

---