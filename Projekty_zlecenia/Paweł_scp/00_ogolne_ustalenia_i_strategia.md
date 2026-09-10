# 00 — Strategia projektu, audyt operacyjny i propozycje wartości (B2B SCP)

**Klient:** Paweł (SCP — surowce i wyroby gumowe / przemysłowe — `scp1.pl`)  
**Platforma:** IdoSell (IAI-Shop)  
**Zespół:** Maksymilian (Senior / rozmowy i strategia), Ksawier (Developer / realizacja techniczna)  
**Status:** Aktywny rejestr strategiczny + audyt techniczno-biznesowy live

---

## 1. Wytyczne od Seniora (Kontekst rozmowy)

### 📩 Wiadomość z czatu (wrzesień 2026):
> *„ale mozesz wsm ustalic jak chcesz znalezc cos fajnego co mozesz podniesc realnie im dochody albo ulatwic prace zmniejszajac straty a ja moge z nim na rozmowie to przedstawic tez”*

---

## 2. Głęboki audyt operacyjny i techniczny (Prześwietlenie sklepu `scp1.pl` i konkurencji `exvalos.cz`)

Zamiast zgadywać, prześwietliliśmy bezpośrednio kod sklepu [`scp1.pl`](https://scp1.pl), jego konfigurację nagłówków, stref dostaw oraz czeskiego konkurenta [`exvalos.cz`](https://e-shop.exvalos.cz/en/products/rubber-sheets/rubber-rolls-without-ply/sbr).

### 🔍 Kluczowe fakty i wykryte błędy operacyjne:

1. **Błąd w Rumunii to wierzchołek góry lodowej (Dziura w strefach IdoSell):**
   - W selektorze walut i krajów (`#menu_settings_country` na stronie głównej `scp1.pl`) sklep ma zahardkodowane **wyłącznie 4 kraje**: Polskę, Czechy, Słowację i Chorwację.
   - **Rumunii (`RO`) w ogóle nie ma na liście wyboru na froncie!**
   - Klient z Rumunii, wchodząc na stronę, widzi walutę PLN, a silnik IdoSell na podstawie geolokalizacji próbuje wymusić strefę, której nie ma w selektorze nagłówka. To wywołuje pętlę nadpisywania ciasteczek i odrzucanie waluty EUR. Każdy klient z Rumunii, Węgier czy Niemiec natychmiast rezygnuje z zakupu.

2. **Fizyka produktu: Zabójcza waga gumy a porzucenia koszyków:**
   - Guma techniczna (SBR/NBR) waży ok. $1.5 \text{ kg}$ na każdy $1 \text{ mm}$ grubości na $1 \text{ m}^2$.
   - Rolka płyty 3 mm ($1.2 \times 10 \text{ m} = 12 \text{ m}^2$) waży **~54 kg**. Rolka 10 mm waży **~180 kg**.
   - Firmy kurierskie (DPD, GLS, InPost) wożą paczki standardowe tylko do 31.5 kg. Ponad 80% asortymentu SCP to **ciężki ładunek paletowy (spedycja LTL: Raben, Schenker, Rohlig SUUS)**.
   - Obecny brak automatycznej kalkulacji paletowej dla rynków UE sprawia, że klienci widzą status „Koszt transportu do potwierdzenia”. W B2B ponad **70% takich koszyków jest bezpowrotnie porzucanych**, bo zaopatrzeniowiec fabryki nie będzie czekał 24h na telefon od Joanny.

3. **Chaos jednostek: `sztuka` vs `rolka` vs `m²`:**
   - Na `scp1.pl` towar sprzedawany jest w jednostce `szt.` (np. 87,40 zł / 1 szt. dla rozmiaru 0,2 x 10 m).
   - Zaopatrzeniowcy w przemyśle operują wyłącznie w **metry kwadratowe ($m^2$)** lub **metry bieżące (mb)**.
   - Klient musi ręcznie przeliczać powierzchnię rolki na kalkulatorze. Jeśli w nowym widoku listy B2B klient wpisze „2”, myśląc o $2 \text{ m}^2$, a IdoSell doda 2 rolki ($24 \text{ m}^2$), powstaje gigantyczny błąd, odmowa przyjęcia towaru i strata na kosztach transportu paletowego w obie strony!

4. **Brak Kart Technicznych (TDS / Atestów PZH) na karcie towaru:**
   - Żadna fabryka ani warsztat nie kupi gumy SBR/EPDM do zastosowań przemysłowych bez weryfikacji Karty Własności Fizyko-Mechanicznych (twardość ShA, odporność chemiczna, rozciągliwość).
   - Obecnie klient musi pisać maile do Joanny z prośbą o PDF. Każdy taki mail to 15 minut zmarnowanego czasu handlowca i opóźnienie decyzji zakupowej o 1-2 dni.

---

## 3. Kreatywne i bezpieczne dźwignie biznesowe (Dla Seniora na rozmowę z Pawłem)

### 💰 FILAR A: Realne podniesienie dochodów (Wzrost marży i wartości koszyka)

#### 0. ⭐ Fundament: Silnik wyceny transportu paletowego (LTL Pricing Engine)
* **Problem źródłowy:** ponad 70% koszyków B2B porzucanych, bo klient nie wie, ile zapłaci za transport ciężkiej rolki (54–180 kg). Status „Koszt transportu do potwierdzenia” zabija zakup.
* **Mechanizm:** Automatyczna wycena w koszyku wg progów wagowych palety — do 31,5 kg kurier, powyżej spedycja paletowa LTL — zintegrowana z przewoźnikiem (Raben/DSV/Geis/Rohlig SUUS) przez API.
* **Wartość dla Pawła:** Realnie zatrzymuje porzucenia koszyków B2B. „Optymalizator palety” (punkt 1) jest dodatkiem NA WIERZCHU tego silnika, a nie jego zamiennikiem.
* **Warunek wstępny:** kompletne dane wagowe produktów w IdoSell.
* **🔎 Rozróżnienie techniczne (krytyczne dla wyceny):** IdoSell wspiera **statyczne profile wagowe** (import stałej tabeli cen frachtu), ale NIE dynamiczne odpytywanie API spedytora w locie. Dwie ścieżki: (A) tania — import stałej tabeli strefowo-wagowej, jeśli Paweł ją ma; (B) droga — customowa integracja API live przez pośrednika. **Przed wyceną ustalić, czy Paweł ma stałe cenniki frachtu paletowego.**
* **Koszt nośnika palety (EPAL):** wymiana 1:1 w LTL międzynarodowym nie działa (brak zwrotu, zniszczone nośniki). Rekomendacja: refakturowanie palety jako pozycji (przejście własności na odbiorcę) lub paleta jednorazowa z kosztem wbudowanym w algorytm wyceny LTL. **ODRZUCONE:** pooling CHEP/LPR (wysokie progi, kary). Drenaż marży na utracie palet [kwota pusta w raporcie — DO WERYFIKACJI].

#### 1. „Optymalizator zapełnienia palety” (Pallet Freight Optimizer — Upsell w koszyku)
* **Mechanizm:** Transport paletowy do Czech, Słowacji czy Rumunii kosztuje ryczałtowo np. 350–500 zł za miejsce paletowe (do 800 kg). Jeśli klient wrzuci do koszyka 2 rolki (110 kg), płaci za całą paletę, a większość ładowności się marnuje.
* **Rozwiązanie:** Dynamiczny pasek w koszyku i na listingu:  
  *„Twoja paleta jest zapełniona w 15%. Masz jeszcze 690 kg wolnego miejsca bez ŻADNEJ dopłaty za transport! Dobierz klej montażowy, wykładzinę Molet lub kolejną rolkę.”*
* **Wartość dla Pawła:** Bezpośredni skok Średniej Wartości Koszyka (AOV). Klient B2B chętnie dokupuje towar na zapas, skoro transport ma już opłacony.

#### 2. Inteligentny konwerter wymiarów na liście B2B ($m^2 \leftrightarrow$ Rolka)
* **Mechanizm:** W nowym widoku wierszowym klient podaje zapotrzebowanie w metrach kwadratowych (np. potrzebuję $25 \text{ m}^2$).
* **Rozwiązanie:** Skrypt w czasie rzeczywistym podpowiada:  
  *„25 m² = 2 pełne rolki (24 m²) + niedobór 1 m². Rekomendujemy zakup 3 rolek (36 m²) z rabatem ilościowym -5%.”*
* **Wartość dla Pawła:** Eliminuje pomyłki przy zamawianiu, drastycznie ułatwia proces zakupowy inżynierom i zwiększa wolumen sprzedaży do pełnych belek.
* **⚠️ Ryzyko:** Bez zmiany modelu jednostek w IdoSell (szt. vs m²) konwerter może POGORSZYĆ błędy — klient wpisuje „2” myśląc o 2 m², a system doda 2 rolki (24 m²). Bezpieczniejsza alternatywa: MOQ / minimalne wielokrotności rolki u źródła.

#### 3. Bramka pobierania Kart Technicznych (Lead Magnet B2B)
* **Mechanizm:** Na listingu i karcie produktu umieszczamy przycisk: *„Pobierz Kartę Techniczną TDS i Atest PZH (PDF)”*.
* **Rozwiązanie:** Przed pobraniem prosimy o podanie NIP-u i adresu e-mail. System natychmiast wysyła PDF automatycznie, a dane kontrahenta trafiają do panelu IdoSell jako gorący lead handlowy dla zespołu sprzedaży SCP.
* **Wartość dla Pawła:** Uwolnienie Joanny od wysyłania plików oraz automatyczne budowanie bazy zaopatrzeniowców z przemysłu.

#### 4. Asymetria walutowa (USD/EUR/PLN) i bufor spreadu (IdoSell)
* **Pochodzenie surowca (Wyjaśnienie „wątku Indii”):** Na `scp1.pl` głównym producentem oferowanych płyt i wykładzin jest **Zenith Industrial Rubber Products Pvt. Ltd.** (globalny producent z Mumbaju w Indiach).
* **Kluczowe rozróżnienie strategiczne (Scenariusz A vs B):**
  * **Scenariusz A (Paweł to bezpośredni importer kontenerowy):** Sam kontraktuje towar w Mumbaju w USD, płaci fracht morski (czas tranzytu 6–8 tyg.) i dokonuje odprawy celnej w PL. Wtedy ryzyko kursowe USD/PLN i USD/EUR bezpośrednio zjada marżę.
  * **Scenariusz B (Paweł to lokalny hurtownik/dystrybutor):** Kupuje gumy marki Zenith od europejskiego przedstawiciela lub innego importera w Polsce na zwykłą fakturę w PLN/EUR. **Wtedy całe ryzyko celno-morskie i walutowe USD go NIE DOTYCZY.**
* **Rozwiązanie dla walut (Weryfikacja inżynierska):**
  * **ODRZUCONY SLOP:** Fantazje AI o „darmowych kontraktach Window Forward bez depozytu z fintechów w 3 dni” — żadna instytucja finansowa nie da linii skarbowej małemu MŚP bez blokowania depozytu zabezpieczającego (margin call) lub twardego ratingu.
  * **REALNE WDROŻENIE:** Naturalny hedging (pokrywanie faktur w EUR wpływami z eksportu w EUR), subkonta walutowe oraz **automatyczny bufor kursowy w IdoSell (+3–4% narzutu do tabeli NBP)** chroniący przed wahaniami kursów w trakcie realizacji zamówień.

---

### 🛡️ FILAR B: Zmniejszenie strat i ochrona marży (Podatki, Prawo, Logistyka)

#### 0. Bezgotówkowy VAT importowy — art. 33a ustawy o VAT (Tylko jeśli Paweł importuje z Indii)
* **Mechanizm (FAKT PRAWNY):** Rozliczenie VAT z importu bezgotówkowo bezpośrednio w deklaracji JPK_V7M zamiast fizycznej wpłaty 23% na konto urzędu celnego w terminie 10 dni (art. 33 ust. 4). Przy wartości kontenera uwalnia to dziesiątki tysięcy złotych żywej gotówki na 60–90 dni.
* **Haczyk agencji celnej (art. 33a ust. 8 ustawy o VAT):** Przedstawiciel celny odpowiada solidarnie z importerem za podatek. Agencje celne, bojąc się małych firm, często odmawiają procedury lub żądają kaucji finansowych/weksli.
* **Werdykt:** WDRÓŻ (jeśli Paweł sam importuje; wymaga oświadczeń na PUESC o braku zaległości; zero kosztów IT).

#### 1. Utrata nośników paletowych EPAL w międzynarodowym LTL (Cichy wyciek gotówki)
* **Mechanizm (FAKT LOGISTYCZNY):** W transgranicznej drobnicy LTL (Raben, Schenker, Rohlig SUUS do CZ, SK, RO, HU, DE) **przewoźnicy NIE wymieniają palet 1:1 na rozładunku**. Paleta EPAL zostaje u zagranicznego odbiorcy, a kierowca odjeżdża.
* **Wpływ na marżę:** Strata 30–45 zł netto na każdej wysłanej palecie certyfikowanej. Przy 50 wysyłkach miesięcznie to **1 500 – 2 250 zł czystej straty z marży**.
* **Rozwiązanie w IdoSell:** Dwie ścieżki: (A) wbudowanie kosztu taniej palety jednorazowej/przemysłowej (koszt ~15–20 zł) w algorytm wyceny spedycji paletowej; (B) automatyczne doliczanie palety EPAL jako pozycji fakturowanej w koszyku.
* **Werdykt:** WDRÓŻ (natychmiastowe zatrzymanie wycieku gotówki z magazynu).

#### 2. Klasyfikacja celna (CN 4008 vs 5906) i Wiążąca Informacja Taryfowa (WIT)
* **Zagrożenie:** Płyty gumowe lite podlegają pod kod CN 4008, ale płyty ze zbrojeniem tekstylnym (przekładane tkaniną) bywają kwalifikowane do Działu 59 (np. CN 5906). Błędna deklaracja agencji celnej grozi retrospektywnym domiarem różnicy cła i odsetek do 3 lat wstecz (art. 103 UKC) przy kontroli KAS.
* **Rozwiązanie:** Wystąpienie do Dyrektora KIS o Wiążącą Informację Taryfową (WIT) — procedura jest **całkowicie bezpłatna** i wiąże organy celne w całej UE przez 3 lata.
* **Werdykt:** WDRÓŻ (rekomendacja procesowa dla Pawła).

#### 3. Bezpieczeństwo WDT 0% (Wymóg dowodów doręczenia CMR / e-POD)
* **Zagrożenie podatkowe:** Zastosowanie stawki WDT 0% przy eksporcie do Czech, Słowacji czy Rumunii wymaga posiadania dowodów wywozu i doręczenia towaru do nabywcy (art. 42 ust. 1 pkt 2 ustawy o VAT). Brak podpisanego listu CMR lub statusu e-POD od Rabena skutkuje domiarem **23% polskiego VAT z kieszeni SCP**.
* **Rozwiązanie:** Wdrożenie procedury archiwizacji elektronicznych potwierdzeń doręczenia (e-POD) od operatorów LTL powiązanych z zamówieniami w IdoSell.

#### 4. Rejestracja opakowań transportowych ROP/EPR (Niemcy LUCID + klauzula VerpackG § 15)
* **Niemcy (VerpackG § 9 i § 15):** Bezwzględny obowiązek rejestracji w ZSVR (rejestr LUCID) od pierwszej wysłanej palety owiniętej stretchem do firmy w Niemczech (brak jakiegokolwiek progu de minimis). Rejestracja jest **całkowicie bezpłatna** (30 min). Brak wpisu = natychmiastowe ryzyko płatnych upomnień prawnych (**Abmahnung na 1 000 – 2 500 EUR**) od niemieckich kancelarii, kara administracyjna do 100 000 EUR i zakaz sprzedaży w DE.
* **Klauzula zwalniająca (§ 15 ust. 1 zd. 4 VerpackG):** Aby SCP nie musiało fizycznie odbierać zużytych palet z Niemiec, do niemieckiego regulaminu/OWS w IdoSell wprowadzamy klauzulę przenoszącą obowiązek zagospodarowania/utylizacji opakowań transportowych na niemieckiego odbiorcę przemysłowego.
* **Czechy (Zákon o obalech 477/2001 Sb., § 15a):** Weryfikacja progów tonażowych (300 kg opakowań rocznie, czyli ok. 12–15 palet) i formuły Incoterms (przy DAP/DDP obowiązek sprawozdawczy EKO-KOM). Monitorować wagę wysyłek.
* **Werdykt:** WDRÓŻ dla LUCID (obowiązkowa formalność 0 zł + klauzula w OWS), monitorować dla Czech.

#### 5. Pełne odblokowanie rynków eksportowych (Naprawa stref IdoSell)
* **Mechanizm:** Rozszerzenie selektora `#menu_settings_country` o Rumunię, Węgry, Niemcy wraz z walutą EUR i flagą `omit cookies`. Eliminacja błędu resetowania waluty na PLN.
* **Werdykt:** WDRÓŻ natychmiast (MVP).

#### 6. Automatyczna weryfikacja VIES w locie
* **Mechanizm:** Weryfikacja NIP UE w bazie VIES przed zatwierdzeniem koszyka z WDT 0%. Moduł natywny IdoSell z bezpiecznym fallbackiem (w razie awarii API VIES zamówienie trafia do ręcznej weryfikacji przez Joannę, koszyk nie jest porzucany).

#### 7. B2B One-Click Reorder
* **Mechanizm:** Błyskawiczne ponawianie zamówień na te same mieszanki gumowe w 15 sekund z panelu klienta.

#### 8. Świadectwa jakości wg PN-EN 10204 (Deklaracja 2.1 vs Atest 2.2 vs Świadectwo 3.1)
* **Rygor prawno-techniczny (FAKT):** Dystrybutor niebędący producentem **NIE MA PRAWA wystawiać świadectwa odbioru 3.1 na własnym papierze firmowym** bez badań odbiorczych partii w akredytowanej jednostce. Przepisywanie danych fabrycznych na druk SCP to poświadczenie nieprawdy (art. 271 k.k.) i ryzyko odrzucenia partii przez kontrolę jakości zakładów przemysłowych OEM.
* **Wdrożenie proceduralne:** SCP wystawia na własnym druku wyłącznie Deklarację zgodności 2.1 lub Atest 2.2 (z badań niespecyficznych). Jeżeli klient przemysłowy bezwzględnie wymaga dokumentu 3.1 — SCP przekazuje wyłącznie **oryginalny, nienaruszony atest 3.1 wytwórcy (Zenith Rubber)** powiązany z numerem partii.
* **Werdykt:** WDRÓŻ natychmiast (instrukcja dla Joanny; 0 zł kosztów IT, 100% ochrony prawnej).

#### 9. Klauzula bezpieczeństwa ATEX / strefy zagrożenia wybuchem (PN-EN IEC 60079-0)
* **Zagrożenie:** Zwykła guma nieprzewodząca stwarza ryzyko wyładowań elektrostatycznych w strefach wybuchowych (kopalnie, silosy zbożowe, lakiernie). W razie wypadku odpowiedzialność odszkodowawcza spada na dostawcę niesprecyzowanego materiału.
* **Rozwiązanie (Disclaimer prawny):** Wdrożenie na kartach TDS w IdoSell stałego zapisu: *„Materiał ogólnego przeznaczenia technicznego. Nieprzeznaczony do pracy w przestrzeniach zagrożonych wybuchem ATEX bez dedykowanych badań rezystywności skrośnej/powierzchniowej”*.
* **Werdykt:** WDRÓŻ (1 zdanie w szablonie IdoSell).

---

### 🧪 FILAR C — Wektory usług dodanych i weryfikacja deep research

#### 🟢 MOCNE I ZWERYFIKOWANE (Dodać do planu):

**1. ⭐ Paszport logistyczny rozładunku w checkout (Winda / Wózek / DMC / Rampa)**
* **Problem:** Rolka gumy waży 54–180 kg (paleta do 800 kg). Brak rampy lub wózka widłowego u odbiorcy w DE/CZ/RO skutkuje odmową rozładunku przez kierowcę LTL, karą za „pusty podjazd” (150–350 zł) i opłatą za ponowny podjazd autem z windą (65–110 zł). Jedna wpadka kasuje marżę z kilku zamówień.
* **Wdrożenie:** Pola/checkboxy w checkout IdoSell wymuszające deklarację: (1) Rampa/wózek widłowy, (2) Wymagana winda rozładunkowa (automatyczna dopłata), (3) Ograniczenia tonażowe dojazdu (>3.5t / >12t). **ABSOLUTNY PRIORYTET OPERACYJNY przy LTL.**

**2. Wycinanie uszczelek na wymiar (MRO) w outsourcingu ze śląskimi wycinarniami**
* **Problem:** Sprzedaż surowca w belkach daje niską marżę (15–20%). Gotowe uszczelki wycinane pod wymiar dla fabryk przynoszą marżę 50–70%.
* **KOREKTA INŻYNIERSKA (Odrzucenie slopu AI o automatycznym uploadzie DXF w koszyku):** Klienci nadsyłają uszkodzone pliki CAD (złe skale, otwarte węzły). Automatyczny upload do koszyka doprowadziłby do zniszczenia surowca i sporów o nesting/odpad.
* **Realne wdrożenie:** Prosty formularz B2B (Lead Magnet): *„Wycinamy uszczelki na wymiar pod Twój projekt — wgraj rysunek techniczny/PDF/DXF, wycena w 4h”*. Joanna przekazuje zapytanie do sprawdzonej wycinarni CNC/waterjet na Śląsku (Tychy, Katowice), dodaje 60–80% narzutu i wysyła ofertę. Zero CAPEX na maszyny.

**3. Baza badań REACH (WWA / SVHC) i atesty EN 10204 2.2 — Fosa rynkowa**
* **Mechanizm:** Tanie gumy z Azji często przekraczają unijne limity rakotwórczych WWA (<1 mg/kg wg załącznika XVII poz. 50 do REACH). Posiadanie sprawozdań z badań akredytowanych (np. SGS, Hamilton) oraz atestów 2.2 odcina „garażową” konkurencję importującą toksyczny surowiec i otwiera drzwi do dużych zakładów przemysłowych.

**4. Outlet końcówek belek (zamiast fikcyjnej „sprzedaży odpadu”)**
* **Mechanizm:** Pozostałości po docinaniu (końcówki belek 1–2 m) wystawiane w sklepie jako dedykowana kategoria *„Outlet / Końcówki magazynowe”* z rabatem -30–40% w celu natychmiastowego odzyskania zamrożonego kapitału.

**5. Quick Order Pad i Engineering Sample Box**
* Masowe wklejanie SKU do koszyka + płatne próbniki 10×10 cm z voucherem 100% na pierwsze zamówienie paletowe.

---

#### 🔴 ODRZUCONY SLOP I SAMOBÓJSTWA OPERACYJNE Z AUDYTÓW AI:

* ❌ **Odbiór odpadów gumowych od klientów w BDO (kod 07 02 80):** BEZWZGLĘDNIE ODRZUCIĆ. Magazynowanie cudzych odpadów wymaga zezwolenia na zbieranie odpadów, monitoringu wizyjnego magazynu online podpiętego pod WIOŚ (art. 25 ust. 6b ustawy o odpadach) i kaucji gwarancyjnych w urzędzie marszałkowskim. Samobójstwo dla małego dystrybutora.
* ❌ **Paczki ścinków/ażuru za 200 zł jako wibroizolacja:** ODRZUCIĆ. Hurtownia nie ma ażuru, bo nie prowadzi produkcji seryjnej, a nikt w e-commerce nie zapłaci 246 zł brutto za karton śmieci w cenie nowej płyty.
* ❌ **Kontrakty Light-VMI z 30% bezzwrotną zaliczką od fabryk:** ODRZUCIĆ. W relacjach przemysłowych to fabryki narzucają terminy płatności 60 dni po odbiorze transzy, a nie płacą zaliczki za trzymanie zapasu.
* ❌ **Procedura celna 4200 w Hamburgu/Rotterdamie:** ODRZUCIĆ dla dostaw na magazyn w Bieruniu. Wymaga kosztownego niemieckiego przedstawiciela fiskalnego i generuje kaucje. Właściwa ścieżka to tranzyt T1 do Polski i odprawa w PL z art. 33a.
* ❌ **Ewidencja starzenia wg ISO 2230 Cure Date na PZ/WZ:** ODRZUCIĆ JAKO PRIORYTET. Norma ISO 2230 ma zastosowanie w lotnictwie i militariach; w hurtowni płyt technicznych o szybkiej rotacji (2–4 miesiące) wymuszanie na magazynierach wpisywania kwartałów wulkanizacji i kodowanie tego w IdoSell to klasyczny akademicki overengineering i strata czasu.
* ❌ **Window Forward bez depozytu z fintechów w 3 dni:** ODRZUCIĆ. Marketingowa obietnica nierealna dla małego MŚP bez blokowania depozytu zabezpieczającego.

---

#### 🟡 WARUNKOWE:
* **Radar zamówień publicznych (API e-Zamówienia / TED):** Skrypt odpytujący darmowe API pod kody CPV 19510000-4 i 44425200-7 jest technicznie darmowy i prosty (pół dnia pracy), ale wymaga weryfikacji, czy spółka ma zasoby do przygotowania wadiów, JEDZ i ofert formalnych.

---

## 3a. Zaktualizowany ranking priorytetów wdrożenia

| # | Inicjatywa | Wpływ na marżę / ryzyko | Wykonalność (Senior + Dev) | Werdykt |
|---|---|---|---|---|
| 1 | **LTL Pricing Engine + Paszport rozładunku** | Kluczowy (zatrzymuje porzucenia i eliminuje kary 150–350 zł za pusty podjazd) | Średnia (konfiguracja IdoSell + checkboxy w JS) | **MVP — WDRÓŻ** |
| 2 | **Eksport CZ/SK/RO + Selektor walut EUR** | Natychmiastowy przychód (odblokowanie rynków ościennych) | Łatwa (naprawa stref i ciasteczek) | **MVP — WDRÓŻ** |
| 3 | **Weryfikacja VIES + reguły WDT 0%** | Ochrona przed 23% domiarem VAT | Łatwa (moduł IdoSell / proxy) | **MVP — WDRÓŻ** |
| 4 | **Rozliczenie nośników palet EPAL w LTL** | Zatrzymanie utraty 30–45 zł na każdej wysłanej palecie | Łatwa (palety jednorazowe lub pozycja w koszyku) | **WDRÓŻ** |
| 5 | **Formularz wyceny cięcia uszczelek (MRO)** | Skok marży z 18% na 60% w outsourcingu bez maszyn | Łatwa (formularz zapytania B2B, bez ryzyka CAD) | **WDRÓŻ** |
| 6 | **Bramka TDS / Badania REACH (WWA) / Atesty** | Budowa fosy jakościowej, odcięcie taniej konkurencji | Łatwa (upload PDF + lead magnet) | **WDRÓŻ** |
| 7 | **Optymalizator zapełnienia palety** | Upsell w koszyku (AOV w górę) | Średnia (po weryfikacji wag towarów) | **FAZA 2** |

---

### 📋 Kluczowe pytania rozstrzygające dla Seniora na rozmowę z Pawłem

1. **Źródło pochodzenia gumy (Kwestia fundamentalna):** Czy wyroby gumowe marki Zenith ściągacie sami w kontenerach morskich bezpośrednio z Indii, czy kupujecie je od oficjalnego dystrybutora w Polsce/Europie na zwykłą fakturę w PLN/EUR?
   * *(Jeśli w Polsce/UE — odrzucamy całe cło i procedurę 33a).*
   * *(Jeśli z Indii — natychmiast pytamy o odprawę z art. 33a VAT w JPK i kaucje agencji celnej).*
2. **Kary za rozładunek LTL:** Czy zdarzają się Wam faktury korygujące od Rabena/Schenwera za puste podjazdy lub wymuszone użycie windy rozładunkowej u klientów, którzy nie mieli wózka widłowego?
3. **Rozliczanie palet EPAL:** Jak obecnie rozliczacie palety wysyłane za granicę (CZ, SK, RO, DE)? Czy doliczacie koszt palety klientowi, czy przewoźnicy nie oddają nośników i spisujecie 40 zł na sztuce w straty?
4. **Rejestracja LUCID (Niemcy):** Czy spółka jest zarejestrowana w niemieckim rejestrze opakowań ZSVR LUCID dla wysyłek paletowych B2B, czy ryzykujecie kary do 100 tys. EUR i płatne wezwania Abmahnung przy wejściu do DE?
5. **Wystawianie atestów jakościowych (PN-EN 10204):** Jak obecnie wystawiacie dokumenty jakościowe fabrykom — czy przekazujecie oryginalne atesty 3.1 od Zenith Rubber, czy drukujecie własne dokumenty z logo SCP (co przy braku własnych badań grozi odrzuceniem partii i odpowiedzialnością karną)?
6. **Certyfikaty i badania REACH (WWA):** Czy posiadacie od producenta aktualne badania na brak rakotwórczych wielopierścieniowych węglowodorów aromatycznych (WWA poniżej 1 mg/kg) i atesty 2.2, którymi możemy odciąć konkurencję na sklepie?
7. **Cięcie uszczelek na wymiar:** Czy klienci pytają o gotowe uszczelki wycięte pod wymiar i czy macie zaprzyjaźnioną wycinarnię CNC/waterjet na Śląsku, której moglibyśmy podsyłać zlecenia z marżą 60%?

---

## 4. Scenariusz rozmowy dla Seniora (Maksymiliana) z Pawłem

Senior nie powinien mówić o „kodowaniu i skryptach”, lecz o **operacyjnych zyskach i unikaniu strat w firmie Pawła**:

> *„Paweł, wdrożyliśmy nowy widok listy i ogarniamy zgłoszenie z Rumunii. Ale zrobiliśmy głęboki audyt operacyjny Twojego sklepu i logistyki magazynowej:*  
> *1. **Eksport i waluty:** W selektorze nagłówka brakuje Rumunii, przez co klienci z zagranicy odbijają się od waluty PLN i uciekają. Odblokujemy to etapami (CZ, SK, RO) z walutą EUR i weryfikacją VIES, żebyś miał 100% spokoju podatkowego przy WDT 0%.*  
> *2. **Logistyka ciężkich palet:** Sprzedajesz rolki po 100–180 kg. Jeśli kurier LTL przyjedzie do klienta w Czechach czy Niemczech, a tam nie ma wózka ani rampy, dostajesz karę 200–300 zł za pusty podjazd, która kasuje marżę z zamówienia. Wprowadzamy w checkout obowiązkowy paszport rozładunku (wózek/rampa/winda), który zabezpiecza Cię przed takimi obciążeniami.*  
> *3. **Utrata palet EPAL:** Spedytorzy LTL nie oddają palet 1:1 za granicą — tracisz 40 zł na każdej wysłanej belce. Wprowadzamy w kalkulatorze tanią paletę przemysłową lub refakturowanie nośnika.*  
> *4. **Wycinanie uszczelek (MRO):** Zamiast sprzedawać tylko surową gumę z marżą 18%, możemy odpalić prosty formularz zapytań o gotowe uszczelki wycinane pod rysunek klienta u kooperantów z Tychów/Katowic z marżą 60% bez kupowania przez Ciebie żadnych maszyn.”*

---

## 5. Indeks powiązanych dokumentów

- [`00_ogolne_ustalenia_i_strategia.md`](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Pawe%C5%82_scp/00_ogolne_ustalenia_i_strategia.md) — Audyt operacyjny, wytyczne seniora, propozycje wartości.
- [`01_zlecenie_rozmowa.md`](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Pawe%C5%82_scp/01_zlecenie_rozmowa.md) — Zlecenie 1: Sprzedaż CZ/SK, blokada detalu, stawki WDT 0%.
- [`02_zlecenie_nowe_zadania.md`](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Pawe%C5%82_scp/02_zlecenie_nowe_zadania.md) — Zlecenie 2: Widok listy B2B, prezentacja 3 cen UX, proforma w mailu, błędy z Rumunii.

