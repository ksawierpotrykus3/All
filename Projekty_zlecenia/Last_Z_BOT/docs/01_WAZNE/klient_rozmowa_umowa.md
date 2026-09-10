> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Transkrypcja Rozmowy: joaxx

> <br />

Zlecenie :
40 dni
Silnik bota + panel lokalny (10 500 PLN)

**Treść oferty**

Silnik bota + panel lokalny (10 500 PLN)

- **Screen capture** przez DXGI Screen Duplication API (niskopoziomowe przechwytywanie ekranu Windows)
- **Detekcja alertu helikoptera** — template matching w OpenCV na ikonie helikoptera na dole ekranu lub skanowanie czatu OCR co kilkanaście sekund
- **Odczyt czatu i współrzędnych** — OCR (EasyOCR) na treści czatu, wyciągnięcie lokalizacji helikoptera
- **Nawigacja do helikoptera** — automatyczne kliknięcie współrzędnych i wycentrowanie kamery
- **Śledzenie licznika czasu** — ciągły odczyt licznika nad helikopterem z tolerancją na dynamiczne skoki
- **Finalizacja (Explore Treasure)** — detekcja zniknięcia helikoptera → wywołanie menu Select → dopasowanie wzorca ikony Explore Treasure → kliknięcie
- **Powrót do czuwania** — po odebraniu nagrody powrót do stanu obserwacji gry
- **Kliknięcia na poziomie sterownika sprzętowego myszy** (obejście SendInput, gotowość pod Arduino HID)
- **Logowanie każdej akcji** — wykrycia, odczyty licznika, decyzje, wykonane akcje (pełna transparentność)
- **Obsługa skalowania DPI** — poprawne współrzędne niezależnie od ustawień monitora
- **GUI z podglądem live** — okno aplikacji z live-podglądem przechwytywanego obszaru
- **Panel konfiguracji reguł** — częstotliwość skanowania, progi czasowe, obszary skanowania, opóźnienia kliknięć
- **Testy 24h** — testy stabilności i wykrywania na koncie testowym
- **Dokumentacja techniczna**

2\. Backend licencyjny (4 500 PLN)

- **FastAPI** jako framework API
- **SQLite** jako baza danych (wystarczająca na start, bez Postgresa)
- **Rejestracja i logowanie użytkowników** — JWT, tokeny dostępu
- **Integracja Stripe** — płatności cykliczne, webhooki (automatyczne zawieszanie subskrypcji przy braku płatności)
- **Endpoint walidacji licencji** — aplikacja Windows przy starcie pyta backend o stan konta, 403 = blokada
- **Zarządzanie kontami** przez proste API (bez panelu administracyjnego)
- **Kod przygotowany pod przyszłą migrację na PostgreSQL**

***

### DANE DOSTĘPOWE (Zapisane z ustaleń na WhatsApp):

**Gra Last Z:**

- **Konto (Email):** <kontolastz@wp.pl>
- **Hasło:** (Brak stałego hasła, logowanie jednorazowe kodem weryfikacyjnym z e-maila - gra zapamięta sesję).

**Skrzynka Pocztowa (WP.pl):**

- **Email:** <kontolastz@wp.pl>
- **Hasło:** kontokonto123!

***

## Wiadomosci  - czytaj od dołu do góry:

Ksawier Potrykus

Freelancer
Wysłano teraz

Dziękuję za wiadomość. Tak, jestem w stanie to doprowadzić do końca, ale najpierw chcę uczciwie poukładać, co było w naszej umowie, a co nie, żebyśmy obaj wiedzieli na czym stoimy.

Nasza umowa obejmowała przygotowanie, a nie wdrożenie. To ważna różnica i proszę, żebyś ją zrozumiał, bo bez tego będziemy się znowu mijać.

W umowie było napisanie kodu. Bota, panelu lokalnego i backendu licencyjnego, czyli konta użytkowników, logowanie, kod integracji Stripe i blokadę bota przy braku licencji. Ten kod powstał i jest. I zauważ, że nawet w samej umowie było napisane wprost "kod przygotowany pod przyszłą migrację na PostgreSQL". Czyli przygotowany, nie wdrożony.

Czego umowa nie obejmowała, to wdrożenia. Czyli postawienia tego na żywym serwerze, kupna domeny, założenia produkcyjnego konta Stripe i przejścia przez jego weryfikację, realnego podpięcia płatności tak, żeby obcy człowiek mógł wejść, zapłacić, dostać licencję i odpalić program. To jest osobny etap, którego nigdy nie zamówiłeś. Nie jest to wada tego, co powstało. To jest brakująca część, której nikt wcześniej nie ustalił.

I są jeszcze rzeczy, których nie obejmowała żadna z zaproponowanych ścieżek, a o które teraz pytasz, pisząc o przygotowaniu do sprzedaży. Instalator, żeby klient odpalał program jednym kliknięciem. Zabezpieczenie przed skopiowaniem pliku i rozesłaniem dalej. Poradnik dla kupującego. Testy na wielu różnych komputerach. Tego nie było w żadnej wersji oferty.

I sprawa "działa na każdym komputerze". Tu muszę być szczery. Nie mogę obiecać dosłownie każdego komputera, bo są maszyny, na których gra działa w trybie administratora, różne ustawienia ekranu i antywirusy, które blokują pliki. Mogę za to obiecać, że program będzie działał na każdym komputerze, który spełnia jasno określone wymagania, czyli Windows 10 lub 11, 64 bity, gra w oknie i ustalone ustawienia. Dam pełną listę wymagań i poradnik uruchomienia.

Proponuję więc, żeby w nowej umowie rozpisać to po kolei. Najpierw działający bot z jasną listą funkcji do przetestowania. Potem wdrożenie licencji, czyli postawienie backendu, podpięcie Stripe i sprawdzenie, że da się to sprzedawać. Potem pakiet sprzedażowy, czyli instalator, zabezpieczenie i poradnik. I dopiero na końcu, jako osobny etap do wyceny, te rzeczy, które były w droższych ścieżkach, jeśli nadal ich chcesz.

Daj znać, czy taki układ Ci pasuje, to przygotuję konkretną listę tego, co wchodzi do którego etapu.

***

joaxx

Zleceniodawca
Wysłano wcześniej

Napisałem do useme, że rozwiązujemy umowę za porozumieniem stron. Ciebie proszę o zastanowienie się jak ma to wyglądać dalej, czy jesteś jeszcze w stanie coś z tego zrobić tak żeby to działało w 100%, było przygotowane do sprzedaży i działało na każdym komputerze.

***

Ksawier Potrykus

Freelancer
Wysłano 3 dni temu

Dzień dobry,

rozumiem Pana stanowisko i przyjmuję je. To, że obecne zlecenie nie spełniło warunków odbioru, nie podlega dyskusji i nie zamierzam dalej ciągnąć go w trybie poprawek.

Natomiast chcę bardzo jasno powiedzieć jedno: ja chcę ten projekt doprowadzić do końca i chcę z Panem dalej pracować. Pana propozycja nowego, odrębnego zlecenia z nowym zakresem, kryteriami odbioru, etapami, terminami i płatnością jest dla mnie do przyjęcia w całości.

Jedno doprecyzowanie, żeby nie było niedomówień: sam program u mnie uruchamia się poprawnie, więc nie chodzi o to, że produkt jest martwy i nie do uratowania. Czego brakuje, to doprowadzenia go do stanu, w którym działa bezproblemowo również na każdym komputerze, bez żadnej ręcznej konfiguracji. I dokładnie to chcę teraz zrobić.

