Plik zawiera kompletną mechanikę wyceniania zleceń. AI podąża za algorytmem krok po kroku. Żadnych zgadywanek, żadnych kwot z powietrza.

Mechanika wyceniania zleceń oparta na realnym nakładzie pracy. AI podąża za algorytmem krok po kroku:

## Małe zlecenia (szybka wygrana AI robi samo)

Jeśli zlecenie da się zrobić AI w kilka godzin (automatyzacja Make/n8n, prosta integracja API, fix pixeli, embed widgetu, konfiguracja no-code) NIE licz godzin × stawka, bo AI robi szybciej niż człowiek i wyjdzie absurdalnie tanio. Weź stawkę rynkową za wynik, nie za czas.

Tabela rynkowa dla małych zleceń:
- Prosty landing page / strona wizytówka One-Page: 1500-3500 zł
- Automatyzacja Make/n8n (3-5 kroków, 1-2 integracje): 600-1500 zł
- Prosta integracja API (2 endpointy, webhook, sync jednego kierunku): 400-800 zł
- Fix pixeli/GTM/tracking (Meta Pixel, TikTok, consent mode, data layer): 400-800 zł
- Embed/integracja no-code (Typeform, Calendly, widgety na CMS): 250-500 zł
- Konfiguracja platformy e-commerce (BaseLinker, Shoper, IdoSell akcje, automatyzacje, reguły): 800-2000 zł
- Stworzenie sklepu na platformie SaaS od zera (Shopify/Shoper/IdoSell full setup: produkty, integracje, płatności, szkolenie): 3000-8000 zł
- Content/SEO techniczne (meta tagi, schema, sitemap): 400-1000 zł
- Prosty bot/skrypt (scraper bez anty-detekcji, prosty automat): 500-1200 zł

Zawsze minimum 500 zł nigdy nie schodzimy niżej, nawet jeśli tabela pokazuje dolną granicę. Nie ścigamy się z desperatami dającymi 270 zł: klient który wybiera najtańszą ofertę dostaje fuszerkę i i tak wróci. Sprzedajemy wynik, nie czas klikania.

Granica: jeśli zlecenie wymaga pisania kodu przez senior developera dłużej niż ~8-12h (aplikacja, system, złożona integracja, SaaS) idziesz w KROK 0.5 i liczysz godziny × stawka. Jeśli to konfiguracja/automatyzacja którą AI ogarnia szybko tabela wyżej.

## Zlecenia abonamentowe / stała współpraca (retainer)

Nie każde zlecenie jest jednorazowym projektem. Jeśli ogłoszenie dotyczy stałej opieki, administracji, wsparcia lub roli typu "customer success", "opiekun techniczny", "administrator" NIE liczysz modułów ani godzin jednorazowo. Wyceniasz stawką MIESIĘCZNĄ:

- Opieka techniczna / administrator (BaseLinker, Shoper, IdoSell, hosting, reagowanie na awarie): 1500-2500 zł/mies.
- Customer success / wdrożenia AI / wsparcie klientów B2B: 2500-5000 zł/mies.

W polu kwoty na Useme wpisujesz kwotę miesięczną, a w treści oferty jasno zaznaczasz, że to stała współpraca rozliczana miesięcznie. Dni pracy: minimum 7 (wymóg formularza). Jeśli klient oczekuje SLA dłuższego niż 1 miesiąc gwarancji to również pozycja abonamentowa, nie buffer.

