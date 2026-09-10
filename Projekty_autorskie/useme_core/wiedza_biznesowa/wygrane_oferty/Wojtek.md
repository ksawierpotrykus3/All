# Senior Node.js Developer (vanilla, bez frameworków) — dokończenie i wdrożenie platformy SaaS do produkcji

## Zleceniodawca
- Imię: Wojtek
- Avatar: nie

## Budżet
Do negocjacji

## Prawa autorskie
Przeniesienie praw autorskich

## Opis zlecenia
Szukam doświadczonego inżyniera do doprowadzenia działającego MVP polskiej platformy B2B (ocena dojrzałości firm produkcyjnych) do wersji produkcyjnej. Ważne — nietypowy, celowo prosty stos:

Backend: czysty Node.js (CommonJS), własny serwer na module http/https, zero zależności runtime Dane: flat-file JSON (rozważamy migrację do SQLite) Frontend: vanilla HTML/CSS/JS, bez frameworków i bundlera Płatności: Stripe (REST + webhook HMAC); PDF: headless Chrome

Szukam osoby, która jest komfortowa z czystym Node bez Reacta/Express i potrafi przejąć oraz utwardzić istniejący kod — NIE szukam przepisania od zera. Mile widziane zacięcie DevOps (Linux, systemd, TLS, backupy) i doświadczenie z bezpieczeństwem webowym (OWASP) oraz RODO. Zakres (kamienie milowe): trwałość danych + backupy, produkcyjny e-mail, utwardzenie bezpieczeństwa, zgodność RODO, wdrożenie produkcyjne, monitoring, weryfikacja Stripe, dokumentacja i przeszkolenie naszego wewnętrznego opiekuna technicznego.

Proszę o krótkie portfolio podobnych wdrożeń (przejęcie/utrzymanie istniejących projektów) i oczekiwaną stawkę.

## Nasza oferta

### Wycena
7000,00 PLN

### Prawa autorskie
Przeniesienie praw autorskich

### Dni pracy
21

### Opis oferty
Czysty Node na wbudowanym module http bez Expressa to świetna opcja pod kątem wydajności. Z tym że przy takim stacku trzeba mocno pilnować wycieków pamięci i nieobsłużonych błędów, bo jeden wyjątek kładzie cały proces. Dlatego twardy daemon w systemd i monitoring to podstawa zeby to mialo rece i nogi na produkcji.

Migracja z płaskich JSONów do SQLite od razu wyeliminuje wam ryzyko race conditions, jak kilku userów naraz strzeli w ten sam plik przy zapisie. Do tego webhooki ze Stripe'a od razu zabezpieczymy walidacją podpisów HMAC na wejściu, więc nie ma opcji na lewe requesty i oszustwa.

Bardzo podobny temat z utwardzaniem systemu rezerwacji robiliśmy dla branży medycznej: `https://doktormonika.pl/zarezerwuj-online).` Backend to odizolowana logika z twardą autoryzacją transakcji, a frontend to czysty Vanilla JS i HTML bez żadnych Reactów i bundlerów, dokładnie tak jak u was. Zero zbednych zaleznosci, laduje sie blyskawicznie.

Weźmiemy to w całości – od izolacji serwera i wdrozenia VPS (Linux, certyfikaty, backupy), przez generowanie PDF na headless Chrome, aż po weryfikacje z OWASP. Wycena z ogłoszenia to pełny ryczałt za utwardzenie tego MVP do stabilnej wersji produkcyjnej, bez pisania wszystkiego od nowa, plus zrobienie dokumentacji dla waszego opiekuna.

Mozemy sie zgadac na krotkiego calla na Google Meet zeby omowic szczegoly

---