Proszę w takim razie o przedstawienie warunków z Pana strony. Nie będę stawiał własnych propozycji ani negocjował, to Pan ustala zakres, etapy, kryteria odbioru i terminy, a ja się do nich dopasuję. Zależy mi na tym, żeby tym razem wszystko było jasne od początku i żeby nie było już żadnych nieporozumień.

Jedyna rzecz, o którą proszę w kwestii obecnego kontraktu, to żebyśmy zamknęli go polubownie, jako rozwiązanie za porozumieniem stron, a nie jednostronne zerwanie. To dla mnie istotne ze względu na historię na profilu. Reszta pozostaje w Pana gestii.

Czekam na Pana warunki.

***

joaxx

Zleceniodawca
Wysłano 3 dni temu

Dzień dobry,
dziękuję za odpowiedź.
Rozumiem i doceniam, że chce Pan obecnie poświęcić czas na poprawki lub nawet budowę programu od podstaw, natomiast z mojej perspektywy problem polega na tym, że termin realizacji już minął, a produkt przedstawiony mi do odbioru nadal nie jest produktem, który mogę nawet normalnie uruchomić.

Przez cały okres realizacji udostępniałem konto testowe i na bieżąco przekazywałem informacje o zauważonych problemach i braku działań. Wielokrotnie zgłaszałem m.in., że helikoptery nie są odbierane. Nie jest więc tak, że problemy zostały ujawnione dopiero po zakończeniu prac.

Teraz, zgodnie z Pana najnowszą instrukcją, zainstalowałem dokładnie DEV\LastZBot-Dev-Setup.exe. Po uruchomieniu utworzonego skrótu nie pojawia się właściwe GUI aplikacji — otwiera się jedynie puste okno konsoli „LastZBot Dev".
Bardzo mi przykro ale to nie ma sensu.

Nie chcę obecnie wchodzić w kolejny nieokreślony etap testowania kolejnych wersji i diagnozowania produktu. Zlecenie miało określony zakres i termin, a jego rezultatem miał być działający produkt, nie kolejna wersja wymagająca wspólnego debugowania po upływie terminu.

W związku z tym na obecnym etapie nie akceptuję realizacji.

Jeżeli mielibyśmy w ogóle rozważać dalszą współpracę, z mojej strony mogłoby się to odbyć dopiero jako nowe, odrębne zlecenie, z ponownie ustalonym zakresem, jednoznacznymi kryteriami odbioru, etapami, terminami i warunkami płatności. Nie traktuję dalszych, nieograniczonych czasowo poprawek obecnej realizacji jako rozwiązania tej sytuacji.

***

Ksawier Potrykus

Freelancer
Wysłano 34 minuty temu

Jeszcze żeby nie było nieporozumień z plikami, doprecyzuję paczkę. Są w niej dwa foldery, DEV i PROD. Proszę użyć tego z folderu DEV, czyli DEV\LastZBot-Dev-Setup.exe. Wersja PROD czekała na połączenie z serwerem licencji i to z pewnością jeden z powodów, dla których u Pana nic nie ruszało po F6, zanim cokolwiek w ogóle mogło się wydarzyć.

Nie chcę Panu obiecywać, że teraz wszystko zadziała od pierwszego odpalenia, bo wiem, że wcześniej było sporo niedoróbek i nie chcę znowu zgadywać. Dlatego najpierw chcę zobaczyć, jak ten DEV faktycznie się u Pana zachowa. Proszę zainstalować, odpalić grę, wcisnąć F6 i nagrać mi ekran, a z folderu programu podesłać plik LOGS.txt, jeśli taki się pojawi. Na tej podstawie zobaczę dokładnie, gdzie stanęło, i będę poprawiać konkret, a nie na czuja.

Odnośnie backendu i Stripe, żeby było jasne: kod z kontami, logowaniem, integracją Stripe i weryfikacją licencji jest gotowy i jest w paczce w folderze source. Zgodnie z ustaleniami to było przygotowane jako kod do wdrożenia, więc jak tylko bot będzie działał poprawnie, pomogę Panu to postawić na serwerze, żeby sprzedaż i licencje działały od A do Z.

***

Ksawier Potrykus

Freelancer
Wysłano 59 minut temu

Dzięki za szczegółowe opisanie sytuacji. Rozumiem frustrację i chcę przeprosić, że doszliśmy do takiego momentu. Zdaję sobie sprawę, że obecna wersja nie spełnia tego co ustaliliśmy i że kontakt mógł być lepszy. Teraz sam biorę to na siebie i chcę po prostu doprowadzić temat do porządku, bez zbędnych dyskusji.

Żebyśmy nie kręcili się w kółko, proszę o komplet informacji, żebym mógł odtworzyć problem dokładnie u siebie. Samo nagranie dużo pomoże, ale bez kilku rzeczy mogę nie trafić w sedno, dlatego proszę o nagranie ekranu od momentu uruchomienia aplikacji, wersję systemu Windows razem z numerem buildu, wersję instalatora albo numer wersji aplikacji którą Pan ma, specyfikację komputera czyli procesor, ilość pamięci RAM i kartę graficzną, informację czy w tle działa antywirus albo firewall który mógłby coś blokować, dokładną kolejność kroków co Pan robi zanim naciska F6, oraz czy gra sama w sobie działa normalnie bez bota. Jeśli aplikacja pokazuje jakiekolwiek okna z błędami, proszę też o zrzuty ekranu tych komunikatów. Im więcej tych informacji dostanę, tym szybciej znajdę przyczynę zamiast zgadywać.

Bardzo proszę też, żeby całą dalszą korespondencję prowadzić przez Useme, a nie prywatnymi wiadomościami do wspólnika. Chcę mieć pełny wgląd we wszystko i nie chcę żeby cokolwiek się zgubiło. Teraz ja osobiście nad tym siadam i doprowadzę to do końca. Proszę dać mi szansę to naprawić, naprawdę mi na tym zależy i będę pracował nad tym do skutku.

***

joaxx

Zleceniodawca
Wysłano godzinę temu

Jestem w stanie przedstawić korespondencję z wykonawcą dokumentującą ustalony zakres oraz wielokrotne zgłaszanie problemów w trakcie realizacji, a także nagranie pokazujące działanie aktualnie przekazanej wersji programu.

Jednocześnie zaznaczam, że zależy mi przede wszystkim na polubownym rozwiązaniu sprawy w ramach procedury Useme. Jeżeli jednak nie będzie możliwe rozwiązanie sporu na tym etapie, zastrzegam sobie możliwość dochodzenia swoich praw i roszczeń na drodze prawnej, w tym sądowej.

Dysponuję korespondencją dokumentującą ustalony zakres zlecenia, zgłaszane w trakcie realizacji problemy, deklaracje wykonawcy dotyczące sposobu działania produktu oraz materiałami pokazującymi działanie przekazanej wersji aplikacji. Materiały te mogę przedstawić w ramach postępowania wyjaśniającego, a w razie potrzeby również w dalszym postępowaniu.

***

joaxx

Zleceniodawca
Wysłano godzinę temu

Dzień dobry,

nie akceptuję wykonania zlecenia i proszę o niewypłacanie wynagrodzenia wykonawcy na obecnym etapie.

Powodem jest to, że przekazany mi produkt w obecnym stanie nie realizuje prawidłowo podstawowych funkcjonalności będących przedmiotem zlecenia i nie nadaje się do odbioru jako ukończona realizacja.