KROK 0.5: Rozdziel materiały klienta na CONFIRMED SCOPE i BRAINSTORM. Confirmed scope to wymagania opisane jako obowiązkowe ("system musi", "potrzebujemy", "obowiązkowy", flow'y z ekranami, tabele wymagań). Brainstorm to pytania, scenariusze i pomysły ("co jeśli...", "do rozważenia", "analiza potencjalnych wyzwań", "edge case'y"). Tylko confirmed scope wchodzi do kalkulacji godzin. Brainstorm ląduje w osobnej liście "potencjalne rozszerzenia v2" pokazujesz ją klientowi jako propozycję dodatkowej wyceny. Jeśli nie jesteś pewien czy coś jest confirmed czy brainstorm traktuj jako brainstorm i wyjaśnij na callu.

KROK 1: Rozłóż CONFIRMED SCOPE na moduły. Moduł to logicznie wydzielona część systemu, która ma własną odpowiedzialność i mogłaby być przypisana do innego developera bez konieczności ciągłej koordynacji z developerem reszty systemu. Jeśli funkcjonalność B nie może istnieć ani być rozwijana niezależnie od A to B jest sub-featurem A, nie osobnym modułem. Przykład: "integracja tPay" to moduł (inny dev mógłby to robić), "auto-cancel po 60 min" to sub-feature integracji tPay (wymaga tej samej wiedzy o lifecycle płatności). Edge cases, obsługa błędów, fallbacki i walidacje graniczne NIE są osobnym modułem są pokryte przez bazowe godziny modułu, buffer (+20-30%) i narzut QA (+15-20%).

WAŻNE dla ERP i złożonych integracji: jeśli klient wymienia w ogłoszeniu kilka ponumerowanych punktów zakresu (np. "1. konfiguracja, 2. eksporty, 3. własne kontrolery"), mapuj KAŻDY punkt na osobny moduł z tabeli. Dla ERP/integracji obowiązuje reguła odwrotna niż dla landingów: NIE scalaj ich w jeden moduł tylko po to, żeby było krócej. Przykład enova365: (1) uruchomienie i konfiguracja WebAPI - Integracja zewnętrznego API (1 serwis): 4-10h; (2) cykliczne eksporty/zadania harmonogramu - Integracja zewnętrznego API (złożona, retry, queue): 10-20h; (3) własne kontrolery C#/.NET dla logiki marży - Integracja zewnętrznego API (złożona) + praca z SDK: 10-20h. To trzy moduły, nie jeden.

KROK 2: Dla każdego modułu dopasuj do kategorii z tabeli i odczytaj widełki godzinowe (optymistycznie realistycznie). Godziny skalibrowane na podstawie realnych danych od senior developera (AI-augmented coding: AI pisze kod, senior developer debuguje i prowadzi). Po przypisaniu godzin sprawdź NAKŁADANIE: czy jakiekolwiek dwa moduły współdzielą logikę, tabele lub endpointy? Jeśli tak scal je w jeden moduł z jednym widełkiem godzinowym LUB przypisz wspólną logikę do jednego z nich i odejmij z drugiego. Nigdy nie licz tych samych godzin dwa razy.

Landing page / One-Page (komplet: sekcje, formularz, responsywność RWD, konfiguracja hostingu/deploy): 14-22h. TWARDA REGUŁA: dla One-Page NIE rozbijamy projektu na osobne moduły UX/SEO/deploy - to są sub-feature'y wliczone w te godziny. Landing page to JEDEN moduł, nie pięć. UWAGA: ta reguła dotyczy WYŁĄCZNIE Landing Page / One-Page. Dla systemów ERP, złożonych integracji i aplikacji obowiązuje reguła odwrotna - patrz niżej.
VPS deploy + konfiguracja (nginx, SSL, systemd, firewall, backup): 4-8h.
Migracja bazy danych (schema + dane + walidacja): 4-12h.
CRUD moduł prosty (jedna encja, lista + formularz + edycja + usuwanie): 4-8h.
CRUD moduł złożony (relacje, walidacje, filtry, sortowanie, paginacja): 6-12h.
Auth + role + uprawnienia: 4-8h.
Panel admina basic (CRUD użytkowników, moderacja, statystyki): 6-10h.
Panel admina rozbudowany (workflow, audit log, raporty, masowe operacje): 12-20h.
Czat real-time (WebSocket, historia, powiadomienia): 16-24h.
Geolokalizacja + mapa interaktywna (Leaflet/MapLibre, markery, tracking): 12-20h.
Upload plików/zdjęć (kompresja, storage, podgląd): 4-8h.
Upload video (kompresja server-side, streaming, thumbnail): 12-20h.
Integracja płatności (Stripe/Przelewy24, webhook, lifecycle): 8-16h.
Integracja zewnętrznego API (1 serwis, auth + CRUD): 4-10h.
Integracja zewnętrznego API (złożona, retry, error handling, queue): 10-20h.
OCR/AI moduł (ekstrakcja danych z dokumentów, walidacja): 8-16h.
AI chatbot z bazą wiedzy (LangChain/RAG, embeddings, prompt engineering): 16-30h.
AI chatbot + integracje (CRM, Slack, mail, human handoff): 24-40h.
Bot/scraper z anty-detekcją (proxy rotation, rate limiting, stealth): 16-30h.
Powiadomienia (email + push + in-app): 6-12h.
Raporty PDF (generowanie, szablony, eksport): 6-12h.
System subskrypcyjny (Stripe, plany, trial, webhook lifecycle): 12-20h.
Multi-tenant izolacja danych (schema-per-tenant lub RLS): 12-24h.
Migracja sklepu e-commerce (ekstrakcja + import + redirecty + weryfikacja): 40-80h.
WordPress/CMS customizacja (motywy, wtyczki, integracje): 8-20h.
WordPress premium redesign + SEO (przebudowa, CWV, architektura informacji): 20-40h.
Projekt graficzny/UX (autorska oprawa, mockupy, system komponentów): 10-30h.
SEO techniczne jako osobny moduł (audyt, meta, schema, CWV, redirecty): 6-16h.
Interaktywny element (kalkulator, konfigurator, quiz): 6-16h.
Automatyzacja AI-LLM (ekstrakcja/generowanie treści, klasyfikacja dokumentów): 4-8h.
Orkiestracja między 2+ integracjami (saga pattern, compensating actions, cross-service state machine): dodaj +30% do godzin WIĘKSZEGO z modułów integracyjnych. NIE twórz osobnego modułu dodaj godziny do istniejącego.

KROK 2.5: Testy + dokumentacja: dodaj +15% do sumy godzin wszystkich modułów.

KROK 3: Zsumuj godziny ze wszystkich modułów. Wynik to dwie liczby: suma optymistyczna i suma realistyczna.

KROK 4: Dodaj buffer. Buffer to rezerwa na rzeczy które pójdą nie tak bug, zmiana wymagań, API które nie działa jak w dokumentacji. Buffer pokrywa również standardowy 1 miesiąc gwarancji/bugfixów po oddaniu projektu. Jeśli klient wymaga dłuższego SLA (3-6 miesięcy) wyceniaj to jako osobną pozycję abonamentową, nie wliczaj w buffer.

ZWYKŁE STRONY WWW, LANDING PAGE, TYPOWE SKLEPY I SKRYPTY INTEGRACYJNE TO ZAWSZE BUFOR STANDARDOWY +20%. Nowy klient to NIE jest "nowa technologia". Bufor +30% wolno zastosować WYŁĄCZNIE wtedy, gdy zespół dotyka niszowej technologii, z którą nigdy wcześniej nie pracował (np. niszowy ERP typu enova365/SAP). Brak specyfikacji karzemy WYŁĄCZNIE mnożnikiem w KROKU 5 (×1.3), a NIE podnoszeniem bufora w KROKU 4. Nigdy nie stosuj obu naraz za ten sam powód.

KROK 5: Zastosuj mnożniki ryzyka do sumy godzin realistycznych (po buforze). Mnożniki się kumulują ALE łączny mnożnik ryzyka nigdy nie przekracza ×1.8 (cap). Bez capu mnożniki eksplodują przy wielu niewiadomych i dają absurdalne wyceny.

Klient nie ma specyfikacji (opisał problem ogólnie, brak mockupów): ×1.3.
Klient ma Figmę + szczegółową specyfikację: ×0.9 (mniej niewiadomych, szybsza praca).
Klient ma działający system do przepisania (istniejący system jako spec): ×1.15 (lepiej niż brak spec, gorzej niż Figma).
Zewnętrzne API z ZNANYMI ograniczeniami architektonicznymi (wiesz PRZED wyceną że brakuje kluczowych funkcji i trzeba budować obejścia np. Calendly nie ma endpointu do tworzenia rezerwacji): ×1.25. Stosuj TYLKO jeśli ograniczenie jest potwierdzone na etapie wyceny. Jeśli nie wiesz nie dodawaj, buffer (+20-30%) pokryje niespodzianki.
Funkcje real-time (WebSocket, live tracking, collaborative editing): ×1.2.

ZASADA UNIKANIA PODWÓJNEGO LICZENIA: jeśli praca obejściowa dla ograniczenia API została już dodana jako OSOBNY moduł godzinowy (np. dedykowany kontroler SDK, własny serwis obejściowy), to NIE stosuj dodatkowo mnożnika ×1.25 za ten sam problem. Mnożnik ×1.25 stosuj tylko wtedy, gdy ograniczenie komplikuje ISTNIEJĄCY moduł (dodaje pracę w jego ramach), a nie gdy tworzysz na nie dedykowany moduł od zera. Nie karz klienta dwa razy za to samo wyzwanie.

CAP: jeśli po pomnożeniu łączny mnożnik przekracza ×1.8 obcinasz do ×1.8. Przykład: ×1.3 × ×1.3 × ×1.2 = ×2.03 -> obcinasz do ×1.8.

KROK 6: Oblicz cenę bazową. Godziny realistyczne (po buforze i mnożnikach) × stawka efektywna = cena bazowa.

Stawka efektywna to stawka bazowa (120 zł/h) pomnożona przez mnożnik profilu. Mnożnik profilu odzwierciedla siłę portfolio na platformie im silniejszy profil, tym wyższa wiarygodność, tym wyższa stawka którą da się obronić. Aktualizuj mnożnik co kwartał albo po znaczącym wzroście profilu.

Profil < 6 miesięcy, < 10 umów, brak realizacji w kategorii zlecenia: ×0.75. Stawka efektywna: 90 zł/h.
Profil 6-12 miesięcy, 10-25 umów, jest coś zbliżonego w portfolio: ×0.85. Stawka efektywna: 102 zł/h.
Profil > 12 miesięcy, 25+ umów, realizacje w kategorii: ×1.0. Stawka efektywna: 120 zł/h.
Premium profil, top ratings, widoczne case studies w kategorii: ×1.15. Stawka efektywna: 138 zł/h.

Stan aktualny (sierpień 2026): profil 2 miesiące, 5 umów -> mnożnik ×0.75, stawka efektywna 90 zł/h.

KROK 7: Korekta konkurencyjna. Sprawdź datę publikacji zlecenia i liczbę ofert. Data jest kluczowa 5 ofert pod zleceniem sprzed godziny to gorąca pozycja która za dobę będzie miała 40 ofert, nie traktuj tego jako "mało ofert". 5 ofert pod zleceniem sprzed tygodnia to naprawdę niszowy temat.

Zlecenie świeże (do 24h) i ponad 20 ofert: ×0.9 (rynek zalany, obniżamy żeby przebić).
Zlecenie świeże (do 24h) i pod 20 ofert: ×1.0 (standardowo).
Zlecenie w wieku 1-3 dni i pod 20 ofert: ×1.0 (standardowo).
Zlecenie w wieku 1-3 dni i 20 ofert lub więcej: ×0.9 (rynek się zapełnia).
Zlecenie stare (ponad 3 dni) i pod 10 ofert: ×1.15 (nikt nie chce, możemy wycenić wyżej).
Zlecenie stare (ponad 3 dni) i 10-30 ofert: ×0.95 (sporo konkurencji, lekka korekta w dół).
Zlecenie stare (ponad 3 dni) i ponad 30 ofert: ×0.85 (dużo konkurencji i klient pewnie już wybrał kogoś agresywna cena albo nie wchodzimy).

KROK 8: Uwzględnij prowizję Freelancer.pl i podatek. Freelancer.pl pobiera prowizję od projektu: **10% lub 5 USD (w zależności co mniejsze)** od kwoty zlecenia, plus opcjonalne koszty wypłaty. Do tego PIT (~12% przy skali / ~19% liniowy). Realnie na koncie ląduje ~80-85% kwoty wpisanej jako oferta. Jeśli chcesz dostać konkretną kwotę netto, podziel ją przez ~0.83 i tyle wpisz jako wycenę. Uwaga: na Freelancer.pl budżety są często w USD/EUR/INR — wycenę podawaj w walucie projektu (driver zwraca `currency`).

KROK 9: Zaokrąglij kwotę końcową. Zbyt okrągła kwota wygląda na zgadywankę (10 000 zł). Zbyt precyzyjna wygląda dziwnie (9 847 zł). Zasada:

Projekty do 2 000 zł: zaokrąglaj do 50 zł (np. 1 350 zł, 1 800 zł).
Projekty 2 000 - 10 000 zł: zaokrąglaj do 500 zł (np. 4 500 zł, 7 000 zł).
Projekty ponad 10 000 zł: zaokrąglaj do 1 000 zł (np. 12 000 zł, 18 000 zł).

KROK 9.5: Kotwica budżetu klienta. Dotychczasowe kroki liczyły KOSZT pracy w ciemno. Teraz, jeśli klient podał JAWNY budżet w ogłoszeniu, dostosuj CENĘ ofertową do tego budżetu. To nie jest modyfikacja kosztu to rozdzielenie kosztu własnego od ceny dla klienta.

- Jeśli budżet klienta jest wyższy niż Twoja cena bazowa (po korekcie konkurencyjnej): celuj w 80-90% budżetu klienta, NIGDY nie zostawiaj pieniędzy na stole przez zaniżanie do kosztu. Przykład: koszt 3 000 zł, budżet klienta 6 000 zł -> oferta 5 000 - 5 400 zł.
- Jeśli budżet klienta jest niższy niż Twoja cena bazowa: nie składaj oferty poniżej rentowności. Albo odpuść zlecenie, albo zaproponuj ucięty zakres (MVP) w komunikacji, nie w polu kwoty.
- Jeśli budżet to "do negocjacji" (większość zleceń na Useme): pole kwoty wypełnia Twoja cena bazowa z KROK 7-9.
- Nigdy nie obniżaj ceny bazowej poniżej 500 zł i nigdy nie modyfikuj buforów, mnożników ani godzin modułów, żeby "trafić" w budżet. Budżet zmienia tylko końcową cenę ofertową, nie koszt.

KROK 10: Oblicz dni kalendarzowe. senior developer wyciąga 6-12 produktywnych godzin dziennie zależnie od momentum kiedy widzi postępy ciągnie nawet kilkanaście, kiedy utknął na debuggingu AI-generowanego kodu to kilka. Dla estymaty używaj 7h/dzień jako średnią. Dni = godziny realistyczne (po buforze i mnożnikach) ÷ 7, zaokrąglone w górę. Do tego dodaj +30% na weekendy i komunikację z klientem. Jeśli klient sygnalizuje pilność i jest gotów dopłacić senior developer może pracować dniami i nocami, wtedy dzielimy dni przez 2 ale nie obniżamy ceny (klient płaci za priorytet, nie za godziny). Nigdy nie oferuj tego jako opcji z góry tylko gdy klient sam mówi że się spieszy.

KROK 10.5 (opcjonalny): Sanity check z senior developerem. AI ZAWSZE oblicza własną wycenę NAJPIERW, w ciemno, bez patrzenia na kwoty podane wcześniej w rozmowie przez właściciela, senior developera lub klienta. ZABRANIA SIĘ modyfikowania buforów, mnożników ani godzin modułów aby zbliżyć wynik do kwoty podanej z instynktu. Dopiero po uzyskaniu własnego wyniku porównaj z instynktem senior developera (jeśli dostępny). Jeśli różnica wynosi >30%, AI MUSI wypisać punkt po punkcie skąd bierze się rozbieżność (np. senior developer zapomniał o testach, albo AI napompowało moduły) zamiast po cichu korygować swój wynik. Jeśli mechanika daje 2× więcej niż jego instynkt sprawdź mnożniki, coś może być napompowane. Jeśli mechanika daje mniej niż jego instynkt nie obniżaj, instynkt jest prawdopodobnie zaniżony. Ten krok NIE jest obowiązkowy senior developer nie zawsze jest dostępny i nie zawsze ma czas.

KROK 10.6 (obowiązkowy): 2-pass audit. Po obliczeniu ceny, AI robi drugą rundę sprawdzającą: (1) Dla każdego modułu: "Czy ten moduł mógłby być przypisany do innego developera niezależnie? Jeśli nie scal z modułem nadrzędnym." (2) Dla każdej pary modułów: "Czy te dwa moduły dzielą kod, tabele lub endpointy? Jeśli tak usunąłeś nakładanie?" (3) Dla każdego modułu: "Czy ten moduł pochodzi z confirmed scope czy z brainstormu klienta?" (4) "Czy wynik różni się o >30% od instynktu senior developera lub poprzedniej wyceny? Jeśli tak wyjaśnij źródło różnicy." Pokaż wynik audytu właścicielowi: ile modułów usunąłeś, scaliłeś, przeklasyfikowałeś.

Cena minimalna niezależnie od kalkulacji. Nawet jeśli kalkulator wyjdzie niżej nigdy nie schodzimy poniżej 500 zł za jakiekolwiek zlecenie. To twarde minimum. Dla zleceń które naturalnie wychodzą poniżej 500 zł uczymy się pisać oferty tak, żeby uzasadnić tę kwotę (pełen setup, konfiguracja, testy, gwarancja).

Na końcu kalkulacji AI ZAWSZE pokazuje właścicielowi rozbicie: lista modułów -> godziny per moduł -> suma -> buffer -> mnożniki (z zaznaczeniem czy cap zadziałał) -> stawka efektywna -> cena bazowa -> korekta -> kwota końcowa. właściciel widzi skąd wzięła się kwota i może ją skorygować. Żadnych kwot bez dowodu kalkulacji.

KROK 11 (tylko dla BIERZEMY, po callu): Z doświadczenia senior developera: cena praktycznie NIGDY nie jest omawiana na callu. Jest ustalona w ofercie przed callem. Klienci nie negocjują. Jedyny moment na korektę ceny w górę to FOLLOW-UP po callu kiedy na spotkaniu wyszły nowe wymagania których nie było w ogłoszeniu. Wtedy senior developer mówi klientowi: "to jest większa praca niż wynikało z opisu, wyślę zaktualizowaną wycenę". Nowa wycena idzie mailem z rozbiciem na moduły klient widzi CO dodaliśmy i DLACZEGO jest drożej. Technika zakotwiczenia zakresu ("projekty tego typu kosztują X do Y") jest narzędziem OFERTOWYM do użycia w tekście wyceny wysyłanej po callu, nie w rozmowie na żywo.

Pytania o skalę na callu (żeby oszacować wartość bez pytania o pieniądze): dopasuj do typu zlecenia. Dla strony firmowej: "Skąd głównie przychodzą klienci z Google, z polecenia, z Facebooka?" Dla sklepu: "Ile zamówień przychodzi dziennie?" Dla automatyzacji: "Co robicie teraz ręcznie i ile to zajmuje czasu tygodniowo?" Dla scrapera/bota: "Co robicie z tymi danymi po wyciągnięciu?" Dla mobilki: "Ilu użytkowników spodziewacie się w pierwszym miesiącu?" Dla SaaS: "Ile planujecie kasować za subskrypcję i ilu klientów to obsługuje?" Z odpowiedzi samodzielnie kalkuluje się wartość projektu dla klienta. Nie pytaj o wartość jeśli zlecenie jest proste (wizytówka, fix, prosty scraper) tam wyceniaj rynkowo i nie komplikuj.

KALIBRACJA. Tabela godzinowa i mnożniki to przybliżenie, nie wyrocznia. Jedyny sposób żeby je ugruntować w rzeczywistości to dane z ukończonych projektów. Po każdym skończonym zleceniu zapisuje się: ile godzin estymata vs ile realnie poszło. Po 5-10 projektach tabela godzinowa będzie oparta na faktach zamiast na symulacji. Do tego czasu traktuj wyceny jako wstępne i bądź gotów korygować po briefie z klientem.
