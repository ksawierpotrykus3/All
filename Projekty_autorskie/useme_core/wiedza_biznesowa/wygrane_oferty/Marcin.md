# Wdrożenie płatności dla firm w aplikacji mobilnej

## Zleceniodawca
- Imię: Marcin
- Avatar: nie

## Budżet
Do negocjacji

## Prawa autorskie
Przeniesienie praw autorskich

## Opis zlecenia
Prace programistyczne polegające na wdrożeniu modułu subskrypcji dla firm w aplikacji mobilnej, działającej na systemach Android i iOS, w tym integrację z systemem płatności oraz logikę obsługi poziomów dostępu dla kont firmowych.

Wymagane funkcje: 
Integracja z zewnętrznym systemem płatności (Revenue Cat / systemy płatności mobilnych), obsługa cyklicznych płatności odnawialnych (subskrypcje) oraz automatyczne nadawanie i odbieranie uprawnień do tras na podstawie statusu płatności firmy. Konfiguracja APl i komunikacji między aplikacją mobilną a panelem administracyjnym w celu weryfikacji aktywnych subskrypcji firmowych w czasie rzeczywistym. Stworzenie panelu/ widoku dla managera firmy do zarządzania listą pracowników (dodawanie/usuwanie z subskrypcji). 
System operacyjny: 
iOS, Android

## Nasza oferta

### Wycena
6000,00 PLN

### Prawa autorskie
Przeniesienie praw autorskich

### Dni pracy
21

### Opis oferty
Z tym Revenue Catem przy kontach formowych zawsze wychodzi na wierzch ten sam problem.

Sklepy App Store i Google Play są skrojone pod subskrypcje B2C. Jeśli manager firmy ma płacić raz i zarządzać listą np. 20 pracowników, przypisywanie tego natywnie przez in-app purchases prosto z telefonu generuje gigantyczne konflikty i czesto kończy się odrzuceniem apki w procesie review przez Apple.

Dużo sensowniejsze i bezpieczniejsze jest zrobienie głównej płatności przez zewnetrzny link/panel webowy np Stripe Checkout, a w samej aplikacji mobilnej zaszywamy tylko logikę odpytującą przez api wasz serwer, czy dany użytkownik jest na aktywnej liście managera. Aplikacja weryfikuje status w czasie rzeczywistym i po prostu puszcza go na trasę albo blokuje.

Budżet za spięcie takiego systemu od A do Z ( to u nas 6000 zł. Mozemy sie zgadac na krotki call zeby ułożyć pod to architekturę danych.

---