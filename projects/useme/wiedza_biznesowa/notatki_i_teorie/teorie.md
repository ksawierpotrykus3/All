# Teorie

Wszystkie teorie w jednym miejscu. Status: `teoria` dopóki test nie potwierdzi lub nie obali.

Podział:
- teorie o klientach i ofertach
- teorie o metodzie (jak pracujemy, jak odkrywamy)

---

## TEORIE METODY

### Ludzie używają AI do oceniania ofert AI
- Status: teoria (metoda)
- Teza: przy 50+ ofertach zleceniodawcy wrzucają oferty do AI, żeby wybrało najlepsze. Oferta musi być zoptymalizowana pod ocenę AI.
- Konsekwencje: proste zdania, słowa kluczowe z opisu, bez ozdobników, jasna deklaracja, konkretne liczby.
- Jak testować: porównać konwersję ofert ludzkich vs AI-owych na tym samym typie klienta. Minimum 3 pary.
- Źródło: korekta użytkownika 2026-09-09

### Monolit może być optimum, a metodyka anty-monolitu może być błędna
- Status: teoria (metoda)
- Teza: dominująca strategia to baseline, nie optimum. Ale sama metodyka szukania lepszych strategii jest nieprzetestowana.
- Konsekwencje: możliwe, że nie da się rozbić oferty na komponenty, monolit jest optimum, błąd atrybucji nigdy nie wystąpi.
- Jak testować: 1) rozbić 3 oferty na 6 komponentów, 2) 5 prób kontr-strategii vs baseline, 3) 3 negatywy tłumaczone inną zmienną.
- Źródło: korekta użytkownika 2026-09-09

---

## TEORIE O KLIENTACH I OFERTACH

### Długość opisu nie zawsze koreluje z wielkością zakresu
- Status: teoria
- Źródło: analiza zleceń 143750 (Notion, 1 zdanie, duży CRM) i 143747 (SQL, 1 zdanie, infrastruktura)
- Data: 2026-09-08
- Powiązane: typ lakoniczny-minimalista
- Uwaga: jedno zdanie może kryć duży projekt; zawsze doprecyzować przed wyceną.

### Lakoniczność + "do negocjacji" = delegacja całości na wykonawcę
- Status: teoria
- Źródło: 143750 (Adam — Notion CRM), 143355 (Jacek — sklep zoo)
- Data: 2026-09-08
- Powiązane: typ lakoniczny-minimalista
- Uwaga: klient nie chce specyfikować, oczekuje, że wykonawca zgadnie zakres.

### Firma może pisać emocjonalnie i kreatywnie, nie tylko formalnie
- Status: teoria
- Źródło: 143916 (Perca — landing page, "porwie nas i klientów :)")
- Data: 2026-09-08
- Powiązane: typ firmowy-emocjonalny
- Uwaga: formalny ≠ firmowy; liczy się ton i oczekiwany efekt.

### Świadomy klient indywidualny potrafi mieć mentalność korporacyjną (twarde MUST HAVE)
- Status: teoria
- Źródło: 143994 (Aleksandra — Google Ads, "MUST HAVE!")
- Data: 2026-09-08
- Powiązane: typ swiadomy-wymagajacy
- Uwaga: osoba prywatna może stawiać warunki jak firma; odpowiedź musi być dopasowana do briefu.

### Ekspert-egzekucyjny nie chce edukacji, tylko wykonania z autonomią
- Status: teoria
- Źródło: 143665 (Michał — SEO Litwa), 144045 (kodiwo — WordPress)
- Data: 2026-09-08
- Powiązane: typ ekspert-egzekucyjny
- Uwaga: odrzuca półprodukty; proponować metodę i jakość, nie podstawy.

### Ogłoszenie o pracę bywa maskowane jako zlecenie freelancerskie
- Status: teoria
- Źródło: 143650 (Dialog Key), 143318 (Bruno Prusaczyk), 143767 (Aethon AI Labs)
- Data: 2026-09-08
- Powiązane: typ rekrutacyjny-pod-przykrywka
- Uwaga: link do zewnętrznego ATS lub sekcja "How to Apply" = rekrutacja, nie projekt.

### Ekspercki opis może iść w parze z rażąco zaniżonym budżetem
- Status: teoria
- Źródło: 143589 (MERN, 10k USD), 143318 (AI senior, $2000/mies.)
- Data: 2026-09-08
- Powiązane: typ spekulacyjny-niedopasowany-budzet
- Uwaga: im większy rozjazd wymagania/budżet, tym mniejsze szanse na realny projekt.

### Firma może stawiać twarde wymagania przy zerowej specyfikacji produktu
- Status: teoria
- Źródło: 143273 (KARTS DESIGN iOS), 143274 (KARTS DESIGN R&D)
- Data: 2026-09-08
- Powiązane: typ firmowy-wymagający, lakoniczny-minimalista
- Uwaga: referencje jako filtr wejścia, a sam projekt nieopisany — to selekcja, nie brief.