Od początku bardzo dokładnie opisałem wykonawcy oczekiwany sposób działania aplikacji. Podstawową funkcją miała być pełna automatyzacja procesu w grze: wykrycie helikoptera, przejście do odpowiedniego miejsca w czacie, przejście do lokalizacji helikoptera, obserwowanie dynamicznego licznika, wykonanie odpowiedniej akcji w momencie zakończenia odliczania, odebranie nagrody oraz automatyczny powrót do stanu oczekiwania.

Wykonawca potwierdził ten zakres i opisywał pełną automatyzację właśnie jako cały powyższy proces. Po analizie przesłanego przeze mnie nagrania szczegółowo opisał również sposób realizacji końcowego etapu, obejmujący wykrycie zniknięcia helikoptera, otwarcie menu Select, znalezienie Explore Treasure, kliknięcie tej opcji i powrót do czuwania.

Co istotne, nie zamawiałem wyłącznie prototypu ani kodu będącego bazą do dalszych prac. Jeszcze przed zawarciem umowy jasno poinformowałem wykonawcę, że interesuje mnie kompletny produkt przeznaczony docelowo do sprzedaży. Następnie wspólnie ustaliliśmy zakres określony przez wykonawcę jako „Minimum do startu sprzedaży subskrypcyjnej”, obejmujący bota, panel lokalny oraz backend licencyjny z kontami użytkowników, logowaniem, integracją Stripe i weryfikacją aktywności licencji.

Niestety problemy z podstawowym działaniem bota występowały praktycznie przez cały okres realizacji i informowałem o nich wykonawcę na bieżąco. W trakcie testów na udostępnionym przeze mnie koncie wielokrotnie obserwowałem, że bot przechodzi do helikoptera, ale następnie nie odbiera nagrody. Informowałem wykonawcę m.in., że większość helikopterów pozostaje niekliknięta oraz że mam wrażenie, iż mechanizm nadal nie działa prawidłowo. Zgłaszałem również przypadki braku kliknięcia, nieprawidłowych czasów reakcji, zawieszania się programu oraz bardzo wysokiego wykorzystania procesora.

Sam wykonawca w trakcie prac informował m.in. o problemach z OCR oraz o wpływie obciążenia procesora na działanie programu. Pomimo tego realizacja została ostatecznie przedstawiona jako gotowy produkt.

Najpoważniejszy problem polega na tym, że przekazana mi obecnie wersja finalna nie realizuje prawidłowo nawet podstawowego scenariusza działania. Wykonawca przy przekazaniu instalatora poinformował mnie, że wszystko jest skonfigurowane tak, aby działało od razu i po uruchomieniu gry oraz naciśnięciu F6 bot automatycznie rozpoczynał pracę. W aktualnie przekazanej wersji aplikacja po uruchomieniu i wydaniu polecenia START/F6 nie rozpoczyna jednak prawidłowo działania.

W związku z tym przygotowuję również nagranie ekranu pokazujące działanie przekazanej wersji na moim komputerze, aby problem można było jednoznacznie zweryfikować.

Nie kwestionuję, że wykonawca przygotował kod źródłowy, dokumentację i poszczególne elementy techniczne projektu. Problem polega na tym, że przedmiotem zlecenia nie było samo przygotowanie kodu czy dokumentacji, lecz wykonanie działającego produktu realizującego uzgodniony proces automatyzacji oraz przygotowanego do wykorzystania w uzgodnionym modelu.

W mojej ocenie nie można uznać za prawidłowo wykonaną realizacji, w której podstawowa funkcja będąca głównym przedmiotem zamówienia nie działa prawidłowo, a w przekazanej wersji finalnej aplikacja nie jest obecnie w stanie poprawnie rozpocząć nawet podstawowego procesu automatyzacji.

Kontakt z wykonawcą podczas realizacji również był utrudniony. Wielokrotnie musiałem ponawiać wiadomości i prośby o kontakt, a zgłaszane przeze mnie uwagi dotyczące działania aplikacji nie doprowadziły do przekazania wersji, którą mógłbym uznać za stabilną i zgodną z ustalonym zakresem.

W związku z powyższym nie akceptuję obecnej realizacji i nie wyrażam zgody na zwolnienie wynagrodzenia wykonawcy.

***

joaxx

Zleceniodawca

zapłacone. Jakbym mógł prosić o tel. któregoś z Panów w wolnej chwili to będę wdzięczny. 533788007

Ksawier Potrykus

Freelancer

Będziemy mieli to na uwadze właśnie, nie zamykamy się tylko na last Z.
i zmieniłem treść umowy, możesz akceptować, chyba że wolisz rozliczać się bez useme. Daj znać
joaxx

Zleceniodawca

mimo wszystko trzymam kciuki za to, żeby coś poszło łatwiej niż się spodziewacie i będziemy oscylować w niższej cenie ;)

joaxx

Zleceniodawca

dobrze, działajmy. Zdecydowałbym się na ścieżkę A, oczywiście z potencjałem do rozwoju. Prośba żeby mieć na uwadze chęć ekspansji na inne gry o podobnej mechanice. Link który Ci wysłałem może służyć jako inspiracja bo właściwie chciałbym żeby tak to wyglądało mniej więcej. LOGOWANIE:
po instalacji gry trzeba poświęcić z 10min. żeby przejść przez jakieś tutriale itp. potem w lewym górnym rogu jak sie kliknie "uzytkownika" to będzie można przelogować na to konto:
<kontolastz@wp.pl> - następnie trzeba wpisać kod który przyjdzie na maila.
hasło do maila: kontokonto123!

jak jestem pod telefonem cały czas i można śmiało do mnie dzwonić z pytaniami odnośnie gry o każdej porze.

Ksawier Potrykus

Freelancer

Bot, którego wysłałeś, faktycznie radzi sobie na oficjalnym kliencie PC i robi to czysto programowo (bez żadnych kostek USB). Piszą zresztą o tym otwarcie w swoim FAQ ("Uses your mouse and keyboard while running"). Robią to za pomocą wirtualnych sterowników myszy i wstrzykiwania akcji na poziomie kernela.
A wspomniałem o tym Arduino
bo obejścia czysto programowe mają jeden duży problem – anty-cheaty na poziomie kernela (jak ACE w Last War) pewnie regularnie aktualizują bazy i potrafią z dnia na dzień zablokować wirtualne sterowniki, co kończy się falami banów. a koszt zrobienia nowego sterownika może oscylować 5-15k. Rozwiązanie z fizyczną kostką Arduino jest sprzętowe i w 100% niewykrywalne. Komputer widzi ją po prostu jako prawdziwą, fizyczną myszkę. Wspominałem o tym jako o ostatecznej metodzie gwarantującej całkowite bezpieczeństwo.
Na szczęście Last Z aktualnie NIE POSIADA tak zaawansowanego anti-cheata jak ACE. Oznacza to, że całe to MVP i w pełni działającego, bezpiecznego bota zrobimy dla Ciebie całkowicie programowo, bez konieczności dokupowania przez użytkowników jakiegokolwiek sprzętu Arduino to po prostu nasz plan B

joaxx

