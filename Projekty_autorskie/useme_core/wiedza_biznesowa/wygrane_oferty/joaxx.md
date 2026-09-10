# programista Computer Vision (OpenCV, OCR, Windows/Android)

## Zleceniodawca
- Imię: joaxx
- Avatar: brak

## Budżet
10 000,00 PLN

## Prawa autorskie
Przeniesienie praw autorskich

## Opis zlecenia
Poszukuję doświadczonego programisty do długoterminowej współpracy przy tworzeniu komercyjnej aplikacji wykorzystującej Computer Vision oraz analizę obrazu w czasie rzeczywistym.

Projekt obejmuje stworzenie aplikacji desktopowej (Windows), która analizuje obraz wyświetlany na ekranie, wykrywa określone elementy interfejsu, rozpoznaje tekst oraz wykonuje zdefiniowane akcje po spełnieniu określonych warunków.

W kolejnych etapach planowane jest rozszerzenie projektu o wersję Android oraz synchronizację z usługami chmurowymi.

UWAGA: Szukam osoby z doświadczeniem w OpenCV / Computer Vision / OCR. Projekty polegające wyłącznie na tworzeniu standardowych aplikacji mobilnych nie będą brane pod uwagę.

### Wymagane funkcje
MVP powinno obejmować:
- analizę obrazu w czasie rzeczywistym
- wykrywanie określonych ikon i elementów GUI
- OCR (odczyt tekstu i liczników)
- monitorowanie zmian na ekranie
- wykonywanie określonych akcji po wykryciu zdarzenia
- system powiadomień
- prosty panel konfiguracji

Mile widziane doświadczenie z: OpenCV, OCR, Python, C++, C#, Windows Desktop, Android

### Umiejętności
AI, android, python, windows

## Nasza oferta

### Wycena
10 000,00 PLN

### Prawa autorskie
Przeniesienie praw autorskich

### Dni pracy
21

### Opis oferty
Cześć,

Piszę w imieniu dwuosobowego zespołu. Działamy bezpośrednio, a analiza obrazu w czasie rzeczywistym to nasza specjalność. Nie jesteśmy ludźmi od prostych apek mobilnych, więc idealnie trafiliśmy w Twoje wymagania.

Żeby nie lać wody, podam dwa konkrety z naszego podwórka. Zbudowaliśmy od zera aplikację opartą na modelach YOLO, która analizuje obraz z kamery w locie, rozpoznaje 80 typów obiektów i błyskawicznie skanuje kody kreskowe oraz QR. Z kolei inny nasz skrypt w OpenCV służył do rozpoznawania konkretnych elementów na fizycznych płytkach PCB. Tam margines błędu był zerowy, a dodatkowym problemem było zmienne oświetlenie z kamery. Analiza ikon i tekstu na płaskim, cyfrowym interfejsie to przy tym dużo czystsza i bardziej przewidywalna robota.

Twój budżet 10 tysięcy na MVP jest w porządku, ale żeby to miało ręce i nogi, musimy podejść do tego mądrze od strony technicznej. W takich projektach najłatwiej wyłożyć się na wydajności.

Zrzuty ekranu musimy robić z niskiego poziomu Windowsa przez DXGI. Inaczej zwykłe metody zadławią procesor i stracisz płynność. Druga sprawa to optymalizacja OCR. Nie skanujemy całego ekranu w poszukiwaniu tekstu. Nasz kod najpierw znajdzie konkretny obszar, wytnie malutki kawałek z samym licznikiem i dopiero to puści przez lekki model czytający. Dzięki temu reakcja programu to będą ułamki sekund. A jeśli aplikacja docelowa w jakiś sposób blokuje sztuczne kliknięcia, wiemy jak wysyłać akcje na poziomie sterownika sprzętowego myszy.

Za tę kwotę zrobimy stabilne MVP na Windowsa z pełnym panelem do ustawiania reguł. Przygotujemy też kod w taki sposób, żeby warstwa analityczna była oddzielona od reszty. Dzięki temu w przyszłości dużo prościej będzie przenieść ten sam algorytm na Androida.

Zdzwońmy się w tym tygodniu na 15 minut.

Pozdrawiam,