### Zlecenie wymagające fizycznej obecności tworzy osobny segment
- Status: teoria
- Źródło: 143823 (konfiguracja MikroTik, Łódź on-site)
- Data: 2026-09-08
- Powiązane: potencjalny typ lokalny-fizyczny-fix
- Uwaga: twarda lokalizacja + mała pula ofert = inna dynamika niż typowy fix zdalny.

### Startup szuka "partnera-lidera", nie wykonawcy
- Status: teoria
- Źródło: 143767 (Aethon AI Labs — "nie szukamy wykonawcy do prostego kodowania")
- Data: 2026-09-08
- Powiązane: typ ekspert-egzekucyjny, rekrutacyjny-pod-przykrywka
- Uwaga: milestone-based + wizja bez konkretów = ryzyko niestabilnych płatności.

### Rekrutera pod przykrywką rozpoznaje się po kombinacji 5 sygnałów
- Status: teoria
- Źródło: analiza 143650, 143318, 143767
- Data: 2026-09-08
- Powiązane: typ rekrutacyjny-pod-przykrywka
- Uwaga: 1 sygnał = podejrzenie, 2–3 = prawdopodobne, 4–5 = pewne.
- Sygnały:
  1. Cel to etat/kontrakt, nie projekt ("join our team", "hiring", miesięczna stawka)
  2. Link do zewnętrznego ATS/portalu (najsilniejszy)
  3. Struktura HR (Responsibilities, Qualifications, How to Apply)
  4. Wymagania jak do etatu (lata doświadczenia, must have)
  5. Ton rekrutera ("we're looking for", "you will be responsible for")

### Pośrednik na Useme: sygnały, zaniżanie budżetu, podwójna rola
- Status: teoria
- Źródło: 143698 (Fabian — "dla strony mojego klienta"), KARTS DESIGN (143507, 143275, 143548, 143562, 143652)
- Data: 2026-09-08
- Powiązane: typ spekulacyjny-niedopasowany-budzet, firmowy-wymagajacy
- Uwaga: zwroty "mój klient", "dla naszego klienta" = pośrednik szuka podwykonawcy, często z marżą w dół ceny. Firma designu bywa jednocześnie zleceniodawcą i wykonawcą. Wariant: pośrednik zaniża budżet, bo sam chce zarobić.

### Część "zleceń" to zbieranie wycen pod dofinansowanie lub przetarg
- Status: teoria
- Źródło: 143618 (ARR ARES), 143507 (KARTS), 143344 (patrykb)
- Data: 2026-09-08
- Powiązane: typ firmowy-wymagajacy
- Uwaga: formalny język urzędowy, prośba o wycenę modułową, brak budżetu = dokument do wniosku. Wariant: szczegółowy brief z pytaniem o wycenę modułową to zbieranie danych do przetargu.

### Duża liczba ofert przy ogólnikowym opisie = sondowanie ceny lub ankietyzacja rynku
- Status: teoria
- Źródło: 143308 (150 ofert), 143618 (103), 143562 (50), 143652 (48)
- Data: 2026-09-08
- Powiązane: lakoniczny-minimalista, indywidualny-mikro-budzet, firmowy-wymagajacy
- Uwaga: im prostsze zadanie i więcej ofert, tym większa presja na niską cenę. Przy 100+ ofertach to ankietyzacja rynku, nie realny projekt.

### "Możliwa dalsza współpraca" to często hak na obniżenie stawki
- Status: teoria
- Źródło: 143652 (Albert — shopify, "możliwa dalsza współpraca"), 143562
- Data: 2026-09-08
- Powiązane: lakoniczny-minimalista, indywidualny-mikro-budzet
- Uwaga: obietnica ciągłości bez konkretów = klasyczny mechanizm presji na niższą cenę teraz.

### "Dokończenie po kimś" to osobna kategoria ryzyka
- Status: teoria
- Źródło: 143548 (EVERWOOD — "co wymaga dokończenia", zaawansowana wtyczka)
- Data: 2026-09-08
- Powiązane: ekspert-egzekucyjny
- Uwaga: przejmowanie cudzego kodu bez repo/dokumentacji = ryzyko ukrytych błędów; wyceniaj z zapasem.







### Wysoki próg wejścia (przykładowy raport, referencje) to filtr jakości, nie zła wola
- Status: teoria
- Źródło: 143681 (przegląd techniczny — wymóg zanonimizowanego raportu), 143721 (enova — 2 referencje + pytanie techniczne)
- Data: 2026-09-08
- Powiązane: typ swiadomy-wymagajacy, ekspert-egzekucyjny
- Uwaga: to nie pułapka — ekspert chce sprawdzić warsztat przed oddaniem projektu.

### Edukacyjny-lękowy: motywacją jest uniknięcie katastrofy, nie produkt
- Status: teoria
- Cytat: "Wiec potrzebuje domenę skonfigurować aby mi skrzynki e-mail nie sparaliżowało."
- Interpretacja: prawdziwy priorytet to ciągłość skrzynek firmowych, nie strona; klient boi się zepsuć coś co działa — trzeba zarządzać lękiem, nie tylko technologią
- Dowody obserwacyjne: 1 oferta (143904)
- Źródło: subagent analiza 143904
- Data: 2026-09-08
- Powiązane: typ swiadomy-edukacyjny