Pomysły super, tylko 99% klientów to azja niestety. Kurczę, troche zdziwiło mnie to, że w last war jest coś w stylu blokera tego typu oprogramowania. A mimo wszystko boty do niej istnieją, np. **[https://lastwarbot.com/](https://useme.com/pl/redirect?url=https%3A%2F%2Flastwarbot.com%2F)**. Nawet mają identyczną mechanikę którą chcemy stworzyć.

**Ksawier Potrykus**

FreelancerWysłano 59 minut temu

Co do kostki – z punktu widzenia sprzedaży to absolutnie nie jest przeszkoda, a wręcz standard w branży zaawansowanych botów. Klienci szukają gwarancji bezpieczeństwa przed banem i chętnie za nią dopłacają. Masz tutaj dwie ścieżki: albo wysyłasz bot z instrukcją „Kup Arduino Leonardo, a program sam się z nim połączy”, albo sprzedajesz pakiet "Premium" (Soft + skonfigurowana przez Ciebie płytka), co zresztą pozwala podyktować wyższą cenę subskrypcji. A wejście na inne tytuły nie będzie wymagało od nas pisania bota na nowo. Zmienimy tylko logikę zachowań i bazę obrazków do wykrywania.\
Backend i bazę danych również od razu projektujemy tak, aby jedno konto obsługiwało wiele licencji i różne gry (panel PWA po prostu wyświetli klientowi, które moduły ma wykupione). Ekspansja na inny tytuł to będą tygodnie, nie miesiące

<br />

**joaxx**

ZleceniodawcaWysłano godzinę temu

Czyli teoretycznie jak wprowadzą takiego anit-cheata do gry to właściwie sprzedanie bota będzie problematyczne bo będzie to wymagało tej kostki usb o której wspomniałeś. Ciekawe jest to, że do last war jest właściwie więcej botów i nie ukrywam, że myślałem również o ekspansji na inne gry z tym "mechanizmem" podobne do last z

<br />

**Ksawier Potrykus**

FreelancerWysłano 2 godziny temu

Chce doprecyzować kwestię Arduino, bo wcześniej wspomniałem o tym w wycenie a nie wyjaśniłem dokładnie po co.\
Arduino HID to mała płytka USB (-+30zł) która emuluje fizyczną myszkę. Jest potrzebne tylko w jednym scenariuszu - jeśli gra wprowadzi kernel-level anti-cheat, taki jak w Last War. ACE wykrywa programowe kliknięcia i blokuje je. Arduino jest poza systemem, więc jest niewidoczne.

zleciliśmy research i sprawdziliśmy to dokładnie. Last Z na ten moment NIE ma ACE. Szansa że wejdzie w ciągu roku to \~35%, w ciągu 3 miesięcy poniżej 15%. Omnilojo ma powody biznesowe żeby go nie wdrażać, gra jest w fazie wzrostu i celuje w zachodnie rynki, gdzie taki rootkit to problem wizerunkowy i prawny.

Więc jednak na MVP NIE potrzebujemy Arduino. Możesz o nim zapomnieć. Jeśli ACE kiedykolwiek wejdzie to kupimy płytkę za 30zł i wgramy firmware w jeden dzień. Kod będzie na to przygotowany.

<br />

**joaxx**

ZleceniodawcaWysłano 1 minutę temu

Czyli teoretycznie jak wprowadzą takiego anit-cheata do gry to właściwie sprzedanie bota będzie problematyczne bo będzie to wymagało tej kostki usb o której wspomniałeś. Ciekawe jest to, że do last war jest właściwie więcej botów i nie ukrywam, że myślałem również o ekspansji na inne gry z tym "mechanizmem" podobne do last z

<br />

<br />

**Ksawier Potrykus**

Freelancer

Dzięki za filmik i za konta, możesz podesłać loginy
Co do zakresu i budżetu.
Twoja lista: backend z kontami i licencjami, logowanie, Stripe, prosty panel PWA do logowania i zarządzania kontem, Resume.

Każdy z tych elementów da się zrobić. Ale nie wszystkie naraz mieszczą się w 10k ani w niewielkim zwiększeniu. Dlatego rozbijam to na dwie ścieżki, wybierasz.

Ścieżka A. Minimum do startu sprzedaży subskrypcyjnej. Całość około 14,5 do 15,5 tys zł.

W skład wchodzi bot i panel lokalny 10,5k oraz minimalny backend licencyjny 4 do 5k. Backend to FastAPI z SQLite, rejestracja, logowanie JWT, Stripe z webhookami, endpoint walidacji licencji przy starcie bota. Zero własnego serwera do zarządzania, konta ogarniasz przez proste API albo bezpośredni dostęp do bazy. Działa, ale bez ładnego interfejsu. Z Twojej listy są tu: backend z kontami i licencjami, logowanie, Stripe. Nie ma panelu PWA i nie ma Resume.

Ścieżka A+. Subskrypcje plus zarządzanie kontem z telefonu. Całość około 18,5 do 21,5 tys zł.

W skład wchodzi ścieżka A plus prosty panel PWA do logowania i zarządzania kontem z telefonu za 4 do 6k. Frontend responsywny, dashboard z podglądem subskrypcji, zmiana hasła, anulowanie. Działa na telefonie przez przeglądarkę, można dodać ikonę na pulpit. Z Twojej listy są tu: backend z kontami i licencjami, logowanie, Stripe, panel PWA. Nie ma Resume.

Ścieżka B. Wszystko co chcesz od początku. Całość około 20 do 24 tys zł, do doprecyzowania po PoC.

W skład wchodzi ścieżka A+ plus mechanizm Resume za 2 do 3k oraz backend na Postgres zamiast SQLite i podstawowy panel admina. Resume to WebSocket, stany bota, wykrywanie rozłączenia, restart klienta, przejście przez ekrany startowe, powrót do obserwacji. Z Twojej listy zrealizowane wszystkie pięć punktów.

Dlaczego PWA i Resume tyle kosztują. PWA to nie jest jeden widok. Trzeba zrobić osobny frontend, podpiąć go pod API, ogarnąć logowanie z tokenami żeby działało niezależnie od apki Windows, przetestować na różnych telefonach i przeglądarkach. Resume to nie tylko zapis stanu. Bot musi wykryć że gra wyrzuciła komunikat o rozłączeniu, przejść w idle, czekać na sygnał z panelu, odpalić klienta od nowa, przejść przez wszystkie ekrany startowe i wrócić do obserwacji. To nie są dodatki, to osobne moduły.

**joaxx**

ZleceniodawcaWysłano 23 minuty temu

mam również gotowe konto do gry.

**joaxx**

ZleceniodawcaWysłano 24 minuty temu

Podoba mi się zaproponowany zakres i myślę, że chcę z Wami współpracować. Natomiast zależy mi, żeby od początku produkt był gotowy do sprzedaży w modelu subskrypcyjnym. Cloud możemy całkowicie odłożyć na później, ale chciałbym porozmawiać, czy w obecnym budżecie albo przy niewielkim jego zwiększeniu da się uwzględnić:

backend z kontami użytkowników i licencjami,\
logowanie do aplikacji,\
integrację Stripe,\
prosty panel PWA do logowania i zarządzania kontem,\
mechanizm Resume.

Cloud i całą infrastrukturę serwerową możemy zostawić na kolejny etap.

przesyłam też link z filmem. Wybacz za amatorkę bo nagrany jest z wielkim znakiem wodnym.\
**[https://www.youtube.com/watch?v=C85z8P2XIEk](https://useme.com/pl/redirect?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DC85z8P2XIEk)**

<br />

**Ksawier Potrykus**

FreelancerWysłano 14 godzin temu

Jak tylko odpiszesz że ok, zmieniam wycene i treść na useme i możesz akceptować.

<br />

**Ksawier Potrykus**

FreelancerWysłano 14 godzin temu

Wybacz za zamieszanie, Maks mówił że miałeś podesłać filmik i na niego czekaliśmy, stąd cisza.\
Co do wyceny - silnik bota, pełna automatyzacja - 5500 zł\
Detekcja ikony, OCR licznika, przechodzenie przez cały flow, klikanie Explore Treasure, powrót do czuwania.\
Panel z customizacją reguł - 5000 zł\
GUI z podglądem live, wszystkie zmienne pod panel (częstotliwość klikania, progi czasowe, obszary skanowania), Arduino HID do bezpiecznego klikania, testy 24h, dokumentacja.\
Czyli razem 10,5k lekko poniżej budżetu.\
Backend subskrypcyjny, PWA na telefon, Resume i cloud to kolejne etapy.

Ciekawostka z naszego researchu: według publicznych danych jesteśmy jedyni , którzy robią bota pod natywny klient Windows. Cała konkurencja działa wyłącznie na emulatorach Androida przez wolny ADB. My działamy bezpośrednio przez DXGI, szybciej i czyściej. Zero konkurencji w tym segmencie.

<br />

**joaxx**

ZleceniodawcaWysłano 16 godzin temu

A witam. A rozmawiałem z Twoim bratem jak dobrze pamiętam. No myślę że działamy. Czekam właściwie tylko na „pełną gotowość” i określenie się z ceną.

<br />

**Ksawier Potrykus**

FreelancerWysłano 21 godzin temu

Dzień dobry, jak tam sytuacja?

<br />

**Ksawier Potrykus**

Nam pasuje czwartek po 14.

<br />

**Ksawier Potrykus**

Za 12k da się to sensownie poukładać. Mój wspólnik od strony technicznej z Tobą pogada bezpośrednio, ja nie będę na callu bo to on się na tym lepiej zna.

Daj znać czy telefon czy Google Meet i kiedy masz czas.

<br />

**joaxx**

Zleceniodawca Wysłano 8 minut temu

Cześć,

Przemyślałem temat i jestem zainteresowany stworzeniem tego jako kompletnego produktu, a nie tylko jednorazowego bota. Mam na ten moment założony budżet na poziomie około 12 tys. zł i chciałbym zobaczyć, czy jesteśmy w stanie sensownie zaplanować zakres, żeby się w nim zmieścić.

Jeżeli uważasz, że da się to dobrze poukładać, to chętnie porozmawiam przez telefon. Myślę, że w 15–20 minut łatwiej będzie omówić całą wizję projektu niż pisać wszystko w wiadomościach.

<br />

**Ksawier Potrykus**

FreelancerWysłano 4 godziny temu

<br />

Od razu mówię że to szacunki, finalne kwoty ustalimy jak PoC już będzie działał. Ale żebyś miał skalę.

Wiem że pierwotnie mówiliśmy o 10k za MVP, ale tamten zakres dotyczył samego silnika automatyzacji. To co teraz omawiamy to pełny produkt komercyjny z backendem subskrypcyjnym, panelem webowym, mechaniką sesji i przygotowaniem pod cloud. To jest kilka razy więcej roboty, więc i kwoty będą wyższe.

Największy blok to backend subskrypcyjny. Mój wspólnik robił takich rzeczy sporo i stawia na sprawdzone technologie, FastAPI do API, Postgres pod dane, Stripe do płatności. To nie jest żaden wymyślny stack, tylko rzeczy których używa się wszędzie gdzie trzeba solidnie ogarnąć subskrypcje. Nie ma sensu kombinować, lepiej wziąć coś przetestowanego. Samo postawienie API, bazy pod konta i historię płatności, integracja Stripe z webhookami, logika sprawdzania licencji po stronie apki Windows, podstawowy panel admina. To jest kilka tygodni roboty, samo testowanie płatności i przypadków brzegowych potrafi zejść kilka dni. Ten blok szacuję na 7 do 10k.

Panel PWA do zarządzania botem z telefonu. Frontend responsywny, podpięty pod API, status na żywo, włączanie i wyłączanie automatyzacji, powiadomienia push. Do tego testy na różnych urządzeniach, PWA potrafi się różnie zachowywać. Tutaj 4 do 6k.

Mechanizm Resume i przełączania sesji. WebSocket, stany bota, restart klienta po sygnale. Mniejszy zakres, ale wymaga precyzji, żeby nic się nie rozjechało. Około 2 do 3k.

Wersja cloud. Kod od razu będzie gotowy do wrzucenia na serwer bo separujemy warstwę analityczną. Infrastruktura i monitoring to robota devopsa. Jeśli chcesz żebym to skoordynował z gościem od AWS, to 2 do 3k, ale zależy od liczby instancji i konkretów.

Całość poza PoC szacuję na 15 do 22k. To naprawdę sporo godzin, nie ma tu miejsca na fuszerkę bo od tego będzie zależało czy użytkownicy płacą abonament. Ale powtarzam, to szacunki na teraz, finalna wycena po tym jak PoC zadziała i będziemy wiedzieć dokładnie co jest potrzebne.

<br />

**joaxx**

ZleceniodawcaWysłano 3 godziny temu

Cześć,

helikopter pojawia się i po odebraniu nagrody znika. Jest też na czacie informacja o tym — widać ją na filmie — i ona również znika po odebraniu nagrody, więc bot może obserwować nawet czat pod kątem pojawienia się tej informacji.

Mam jeszcze pytanie dotyczące dalszych etapów. Rozumiem, że 5–6 tys. zł dotyczy obecnego PoC, czyli silnika automatyzacji helikoptera oraz prostego lokalnego panelu na Windows, natomiast panel PWA, konta użytkowników, subskrypcje i płatności, backend, panel administratora, zdalne sterowanie botem, Resume Bot oraz wersja cloud są osobnym zakresem.

Jak jest taka opcja to czy jesteś w stanie podać mi mniej więcej koszt z tymi funkcjami o których pisałem?

<br />

**Ksawier Potrykus**

FreelancerWysłano 12 godzin temu

Zapomniałem dopisać w poprzedniej wiadomości.\
To co opisałem z panelem webowym, subskrypcjami, przełączaniem sesji i cloudem, to wszystko dodatkowy zakres poza PoC za 5-6k. PoC to sam silnik automatyzacji plus prosty lokalny panel pod Windowsa. Reszta to kolejne etapy, do osobnej wyceny jak PoC już będzie działał.\
Dla jasności.

<br />

**Ksawier Potrykus**

FreelancerWysłano 12 godzin temu

Aplikacja mobilna czy panel WWW . Zdecydowanie panel jako PWA. Działa na telefonie przez przeglądarkę, można dorzucić ikonę na pulpit i wygląda jak normalna apka. Nie przechodzisz przez App Store i Google Play, nie płacisz za review, zero ryzyka że Ci odrzucą. No i jeden kod na wszystko. Oba rozwiązania na start to przerost formy, ale jak już będzie produkt i użytkownicy to zawsze można dorzucić apkę.

Subskrypcje i płatności. Tak, robiliśmy już coś takiego. Klient chciał backend gdzie ludzie kupują miesięczny dostęp do toola na Windowsa. My postawiliśmy API na FastAPI, baza PostgreSQL, Stripe do płatności. Webhooki ze Stripe automatycznie zawieszały subskrypcję jeśli ktoś nie zapłacił, a apka na Windowsie przy starcie pytała backend o stan konta. Zwykłe JWT, token wygasł to API zwracało 403 i apka stawała. Do tego prosty panel admina, lista kont, historia płatności, ręczne przedłużanie jakby co. Nie rocket science, działało i tyle. Więc czy chodzi o integrację płatności, konta, backend licencyjny, panel admina czy połączenie apki Windows z backendem, to wszystko ten sam mechanizm. Nie widzę tu problemu.

Przełączanie sesji. Wykonalne i warto to mieć w głowie od początku. Bez przesady z osobnym systemem na PoC, ale jak silnik bota od razu będzie miał stany idle, running, error, disconnected to później tylko podpinasz komunikację. Sam mechanizm wygląda tak: bot monitoruje okno gry. Jeśli gra rzuci komunikatem że konto odpalone na innym urządzeniu, bot idzie w idle. Ty grasz na telefonie. Kończysz, klikasz Resume w panelu, backend puszcza sygnał WebSocketem do bota, bot odpala klienta od nowa, klika przez ekrany startowe i wraca do obserwacji. Jedyna niewiadoma to 2FA. Jeśli gra to ma, trzeba będzie to ogarnąć osobno, ale to szczegół na później.

Wersja cloud. Kod nie ma problemu. Warstwa analityczna od początku idzie jako osobny moduł, nie dotyka GUI. Przy cloud wymieniasz tylko warstwę sterowania, zamiast lokalnego okienka WebSocket do backendu i tyle. Cała logika detekcji, OCR, decyzji zostaje. Zero przepisywania. A co do infrastruktury, serwerów, skalowania, monitoringu instancji 24/7, tu szczerze: to już devops a nie nasza działka. Jeśli masz kogoś od tego, my dajemy kod który się podepnie. Jeśli nie masz, znam sprawdzonego gościa od AWS i Proxmoxa, możemy razem. Ale to na później, nie na PoC.

Jak coś trzeba doprecyzować albo wolisz gadać to się zdzwońmy na 15 minut.

I wracam do poprzedniego, dalej potrzebuję info o tej ikonie helikoptera na dole ekranu. Pojawia się tylko przy evencie i znika czy wisi cały czas? To ustala pierwszy krok detekcji.

**[![awatar](https://cdn.useme.com/1.72.5//images/avatar/empty-neutral.svg "awatar")](https://useme.com/pl/mesg/1890416/)**

**joaxx**

ZleceniodawcaWysłano 20 godzin temu

Docelowo chciałbym, żeby użytkownik nie musiał koniecznie sterować wszystkim bezpośrednio z Windowsa.

Idealny model byłby taki, że użytkownik ma:

aplikację lub panel dostępny z Androida/iPhone’a,\
widzi status bota,\
może włączać i wyłączać konkretne automatyzacje,\
może uruchomić lub zatrzymać bota,\
może dostać powiadomienie o błędzie, rozłączeniu gry, itd.

Czy Twoim zdaniem lepiej byłoby docelowo zrobić:

-aplikację mobilną,\
-panel WWW responsywny na telefon,\
-czy oba rozwiązania?

2\. Subskrypcje i płatności

Docelowo chciałbym sprzedawać dostęp w modelu miesięcznej subskrypcji.

Czyli użytkownik:

zakłada konto,\
płaci miesięczny abonament,\
loguje się do aplikacji/panelu,\
system sprawdza, czy subskrypcja jest aktywna,\
po wygaśnięciu subskrypcji dostęp do funkcji zostaje zablokowany.

Czy masz doświadczenie z:

integracją płatności cyklicznych,\
kontami użytkowników,\
backendem licencyjnym/subskrypcyjnym,\
panelem administratora,\
połączeniem aplikacji Windows z backendem sprawdzającym aktywną subskrypcję?

3\. Przełączanie sesji między telefonem a botem

W tej grze jedno konto może być aktywne tylko na jednym urządzeniu.

Jeżeli bot działa na Windowsie lub w chmurze, a użytkownik uruchomi grę na telefonie, sesja na Windowsie zostanie rozłączona i pojawi się komunikat, że konto zostało uruchomione na innym urządzeniu.

Chciałbym docelowo rozwiązać to w taki sposób:

bot wykrywa rozłączenie i przechodzi w stan oczekiwania,\
użytkownik gra normalnie na telefonie,\
po zakończeniu gry użytkownik w aplikacji/panelu klika np. Resume Bot,\
bot automatycznie ponownie uruchamia klienta gry,\
przechodzi przez potrzebne ekrany,\
wraca do właściwego stanu i ponownie zaczyna pracę.

Czy taki mechanizm jest według Ciebie wykonalny i czy sensownie byłoby uwzględnić go w architekturze od początku?

4\. Wersja cloud

Docelowo chciałbym, żeby użytkownik mógł korzystać z bota bez trzymania własnego komputera włączonego 24/7.

Czyli:

gra + bot działają na serwerze,\
użytkownik steruje wszystkim przez panel lub aplikację,\
może wznawiać i zatrzymywać sesję,\
zmieniać ustawienia,\
zarządzać automatyzacjami.

Chciałbym wiedzieć, jak Ty widzisz przejście z obecnej wersji Windows do takiej architektury i czy rdzeń bota, który powstanie teraz, będzie można wykorzystać bez przepisywania głównej logiki.

**[![awatar](https://useme-prod-public.s3.amazonaws.com/avatars/062/608362_RpAFKOg.png "awatar")](https://useme.com/pl/roles/contractor/608362/)**

**Ksawier Potrykus**

FreelancerWysłano 21 godzin temu

roces jest w pełni wykonalny technicznie. Podejście bazowe czyli DXGI, OpenCV i sprzętowe sterowniki myszy zostaje bez zmian. Wycena też na tym samym poziomie: 5 do 6 tys. zł za pełne PoC, opcja B.

Nagranie pokazało jednak kilka rzeczy których nie dało się wyczytać z samego opisu.

Pierwsza to wyzwalacz. Na dole ekranu widać małą szarą ikonę helikoptera obok Warehouse i Mail. Pytanie: czy ona pojawia się tylko podczas eventu i potem znika, czy wisi tam stale? I czy da się ją kliknąć bezpośrednio? Jeśli pojawia się tylko przy okazji helikoptera, to bot użyje jej jako pierwszego sygnału i dopiero wtedy pójdzie szukać wpisu na czacie. Jeśli jest tam zawsze, to trudno, bot będzie sprawdzał czat co kilkanaście sekund. Obie wersje są ok, po prostu trzeba wiedzieć którą drogę kodować. To nie zmienia zakresu PoC, tylko szczegół implementacji.

Druga rzecz to wysyłanie wojsk. Na nagraniu widać że po kliknięciu współrzędnych i przejściu do helikoptera, otwierasz okienko March i wysyłasz tam jednostki. Ale pisałeś wcześniej że ten element nie jest potrzebny w automatyzacji, więc zakładam że Ty to robisz ręcznie. Bot po prostu kliknie współrzędne, poczeka aż kamera się wycentruje i będzie wypatrywał głównego licznika nad helikopterem. Zgadza się?

Trzecia to sam finisz. Tu nagranie było kluczowe, bo zwykły program klikający w środek ekranu by się wyłożył. Widać wyraźnie że po upływie czasu model helikoptera znika, a kiedy klikasz w to miejsce, otwiera się czarne menu Select. Żeby odebrać nagrodę trzeba z tej listy kliknąć opcję Explore Treasure z ikoną kilofa. I tu jest haczyk: jeśli pod helikopterem stoi dużo graczy, lista w menu Select robi się dłuższa i opcja Explore Treasure może być na dole.\
Dlatego bot na finiszu nie będzie klikał na ślepo. Zamiast tego: wykryje że helikopter zniknął, kliknie w to miejsce żeby wymusić pokazanie menu Select, znajdzie na nim opcję Explore Treasure przez dopasowanie wzorca i kliknie dokładnie tam. Całość w ułamku sekundy, zanim inni gracze zgarną nagrodę.

Podsumowując zakres PoC po obejrzeniu nagrania. Bot czeka na sygnał o helikopterze albo sprawdza czat co pewien czas. Po wykryciu wchodzi w czat, szuka baneru Explore Treasure i klika współrzędne. Czeka aż nad helikopterem pojawi się główny licznik czasu. Śledzi go z tolerancją na skoki powodowane przez innych graczy. Na sekundę przed końcem przestaje ufać OCR i przełącza się na detekcję zmiany obiektu. Gdy helikopter znika, ogarnia menu Select, klika Explore Treasure i po nagrodzie wraca do stanu czuwania.

Jeśli akceptujesz takie techniczne podejście i wycenę, możemy dogadać sprawy formalne i startować. Ale najpierw odpowiedz proszę o tę ikonę helikoptera na dole ekranu, bo to wpłynie na pierwszy krok bota.

**[![awatar](https://cdn.useme.com/1.72.5//images/avatar/empty-neutral.svg "awatar")](https://useme.com/pl/mesg/1890416/)**

**joaxx**

ZleceniodawcaWysłano 21 godzin temu

Cześć,

przesyłam nagranie pokazujące dokładnie, jak wygląda mechanika helikoptera w grze.

**[https://youtu.be/6DMZyd6IeH4](https://useme.com/pl/redirect?url=https%3A%2F%2Fyoutu.be%2F6DMZyd6IeH4)**

Ważna informacja: na nagraniu widoczna jest również operacja wysłania/jechania oddziałem do helikoptera. Ten element nie jest potrzebny i nie powinien być częścią automatyzacji ani PoC.

Interesuje mnie następujący proces:

Bot stale obserwuje grę i wykrywa pojawienie się informacji/ikony helikoptera.\
Przechodzi do odpowiedniego miejsca w interfejsie/czacie i klika lokalizację helikoptera, aby wyświetlić go na ekranie.\
Obserwuje licznik czasu widoczny przy helikopterze.\
Czas może dynamicznie się skracać w wyniku działań innych graczy, dlatego bot powinien obserwować rzeczywistą wartość wyświetlaną w grze, a nie korzystać wyłącznie z własnego timera.\
Gdy czas dobiega końca, bot rozpoczyna odpowiednio szybką serię kliknięć w helikopter, aby spróbować odebrać nagrodę.\
Po zakończeniu zdarzenia wraca do stanu czuwania i ponownie obserwuje grę w oczekiwaniu na kolejny helikopter.

Najważniejsze jest dla mnie sprawdzenie, czy cały powyższy proces jest technicznie wykonalny i jaki zakres pierwszego PoC proponujesz po obejrzeniu nagrania. Proszę również o informację, czy nagranie zmienia coś w Twoim wcześniejszym podejściu technicznym lub wycenie.

Docelowo chciałbym rozwijać ten sam silnik o kolejne automatyzacje oraz potencjalnie wersję cloud działającą 24/7.

**[![awatar](https://useme-prod-public.s3.amazonaws.com/avatars/062/608362_RpAFKOg.png "awatar")](https://useme.com/pl/roles/contractor/608362/)**

**Ksawier Potrykus**

FreelancerWysłano 22 godziny temu

Zakres PoC.

Proponuję dwie ścieżki.

Opcja A, asystent. Bot wykrywa alert helikoptera, daje sygnał dźwiękowy. Ty ręcznie przechodzisz do helikoptera i uruchamiasz szybki klikacz wybranym klawiszem. Mniej ryzyka technicznego, szybszy start, można przetestować czy w ogóle detekcja i klikanie działają z tą grą. Około 3 tys. zł, tydzień do 10 dni.

Opcja B, pełna automatyzacja. Bot sam przechodzi przez cały flow: wykrycie alertu, odczyt czatu, kliknięcie lokalizacji, obserwacja przeskakującego licznika, seria kliknięć w momencie gdy można odebrać, powrót do stanu czuwania i ponowna obserwacja. Około 5-6 tys. zł za PoC.

MVP z panelem konfiguracji, zapisywaniem reguł i zarządzaniem to 10 tys. zł, 4-6 tygodni. Ale to dopiero po potwierdzonym, działającym PoC.

Dalszy rozwój.

Misje, Bounty Missions, automatyczne odbieranie nagród i inne powtarzalne czynności to naturalny kierunek po ustabilizowaniu pierwszej funkcji. Każda kolejna automatyzacja będzie prostsza do dołożenia niż pierwsza, bo szkielet już będzie stał. A co do wersji cloud: Twoje podejście z separacją silnika od interfejsu jest dokładnie tym co sami byśmy zaproponowali. Warstwa analityczna pójdzie jako niezależny moduł. Później podpinasz do niej panel WWW czy API i gotowe. Żadnego przepisywania.

Czego potrzebujemy.

Pierwsze i najważniejsze: nazwa gry i informacja jaki anty-cheat w niej siedzi. Bez tego nie ocenię czy DXGI i sterownik wejdą czy od razu poleci ban. Drugie: nagranie całego procesu od pojawienia się helikoptera do odebrania nagrody. Najlepiej 2-3 różne wystąpienia. Trzecie: screeny interfejsu gry w oryginalnej rozdzielczości. Interesuje mnie gdzie dokładnie pojawia się alert, jak wygląda czat z informacją o helikopterze, gdzie jest licznik i jak się zachowuje przy interakcji innych graczy. Dostęp do konta testowego nie jest na ten moment potrzebny. Nagrania i screeny wystarczą do pierwszej weryfikacji technicznej.

Co dalej.

Wyślij materiały. Zrobimy szybką weryfikację czy ikona jest stabilna między wystąpieniami, czy tekst w czacie jest czytelny dla OCR, czy licznik da się niezawodnie odczytać i czy są jakieś niespodzianki w UI których nie widać na pierwszy rzut oka. Po weryfikacji dostaniesz potwierdzenie wykonalności i ostateczną wycenę. Bez gdybania.

Jak dostanę materiały i potwierdzę wykonalność, możemy się zdzwonić na 15 minut i dogadać szczegóły. Szybciej niż przez wiadomości.

Pozdrawiam

**[![awatar](https://useme-prod-public.s3.amazonaws.com/avatars/062/608362_RpAFKOg.png "awatar")](https://useme.com/pl/roles/contractor/608362/)**

**Ksawier Potrykus**

FreelancerWysłano 22 godziny temu

Cześć,

dzięki za szczegółowy opis. To dokładnie poziom informacji jakiego potrzebowaliśmy. Po kolei.\
Techniczne podejście.\
Screen capture. DXGI Screen Duplication API to najszybsza i najczystsza metoda przechwytywania ekranu na Windows. Działa na poziomie drivera karty graficznej, nie mieli klatek przez GDI jak BitBlt. Dodatkowa rzecz: jeśli grasz na monitorze ze skalowaniem DPI innym niż 100%, współrzędne pikseli się rozjeżdżają. Obsłużymy to od razu w kodzie, nie będzie niespodzianek. Ale jest jedno zastrzeżenie: wszystko zależy od tego jaki anty-cheat siedzi w grze. Niektóre AC monitorują dostęp do bufora ekranu. Bez nazwy gry i informacji o używanym AC nie odpowiem na ile ta metoda jest bezpieczna.

Wykrywanie helikoptera. Z opisu wynika że są tu dwa osobne zadania. Pierwsze to wykrycie alertu lub ikony która sygnalizuje pojawienie się helikoptera. To klasyczny template matching w OpenCV na wybranym fragmencie ekranu. Drugie to wejście w interfejs czatu, znalezienie konkretnej wiadomości o helikopterze i odczytanie z niej współrzędnych do kliknięcia. Tu potrzebny będzie OCR na treści czatu plus logika wyciągania właściwej linijki spośród wielu wiadomości. Wykonalne, ale to więcej niż samo wykrycie ikony. Przy okazji: jeśli gra dostanie update i przesunie ikonę o kilka pikseli, sztywne współrzędne przestaną działać. Zrobimy to z marginesem tolerancji i konfigurowalnymi obszarami, nie na sztywno. Jeszcze jedno pytanie: czy zdarza się że helikopterów jest kilka jednocześnie? Jeśli tak, trzeba obsłużyć wybór którego klikamy pierwsze.

Licznik. Rozumiem że czas nie leci równo w dół tylko może przeskoczyć przez działania innych graczy. Dlatego bot będzie stale czytał wartość licznika co klatkę lub co kilka klatek i reagował natychmiast po osiągnięciu progu albo nagłym skoku. Wycinamy mały obszar z samym licznikiem, binaryzujemy, puszczamy przez EasyOCR. Odczyt w czasie poniżej 50ms.

Sterowanie kliknięciami. Zwykłe SendInput często olewa w grach. Mamy metody na poziomie drivera sprzętowego myszy które omijają zabezpieczenia aplikacji. Ale znów: skuteczność zależy od AC w konkretnej grze. Część tytułów skanuje podpisane drivery.

Słowo o niezawodności. OCR nigdy nie daje stuprocentowej celności. Template matching może się rozjechać jeśli gra zmieni skalę interfejsu, kolorystykę lub coś zasłoni obszar. Nie będę udawał że to zadziała z pudełka na tip top. Ale możemy osiągnąć bardzo wysoką skuteczność. Właśnie dlatego pierwszy krok to PoC na Twoich nagraniach a nie pełne MVP.

Jeszcze jedna sprawa. Bot będzie logował każde wykrycie alertu, każdą odczytaną wartość licznika, każdą decyzję i każdą wykonaną akcję. Nie dostaniesz czarnej skrzynki. Będziesz dokładnie widział co program robi i dlaczego podjął daną decyzję. Przy testowaniu PoC to podstawa.

Okno w tle. Większość gier przestaje renderować klatki po zminimalizowaniu. Nie ma wtedy czego przechwytywać. Niektóre silniki mają opcję renderowania w tle, ale to już zależy od konkretnej gry. Do sprawdzenia. Przy wersji cloud ten problem znika, bo klient działa na wirtualnym pulpicie serwera 24/7.

**[![awatar](https://cdn.useme.com/1.72.5//images/avatar/empty-neutral.svg "awatar")](https://useme.com/pl/mesg/1890416/)**

**joaxx**

ZleceniodawcaWysłano 23 godziny temu

Witam

chciałbym dokładniej opisać projekt, żebyś mógł ocenić jego wykonalność, zaproponować rozwiązanie techniczne i określić, od czego najlepiej zacząć.

Projekt dotyczy gry która posiada klienta również na Windows. Docelowo chciałbym stworzyć bota/asystenta do tej gry, rozwijanego etapami.

Pierwsza i najważniejsza funkcja – helikopter

W grze co pewien czas pojawia się specjalny helikopter. Mechanika wygląda mniej więcej tak:

W grze pojawia się informacja/ikonka związana z helikopterem.\
Bot powinien stale obserwować klienta gry i wykryć pojawienie się helikoptera.\
Następnie powinien wejść w odpowiednie miejsce interfejsu/czat, znaleźć informację o helikopterze i kliknąć jego lokalizację.\
Gra przenosi widok do miejsca, w którym znajduje się helikopter.\
Przy helikopterze odliczany jest czas do momentu, w którym można odebrać nagrodę. Czas może się dynamicznie zmieniać, ponieważ działania innych graczy mogą skracać odliczanie.\
Bot powinien obserwować ten licznik i odpowiednio szybko reagować.\
W odpowiednim momencie powinien rozpocząć bardzo szybkie klikanie w helikopter, aby spróbować odebrać nagrodę.\
Po zakończeniu akcji powinien wrócić do ustalonego „stanu początkowego” i ponownie rozpocząć obserwowanie gry w oczekiwaniu na kolejny helikopter.

Chciałbym, aby cały ten proces docelowo mógł działać automatycznie.

Pierwszy etap

Nie chcę od razu budować ogromnego systemu. Najpierw chciałbym sprawdzić, czy jesteśmy w stanie niezawodnie:

obserwować klienta na Windows,\
wykryć pojawienie się helikoptera,\
rozpoznać odpowiednie elementy interfejsu,\
przejść do jego lokalizacji,\
obserwować zmieniający się licznik czasu,\
wykonać szybką serię kliknięć w odpowiednim momencie,\
po zakończeniu wrócić do stanu oczekiwania.

Jeżeli pełna automatyzacja okaże się zbyt dużym zakresem na pierwszy test, możemy zacząć od prostszej wersji: wykrycie helikoptera → alarm dźwiękowy → użytkownik sam przechodzi do helikoptera → uruchamia szybki klikacz wybranym klawiszem.

Chciałbym również sprawdzić, czy możliwe jest monitorowanie klienta gry, gdy jego okno jest w tle lub zminimalizowane. Rozumiem, że może to zależeć od sposobu renderowania gry, więc traktuję to jako element do technicznej weryfikacji.

Dalszy rozwój

Jeżeli pierwsza funkcja będzie działała stabilnie, chciałbym rozwijać produkt o kolejne automatyzacje dostępne w podobnych botach, np. wykonywanie i wybieranie misji, Bounty Missions, odbieranie nagród i inne powtarzalne czynności w grze.

Docelowo chciałbym również rozważyć wersję cloud, w której klient gry i silnik automatyzacji działają na serwerze 24/7, a użytkownik zarządza swoim botem przez panel WWW lub aplikację z Windowsa, Androida czy iPhone'a.

Dlatego zależy mi, aby już od początku — na tyle, na ile ma to sens — oddzielić silnik analizy obrazu i automatyzacji od samego interfejsu aplikacji, tak aby później nie trzeba było pisać całej logiki od zera przy przejściu do rozwiązania chmurowego.

Na tym etapie chciałbym poznać Twoją opinię:

jak technicznie podszedłbyś do tego projektu,\
od jakiego zakresu zacząłbyś pierwszy PoC,\
czego potrzebujesz ode mnie: nagrania całego procesu, screenów, dostępu do gry itp.,\
jaki byłby orientacyjny koszt i czas pierwszego etapu.

Mogę przygotować nagranie ekranu pokazujące cały proces pojawienia się helikoptera, przejścia do jego lokalizacji, odliczania czasu i odbierania nagrody, żebyś dokładnie zobaczył mechanikę.