### Lakoniczny-biznesowy: zna cel, nie zna mechanizmu — "chyba" otwiera pole
- Status: teoria
- Cytat: "Zlecę konfigurację przez API chyba."
- Interpretacja: klient zna nazwy narzędzi i efekt (transkrypcje→CRM), ale nie wie JAK; słowo "chyba" = otwarty na alternatywę no-code (n8n/Zapier), a nie na programowanie
- Dowody obserwacyjne: 1 oferta (143981)
- Źródło: subagent analiza 143981
- Data: 2026-09-08
- Powiązane: typ lakoniczny-minimalista

### Przejmowanie kodu AI: "Powstał w Lovable" = refaktoryzacja, nie rozwój
- Status: teoria
- Cytat: "System jest już zbudowany i działa. Powstał w Lovable, kod jest w React/TypeScript, backend oparty jest o Supabase."
- Interpretacja: kod generowany AI bywa niespójny i bez testów — pod "dalszym rozwojem" kryje się potrzeba refaktoryzacji; wyceniaj z zapasem na zrozumienie cudzego kodu
- Dowody obserwacyjne: 1 oferta (143861)
- Źródło: subagent analiza 143861
- Data: 2026-09-08
- Powiązane: typ ekspert-egzekucyjny, "dokończenie po kimś"

### Instytucjonalny-pilotażowy: konkretny budżet + szkolenie = pilotaż pod większy projekt
- Status: teoria
- Cytat: "Zlecenie obejmuje wdrożenie, testy, instrukcję oraz szkolenie prowadzących."
- Interpretacja: pełny cykl wdrożeniowy z dokumentacją i szkoleniem przy realistycznym budżecie sugeruje pilotaż — jeśli się sprawdzi, wróci z kolejnymi modułami
- Dowody obserwacyjne: 1 oferta (143924)
- Źródło: subagent analiza 143924
- Data: 2026-09-08
- Powiązane: typ swiadomy-wymagajacy

### Wewnętrzne wsparcie techniczne = zleceniodawca celowo zawęża odpowiedzialność wykonawcy
- Status: teoria
- Cytat: "my odpowiadamy za ogarnięcie integracji po stronie naszego CRM / Manago AI. Wykonawca tylko wysyła ustrukturyzowane dane."
- Interpretacja: klient ma własnych programistów i celowo odcina kosztowny zakres — to przygotowanie, ale i kontrola kosztów; wycenaj tylko to, co naprawdę do Ciebie należy
- Dowody obserwacyjne: 1 oferta (143287)
- Źródło: subagent analiza 143287
- Data: 2026-09-08
- Powiązane: typ swiadomy-wymagajacy

### Farmy treści AI pod SEO: ChatGPT do masowej generacji podstron
- Status: teoria
- Cytat: "opis każdej stacji do wprowadzenia poprzez API CHATGPT albo ręcznie" + "BLOG … automatycznie przerabiane teksty poprzez API CHATGPT"
- Interpretacja: nacisk na automatyczną generację treści pod tysiące podstron = farma treści pod SEO, nie realny serwis; ryzyko pracy przy projekcie o wątpliwej wartości
- Dowody obserwacyjne: 1 oferta (143289)
- Źródło: subagent analiza 143289
- Data: 2026-09-08
- Powiązane: typ spekulacyjny-niedopasowany-budzet

### "Umowa na część etatu" pod pozorem freelancera = fałszywe B2B
- Status: teoria
- Cytat: "rozliczenie przez Useme lub umowa na część etatu"
- Interpretacja: klient chce stałej dyspozycyjności i zaangażowania pracownika, ale bez ZUS/urlopów; to sygnał fałszywego B2B — wyceniaj czas dyspozycyjności, nie tylko zadania
- Dowody obserwacyjne: 1 oferta (143325)
- Źródło: subagent analiza 143325
- Data: 2026-09-08
- Powiązane: typ firmowy-wymagajacy, rekrutacyjny-pod-przykrywka

### Marketingowy wariant rekrutacyjny: emoji + "cykliczne zlecenia" bez konkretu
- Status: teoria
- Cytat: "Świetnie się składa" + "Cykliczne zlecenia… Projekty o różnej skali" + "Wymagane funkcje: W zależności od zlecenia"
- Interpretacja: to budowanie bazy wykonawców przez agencję, nie konkretne zlecenie; obietnice stałej pracy bez briefu przyciągają masowo, ale realne zlecenia mogą być niskomarżowe lub nigdy nie nadejść
- Dowody obserwacyjne: 1 oferta (143314)
- Źródło: subagent analiza 143314
- Data: 2026-09-08
- Powiązane: typ rekrutacyjny-pod-przykrywka

<!-- FORMAT WPISU:
### [Twierdzenie]
- Status: teoria
- Cytat: "dokładny fragment z oferty"
- Interpretacja: co z cytatu wynika
- Dowody obserwacyjne: N ofert (lista ID)
- Źródło: (AI / doświadczenie / zlecenie X)
- Data:
- Powiązane: typy, zlecenia
- Konflikt: (jeśli sprzeczne z innym wpisem — wskaż)
-->
