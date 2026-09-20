# PROJEKT — pomysły AI, technologie, decyzje odrzucone

> To materiał, NIE ustalenia użytkownika. Nic tu nie jest wybrane ani zatwierdzone.

﻿# Propozycja Architektury i Stacku Technologicznego: Magazyn

> [!NOTE]
> **Status:** Wstępna koncepcja architektoniczna (Draft / Subject to change).  
> Zapisane jako punkt odniesienia do dalszych testów i planowania. Nic nie jest tu zabetonowane – wszystko może ulec zmianie w toku empirycznej weryfikacji.

> [!WARNING]
> **SEKCJE 1 i 2 (Przegląd Architektury, Nośnik Danych) — UWAGA.**
> To dało AI. Użytkownik tego nie rozumie i tego nie ustalał.
> Napisane jest tam słowo „Rozwiązanie:" — to słowo jest mylące, bo wygląda jak decyzja użytkownika, a nią nie jest.
> Zlecenie użytkownika 1:1: „dopisz tam ze to Ai dalo i ja tego nie rozumiem do tego pliku".

## SPIS SEKCJI + STATUS

| Sekcja | Tytul | Status |
|--------|-------|--------|
| 1-3, 5 | Architektura / Nosnik / Orkiestrator / Nauka | POMYSL AI, przedwczesne - NIE budowac |
| 4 | Dwa Tryby Pracy | POMYSL AI, czesciowo |
| 6 | Korekty do Stacka | KOREKTY UZYTKOWNIKA |
| 7 | Wymagania wobec Danych | USTALENIE UZYTKOWNIKA |
| 9-10 | Co istnieje na swiecie / badania | ROZEZNANIE, nie wybor |
| 11 | Tryb Porzadkowania (lineage) | POMYSL, czesciowo PRZYJETY |

> Dla czytajacego AI: sekcje 1-5 to przedwczesny stack - czytaj, NIE buduj. Sekcje 6-11 wartosciowe.

---

## 1. Przegląd Architektury Systemu

```mermaid
graph TD
    User["Użytkownik (1 proste pole wpisu / Enter)"] -->|Atomowa myśl LUB Zadanie| Core["Główny Silnik: Python Agent Runner"]
    
    Core -->|1. Wymienny model LLM| LLM["projects/deep (Lokalne darmowe AI) <br/> opcjonalnie: Claude / GPT API"]
    Core -->|2. Wyszukiwanie hybrydowe (Bez ślepych wektorów)| Search["SQLite FTS5 (Pełnotekstowe) + Ripgrep (rg)"]
    Core -->|3. Tool Calling / Selektywny dostęp| Storage["Magazyn Danych (Dwie Warstwy)"]
    
    subgraph Storage["Magazyn Danych"]
        subgraph TopLayer["Warstwa Wierzchnia (Esencja)"]
            Atoms["atomy.jsonl (1 linijka = 1 atomowy byt)"]
            Wnioski["tablica_wnioskow.md (swobodne wnioski)"]
            Skills["skills/ (gotowe łańcuchy i procedury AI)"]
        end
        
        subgraph DeepLayer["Głęboka Warstwa Surowa (Niewidoczna dla użytkownika)"]
            PDFs["surowe/pdf/ (preprinty naukowe, artykuły)"]
            Images["surowe/obrazy/ (screeny błędów, zdjęcia)"]
            Failures["porazki/ (zlecenia i oferty ze statusem porażka)"]
            Learning["nauka/ (wygenerowane lekcje + co_umiem.md)"]
        end
    end
    
    Worker["Pobieracz w tle (Python Scraper)"] -->|Automatyczne zasilanie| PDFs
```

---

## 2. Nośnik Danych: Rozwiązanie problemu „Ani baza, ani dysk”

Użytkownik nienawidzi przeszukiwania folderów i czytania setek jednolitych plików `.md`. Sztywny SQL z kolei łamie się przy nowym typie myśli, a naiwne embeddingi wektorowe gubią twarde fakty (badanie *arXiv:2508.21038*).

### Rozwiązanie:
1. **Warstwa Wierzchnia (Atomy): `magazyn/atomy.jsonl`**
   - Format: JSON Lines. Każda linijka to niezależny atom (data, surowa treść, automatyczne tagi).
   - Niezwykle odporne na awarie, brak sztywnego schematu, zero barier przy wprowadzaniu nowych typów informacji.
2. **Indeks Błyskawiczny: `SQLite FTS5` + `Ripgrep (`rg`)`**
   - Pełnotekstowy indeks w SQLite (moduł FTS5 z algorytmem BM25) oraz narzędzie `ripgrep`.
   - Wyszukiwanie po twardych frazach, słowach kluczowych i parametrach w ułamku milisekundy.
   - Zero halucynacji związanych z wektorami – model widzi dokładne wystąpienia i linijki.
3. **Głęboka Warstwa Surowa (Binarne i Pełne Dane):**
   - `magazyn/surowe/pdf/` – oryginalne pobrane preprinty.
   - `magazyn/surowe/obrazy/` – zrzuty ekranu, błędy ze sklepów.
   - `magazyn/porazki/` – zlecenia z Useme oznaczone flagą `porażka` (AI samo robi ich autopsję).
   - `magazyn/nauka/` – wygenerowane lekcje oraz plik `co_umiem.md` (rejestr opanowanych zagadnień).

---

## 3. Główny AI (Centralny Orkiestrator z wymiennym modelem)

- **Środowisko:** Python 3.11+ działający lokalnie.
- **Niezależność od dostawcy (Wymienny model):**
  - Domyślnie spięty z lokalnym darmowym serwerem w `C:\Users\buchh\projects\deep` przez protokół OpenAI-compatible API.
  - Zmiana modelu na dowolny inny (Claude 3.5 Sonnet, GPT-4o, DeepSeek) wymaga edycji **jednej linijki** w konfiguracji środowiska.
- **Narzędzia Głównego AI (Tool Calls):**
  - `szukaj_w_magazynie(query)` – przeszukuje bazę atomów i indeks FTS5.
  - `czytaj_plik_gleboki(sciezka)` – nurkuje do surowego PDF-a (biblioteka `pypdf`/`pdfplumber`) lub analizuje obraz multimodalnie.
  - `dodaj_byt(tekst)` – atomowy zapis do `atomy.jsonl`.
  - `autopsja_porazki(oferta_id)` – analiza odrzuconej oferty i wyciągnięcie punktu awarii.
  - `zapisz_lekcje(tytul, tresc)` – archiwizacja lekcji i aktualizacja stanu wiedzy.

---

## 4. Dwa Tryby Pracy (Interakcja)

> [!CAUTION]
> **KOREKTA UŻYTKOWNIKA (2026-09-18) — ten punkt jest BŁĘDNY.**
> Użytkownik 1:1: „ALE TO NIE JEDNO POLE. to moze byc kurwa wszystko RODZIEL 1 to ze INPUT moze byc ROZNE Z 1000 INNYCH STRON. to jest najwazniejsze."
> Wejście to **nie jedno pole**. Wejściem może być **wszystko**, z **1000 różnych stron**. Może lądować: 1 linijka, 100, 1000, PDF-y, txt, md, pliki. Ma **nie szukać „1 linijki"**, tylko **wszystko, co jest potrzebne**.
> Szczegóły: `slownik.md`, sekcja „INPUT: NIE JEDNO POLE".

1. **Tryb Atomowy (Codzienność / Mikro-operacje):**
   - ~~Jedno pole wpisu~~ -> Wpisujesz myśl -> Wciskasz `Enter`.
   - Zero czatowania, zero pytań ze strony AI. Myśl zostaje cicho dopisana jako pojedynczy byt.
   - Jeśli wpis przeczy istniejącej regule – AI wskazuje konkretną linijkę, Ty dopisujesz 1 zdanie reakcji, a kolejna myśl rozstrzyga relację.
2. **Tryb Zadaniowy i Problemowy (Emergency):**
   - Wpisujesz cel (np. *„zwiększ konwersję ofert Useme”*) lub zgłaszasz awarię bota.
   - AI wyciąga przed Twoje oczy twarde zderzenie faktów (Twoje porażki vs cudze patenty z bazy).
   - Wszystkie wypracowane wnioski i warianty zostają **trwale zapisane na dysku**, a nie giną w ulotnym oknie przeglądarki.

---

## 5. Moduł Nauki i Automatyczny Pobieracz (Świat 2)

- **`pobieracz.py` (Background Worker):**
  - Skrypt działający autonomicznie w tle.
  - Zasysa najnowsze preprinty (arXiv, Europe PMC itp.) i posty tematyczne (Reddit).
  - Składa pliki PDF w głębokiej warstwie, a na wierzch wyrzuca tylko krótkie powiadomienie o nowym materiale.
- **Baza „Co już umiem” (`co_umiem.md`):**
  - Twardy rejestr opanowanych tematów, do którego AI zagląda przed wygenerowaniem każdej lekcji, aby nie powtarzać tego, co już znasz.

---

## 6. KOREKTY DO STACKA (z rozmowy 2026-09-13)

> Te punkty nadpisują / uzupełniają wcześniejszy draft. Zapisane 1:1 z reakcji użytkownika.

### Korekta 1: USUNĄĆ „jeden program, który siedzi i czeka"

**Cytat użytkownika:**
> „a mozna usunac punkt 1? bo np co mi po wpisach jak np nie bede mogl uzywac Ai gdzie indziej zeby sie poruszac po danych i je zmieniac"

- **Dane NIE MOGĄ należeć do jednego programu.** Mają leżeć w miejscu dostępnym dla AI **z dowolnego środowiska** (dziś IDE, docelowo apka).
- „1 program = silnik" wypada. Zastępuje go zasada: **dane są otwarte dla AI z każdego miejsca, nie zamknięte w jednej aplikacji.**
- Spójne z Wpisem 35 („ani baza, ani dysk").

### Korekta 2: INPUT to nie 1 linijka

**Cytat użytkownika:**
> „1 przyklad inputu to za mało"

- Wejście **nie może być sztywne** („1 linijka = 1 myśl").
- Wpadać może dowolna ilość / forma: elaborat, zrzut, kontekst, wiele bytów naraz.
- Input = **elastyczny**, nie jeden format.

### Korekta 3: „Szukanie po twardych słowach" — OTWARTE

**Cytat użytkownika:**
> „3. no tak ale jak i gdzie"

- Kierunek (hybryda zamiast wektorów) potwierdzony, ale **jak i gdzie** — nierozpracowane.
- Zapisane jako **otwarty punkt**, nie rozstrzygnięty.

---

## 7. WYMAGANIA WOBEC DANYCH (materiał do wyboru stacka)

> Ustalenie użytkownika (2026-09-13): **treść (Useme, portfolio, studia) jest tylko przykładem — nie jest potrzebna do wyboru stacka.** Do wyboru stacka potrzebne są **możliwości operacji na danych**, nie ich zawartość.

**Cytat użytkownika (kontekst ustalenia):**
> „A. a po co to komu. kontekst ma byc taki ze to tylko przyklad tego ze istnieja dane ktore musa byc mieszczone gdzies. i dostepne dla Ai, do czytania, edytowania i tworzenia nowych rzeczy na podstawie danych
> co tez musi byc skladowane edytowalne. usuwalne itp
> reszta nie jest potrzebna do wyboru stacka”

### Lista wymagań (operacje na danych)

1. **Czytać** — AI
2. **Edytować** — AI
3. **Usuwać**
4. **Tworzyć nowe rzeczy** na podstawie danych
5. **Składować wszystko** (nic nie wypada)
6. **Oznaczać jako nieistotne bez usuwania** (skreślanie / git)
7. **Historia / cofanie** do wcześniejszych wersji
8. **Zejść głębiej** (wiele poziomów w dół — opcja, nie domyślnie)
9. **Zapis automatyczny** (rozmowy, pliki) — bez ręcznego exportu
10. **Dostęp z każdego miejsca** — dysk lokalny wystarczy, **bez chmury**; nie zamknięte w jednym programie
11. **Segregacja przez agentów** (nie przez użytkownika)
12. **Rozrost bez limitu**

### Esencja wymagań (cytaty użytkownika 1:1)

**Korekta punktu 10 (chmura niepotrzebna):**
> „10. jak cos to nie trzeba si bawic w chmurze. wystarczy ze na dysku jest”

**Podsumowanie użytkownika:**
> „chyba nie mam wiecej pomyslow. 
> najwazniejsze to wlasnie pelna wolnosc w skladowaniu, operacje na plikach i towrzenie
> i oczywicie PELNE wsparcie AI w tym.”

- **Najważniejsze:** pełna wolność w składowaniu + operacje na plikach + tworzenie.
- **I pełne wsparcie AI w tym.**
- **Chmura:** niepotrzebna. Wystarczy **lokalny dysk**.

### Kryteria dla przyszłego stacka i dynamika danych (ustalenia z 2026-09-20)

**Cytat użytkownika 1:1:**
> „1. to tylko przyklad. program zewnetrzny nie obejmuje wymyslania stacku tego projektul bo ja ogolnei tylko pisze zeby wymyslec stack potem z Ai. ten ounkt jest dla niego zbedny. chodzi tylko ze daje dane.
> 2. reguly ktorych nie mam ale moze bede mial jak stworze wlasnie AI z dostepem do tego miejsca i kaze mu chodzic
> 3. ten sam zespol co dostaje Daje daje output gdzies.  troche jak entropia. Ai moze dostawac dane. tak samo jak je wydzielac. zmieniac edytowac. 
> Potem kluczowe dla stacka jest jak najwieksza wydajnosc i moze jakies duperele dodatkowe.”

- **Programy zewnętrzne poza stackiem:** Dowolne programy ściągające (skrypty, pobieracze) są poza stackiem samego Magazynu – ich jedyną rolą jest wrzucanie surowych danych do środka.
- **Reguły o użytkowniku i stylu powstaną w działaniu:** Zostaną wypracowane, gdy AI dostanie dostęp do danych w magazynie i zacznie po nim „chodzić” i uczyć się wzorców.
- **Entropia / dynamika danych:** Zespoły AI pobierają dane, wydzielają z nich części, edytują, modyfikują i generują output. Dane krążą, a nie leżą martwe.
- **Główny wymóg techniczny pod wybór stacka:** **JAK NAJWIĘKSZA WYDAJNOŚĆ** (szybkość operacji, zero lagów przy dużej ilości danych, swobodne wydzielanie i modyfikacje).

---

## 9. ISTNIEJĄCE TECHNOLOGIE (sprawdzone w sieci 2026-09-13)

> ⚠️ **STATUS: POMYSŁ / PROPOZYCJA — NIE DEFINITYWNY STACK.**
> To tylko rozeznanie, co istnieje na świecie. Nic tu nie jest wybrane ani zabetonowane. (Oznaczenie dodane na wyraźne żądanie użytkownika, 2026-09-13.)

**Pytanie użytkownika 1:1 (kontekst):**
> „No tak glowny zrodlem wiedzy beda moje rozmowy z AI i one beda surowe w swoich wlasnych rubryczkach na rozmowy. i beda oznaczane dokladnie ktore rozmowy sa wykestraktowane. a ktore nie, a ktore tylko w tym miejscu i tym. bo nie trzeba odrazu calego, ale musu byc system oznaczania i zapsiwania zeby nastepne Ai wiedzialo o tym.  i nawet mozna by bylo wziac tylko 1 linijke zalozmy,
> zalozmy ze mozna by bylo miec system w ktorym NIE trzba odrazu segregowac ale informacje SAME przychodza do AI. gdy potrzebuje. tylko to tworzy koeljny burdel bo co potem jak Ai to wezmie? i nie chce czytac co sie stanie bo nawet nie wiadomo czy na to sie zdecydujemy. i nie wiem czy jest odpowiednie. znajdz informacje czy istnieje jakas dobra technologia, i znajdz ze nie istnieje i zobaczymy czy istneije czy nie
> i nie do konca rozumiem co napisales tam bo nie dales zadnego osadzenia w rzeczywistosci, kazales mi mysec w prozni o czyms o czym nie wiem i nie moge tego wyobrazic se”

**Pytania użytkownika:** czy istnieje technologia na (a) oznaczanie, które rozmowy są wyekstrahowane, które nie, a które tylko częściowo, oraz (b) system, w którym **nie trzeba segregować z góry**, a informacje **same przychodzą do AI, gdy potrzebne**?

**Odpowiedź: OBA ISTNIEJĄ** — jako nazwane wzorce i gotowe produkty.

### A. Surowy zapis + warstwa pochodna + znacznik, co przerobione = **Event Sourcing + CQRS**

- **Event Sourcing:** zamiast trzymać tylko aktualny stan, trzyma się **pełny strumień zdarzeń w append-only store**. Ten strumień jest **źródłem prawdy** („system of record"); stan odtwarza się przez „replay" (odtworzenie).
  - Źródło: [Microsoft — Event Sourcing pattern](https://learn.microsoft.com/azure/architecture/patterns/event-sourcing)
- **CQRS (Command Query Responsibility Segregation):** oddziela zapis od odczytu. Odczyt to **projekcje** („read models" / materialized views) — widoki liczone ze zdarzeń.
  - **Projekcja ma własny licznik pozycji (watermark)** — wie, do którego zdarzenia doszła.
  - **Projekcję można skasować i przeliczyć od zera** ze zdarzeń.
  - „Nie trzeba idealnie za pierwszym razem" = **właściwość konstrukcji**, nie ulga.
  - Źródło: [Event Sourcing & CQRS — projections and read models](https://www.techinterview.org/post/3233465463/system-design-event-sourcing/)
- **Odpowiedniki, które użytkownik zna:** **git** (untracked → staged → committed) oraz **księga bankowa** (saldo liczone z transakcji, nie zapisane osobno).
- **To już istnieje w świecie AI:** **Zep / Graphiti** — trzyma surowe wiadomości jako „**episodes**" („a non-lossy data store"), i **z nich** wyciąga fakty do grafu czasu. Czyli dokładnie: surowe rozmowy w swoich „rubryczkach" + warstwa pochodna.
  - Źródło: [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://blog.getzep.com/content/files/2025/01/ZEP__USING_KNOWLEDGE_GRAPHS_TO_POWER_LLM_AGENT_MEMORY_2025011700.pdf)
  - Zep rozwiązuje też problem sprzeczności: śledzi **okresy ważności faktów** („fact validity windows").

### B. Informacja przychodzi do AI na żądanie = **Agentic RAG**

- Standardowe RAG to sztywny pipeline (zapytanie → embedding → top-k → prompt). **Agentic RAG** to pętla: **agent sam decyduje, kiedy szukać, jak zawęzić i kiedy przestać.**
  - „an AI agent treats retrieval as a tool that it can invoke on demand" — [Microsoft — Develop an agentic RAG solution](https://learn.microsoft.com/azure/architecture/ai-ml/guide/rag/rag-agentic)
- **Gotowe produkty (open source, self-hostowalne):**
  - **Mem0** — extract + retrieve, wektory + encje (Apache 2.0)
  - **Zep / Graphiti** — temporalny graf wiedzy (Apache 2.0)
  - **Letta (d. MemGPT)** — pamięć „jak w systemie operacyjnym": agent sam edytuje pamięć (Apache 2.0)
  - **LangMem** — KV + wektory (MIT)
  - Źródło: [Best AI Agent Memory Providers 2026](https://www.developersdigest.tech/blog/best-ai-agent-memory-providers-2026)
- **Związane pojęcie:** **Context Engineering** (następca „prompt engineering") — dyscyplina decydowania, co wchodzi do kontekstu, kiedy i w jakiej formie.

### Obawy użytkownika — potwierdzone w danych (nie jest sam)

- **„Co potem, jak AI to weźmie?"** → w branży nazwane: „**Retrieval is close to solved; synthesis isn't**" — znalezienie właściwej informacji udaje się w 97%, ale poprawne **użycie** jej tylko w 87%.
- **Koszt:** pętle agentowe to **3–10× więcej tokenów** niż pipeline statyczny; zdublowanie kontekstu ≈ 4× dłuższe oczekiwanie.
- **Chaos przy zbyt dużym kontekście:** **Context Rot** (Chroma 2025) — im dłuższy kontekst, tym mniej równomiernie model z niego korzysta. Wszystkie 18 badanych modeli się degradowały.
- **Uwaga o benchmarkach:** w LoCoMo 6,4% klucza odpowiedzi było błędne, a sędzia LLM akceptował do 63% celowo błędnych odpowiedzi → liczbom od dostawców nie można ufać.

### Czego NIE MA (uczciwie)

- **Nie ma jednego gotowego produktu**, który robi dokładnie to, co opisuje użytkownik (surowe rozmowy + częściowe ekstrakcje z własną decyzją + agenci porządkujący + AI czytające dane z każdego miejsca + pełna wymienność modelu).
- **Istnieją klocki i wzorce.** Złożenie ich w jeden system = praca własna, nie gotowiec.

### Doprecyzowania użytkownika do sekcji 9 (1:1)

**Kontekst:** reakcja użytkownika na sekcję 9 (2026-09-13).

> „a zapisales moja cala wypowiedź? i wszystkie poprzednie poprawnie? 
> co do Ai. Ai mam darmowe narazie. chyba ze wezme ten drozszy to wtedy co? i context rot, I TAK zadania niektore moje wymagaja kontekstu  no nie da sie go skrocic bo wtedy nie odpowie dobrze wiec to juz nie wina technolii prawda? czy ja zle rozumiem nie jestem techniczny zbytnio. i oznacz ten pomysl jako tylko POMUYSL propozycja a nie definitywny stack”

- **Pytanie 1:** AI ma darmowe na razie. Jeśli weźmie droższy — to wtedy co?
- **Pytanie 2 (context rot):** niektóre jego zadania **wymagają kontekstu** i nie da się go skrócić, bo wtedy nie odpowie dobrze → **„to już nie wina technologii, prawda?"**
- **Polecenie:** oznaczyć ten pomysł jako **tylko POMYSŁ / propozycja**, a nie definitywny stack. *(zrobione — status w nagłówku sekcji 9)*
- **Pytanie 3:** czy cała jego wypowiedź i wszystkie poprzednie są zapisane poprawnie? *(BŁĄD AI: wypowiedź z pytaniem o technologię NIE została zapisana — uzupełnione 2026-09-13.)*

---

## 10. NAJNOWSZE (2025/2026) — przegląd badań

> ⚠️ **STATUS: POMYSŁ / ROZEZNANIE — NIE DEFINITYWNY STACK.** Nic nie jest wybrane. To tylko przegląd stanu świata.
> (Na żądanie użytkownika: „teraz mamy O WIELE LEPSZE MODELE. sprawdz w koncu jakie badania z 2026 roku i 25")

### Najbliżej wymagań użytkownika — **MemMachine** (marzec 2026)
- [arXiv:2604.053](https://arxiv.org/pdf/2604.04853v1) — „A Ground-Truth-Preserving Memory System for Personalized AI Agents".
- Architektura **zachowująca prawdę źródłową**: **przechowuje surowe epizody rozmów i minimalizuje rutynową ekstrakcję przez LLM**.
- Krytykuje Mem0/Zep/MemGPT: one polegają na LLM przy ekstrakcji, aktualizacji, agregacji i usuwaniu → **wysoki koszt, błędy z probabilistycznej ekstrakcji, kumulujące się błędy w czasie**.
- **~80% mniej tokenów wejściowych** niż Mem0.
- Kluczowe ustalenie: **optymalizacje na etapie odczytu dają więcej niż zmiany na etapie wchłaniania** (retrieval depth +4,2%, format kontekstu +2,0%, prompt wyszukiwania +1,8% — vs chunking zdań tylko +0,8%).

### **Chained Recursive Language Models** (sierpień 2026)
- [arXiv:2608.05124](https://arxiv.org/html/2608.05124v1) — dokładnie pomysł użytkownika „wiele chatów, jeden kontekst".
- Ten sam model wołany **wielokrotnie jako świeże korzenie rozumowania**. Każdy dostaje: pierwotny problem + kontekst + **zwarte streszczenie** + **czarną tablicę (plain-text blackboard)** + **trwałe artefakty zapisane przez poprzedników**.
- **Nie dziedziczy pełnej historii rozmowy.** Powód: dzielenie zadania na kawałki, żeby artefakty pośrednie mogły być sprawdzone i poprawione przez kolejne świeże wywołanie.

### **Sculptor** (ICLR 2026) — aktywne zarządzanie kontekstem
- [OpenReview](https://openreview.net/forum?id=HPeiH7da0Z) — model dostaje **odwracalne narzędzia** do własnej pracy pamięciowej: cięcie, składanie/streszczanie/przywracanie, precyzyjne szukanie.
- **Kluczowa diagnoza:** istniejące metody RAG/pamięci robią filtrowanie **nieodwracalne** — jeśli raz odrzucą informację „z początku nieistotną, a później kluczową", nie da się jej odzyskać. W wieloetapowym rozumowaniu to zabójcze.
- Nazywa też problem **interferencji proaktywnej**: stare/nieaktualne informacje w kontekście stale przeszkadzają.
- Wynik: 13B model z 39,4 → **73,8** średnio na długokontekstowych benchmarkach.

### **MindMemOS** (sierpień 2026) — samo-rozwijająca się warstwa pamięci
- [arXiv:2608.12428](https://arxiv.org/html/2608.12428v1), Noah's Ark Lab (Huawei). Open source.
- Porządkuje informacje strukturą **encja–właściwość–czas**.
- **„Dreaming"**: konsolidacja pamięci przez **scalanie redundantnych rekordów i rozwiązywanie konfliktów**.
- **Implicit corrective feedback** = sygnał human-in-the-loop do poprawiania błędnych wspomnień.
- **MindSkillEvolve**: zamienia trajektorie wykonania agenta w wielokrotnie używalne umiejętności.
- Wynik: 94,03% na LOCOMO.

### **O-Mem** (listopad 2025)
- [arXiv:2511.13593](https://arxiv.org/html/2511.13593v2) — krytyka istniejących systemów: grupują wiadomości po temacie **przed** wyszukiwaniem, przez co **pomijają informacje semantycznie niepasujące, ale krytyczne dla użytkownika** i wprowadzają szum.
- To wprost problem użytkownika: „przykład / dygresja, która może być ważna".

### Praktyka produkcyjna — „harness" (wrzesień 2026)
- [Context Engineering Inside The Harness](https://metaailabs.com/context-engineering-inside-the-harness-4-mechanisms-that-beat-context-overflow-and-goal-loss-on-long-horizon-tasks/)
- Konkretne, wdrożone progi:
  - Odpowiedź narzędzia **> 20 000 tokenów** → zapis na dysk + zwrot ścieżki i podglądu pierwszych 10 linii.
  - Gdy kontekst przekroczy **85% okna** → starsze wywołania narzędzi skracane do wskaźnika.
  - Claude Code: „auto memory" ograniczone do **pierwszych 200 linii / 25 KB**.
  - Podagent czyta 6 100 tokenów, oddaje **420 tokenów**; typowo streszczenie wraca w 1 000–2 000 tokenów.
- Ustalenie: **warstwa, która to naprawia, to nie model — to „uprząż" (harness)** wokół modelu.

### Przekrojowa synteza — dwa przeglądy
- [Memory in the Age of AI Agents: A Survey (arXiv 2512.13564)](https://arxiv.org/abs/2512.13564) — nowa taksonomia 3-wymiarowa: **trwałość / ziarnistość / operacja** (append-only vs insert/update/delete). Odrzuca podział „krótko-/długoterminowa" jako zbyt gruby.
- [Memory for Autonomous LLM Agents (arXiv 2603.07670)](https://arxiv.org/abs/2603.07670) — mocna teza: **różnica „z pamięcią" vs „bez pamięci" bywa większa niż różnica między samymi modelami.**

### Odpowiedź na pytanie „droższy model — co wtedy?"
- **Nowe modele nie usuwają context rot** — to własność architektury uwagi, nie błąd do wytrenowania. Skuteczny kontekst bywa **4–10× mniejszy** niż reklamowane okno.
- Co się zmienia wraz z nowszymi modelami: lepsze radzenie sobie z długim kontekstem, ale **nadchodzi to głównie z warstwy wokół modelu** (uprząż: offloading, kompaktowanie, podagenty), a nie z samego modelu.

### Kategorie arXiv pod samodzielne szukanie
- **cs.CL** (Computation and Language) — gdzie ląduje większość prac o pamięci agentów i kontekście.
- **cs.IR** (Information Retrieval) — wyszukiwanie, reranking, ruch odpytywania.
- **cs.AI** — agenci, architektury pamięci.
- **cs.HC** (Human-Computer Interaction) — interfejsy, ludzie w pętli.
- **cs.DB** (Databases) — trwałość, logi, event sourcing.
- **cs.SE** — narzędzia i inżynieria agentów.
- Najlepszy start dla tego projektu: **cs.CL + cs.IR**.

---

## 11. TRYB PORZĄDKOWANIA Z AI (pomysł — PO BASELINE)

> ⚠️ **STATUS: POMYSŁ PO BASELINE.** Nie do robienia teraz.

**Pytanie użytkownika 1:1:**
> „Okej co w sytuacji kiedy np robie porzadek z Ai i pisze cos z gory? tak jaj poprzednio dales mi punkty i mowie definitywnie jak to widze. chcialbym miec takie cos do robienia porzadkow ze mna jako pomysl po baseline. i chcialbym wiedziec jakby to moglo wygladac technicznie i prosto po ludzku”

**TAK — istnieje. Ma dwie nazwy.**

### Nazwa 1: **ADR — Architecture Decision Record** (zapis decyzji)

Wzorzec Michaela Nygarda (2011), standard branżowy. Struktura:
- **Status:** `Proposed` → `Accepted` → `Deprecated` → `Superseded by ADR-XXX`
- **Data**
- **Context** — jaka sytuacja, jakie ograniczenia. Pisane „dla kogoś, kto nie ma żadnego kontekstu — bo za 18 miesięcy tym kimś będziesz ty".
- **Decision** — konkretnie, bez ogródek.
- **Consequences** — co staje się łatwiejsze, co trudniejsze, jakie trade-offy przyjmujemy świadomie.
- **Options Considered** — jakie opcje rozważano, ich plusy/minusy i **dlaczego ich nie wybrano**. Branża nazywa to **najcenniejszą sekcją**, bo oszczędza ponowne roztrząsanie tej samej decyzji.

**Reguły twarde (kluczowe dla projektu):**
- **Niezmienny po zatwierdzeniu.** Przyjętego zapisu **nigdy się nie edytuje** — pisze się nowy, który go zastępuje.
- **Nie edytuj i nie usuwaj oryginału.** Historia decyzji jest cenna — **łącznie z tymi, które okazały się błędne**.
- Test, czy warto zapisać: **jeśli cofnięcie decyzji zajęłoby więcej niż sprint — warto.**

### Nazwa 2: **Human-in-the-Loop (HITL) — brama zatwierdzania**

Przepływ (6 kroków):
1. **Propose** — agent tworzy propozycję
2. **Check** — reguła decyduje, czy wymaga przeglądu
3. **Contextualise** — recenzent dostaje **dość, żeby zdecydować**: co agent chce zrobić, dlaczego, w czyim imieniu, jaki będzie skutek
4. **Decide** — zatwierdź / odrzuć / popraw / eskaluj
5. **Execute or stop** — system zapisuje decyzję, potem wykonuje albo blokuje
6. **Learn** — wynik zasila progi na przyszłość

**Reguła architektoniczna:** brama stoi **w ścieżce autoryzacji, nie w ścieżce wykonania**. Jeśli sprawdzenie dzieje się po akcji — to nie zatwierdzenie, tylko wpis w logu.
**Znanym słabym punktem jest „approval fatigue"** (zmęczenie zatwierdzaniem → klepanie na ślepo).
**Rozdzielenie ról:** **maker–checker** (twórca ≠ sprawdzający).

### Po ludzku — jak to wygląda

**Propozycja i decyzja to dwa osobne dokumenty.** Propozycji nie wolno ruszać. Decyzja to nowy zapis, który mówi: przyjmuję / odrzucam / zmieniam. Jeśli zmienisz zdanie za pół roku — nowy zapis mówi „zastępuje tamten, dlatego że...". **Nikt nie nadpisuje niczego.**

**Analogia 1 — umowa z aneksami.** Nie przepisujesz starej umowy. Podpisujesz aneks. Stara umowa leży.
**Analogia 2 — przegląd zmian w kodzie (PR).** Propozycja po jednej stronie, zatwierdzenie po drugiej. Oba zostają.
**Analogia 3 — git.** Historia, nie nadpisywanie.

### Czego brakuje w tym, co robiliśmy dzisiaj

- Dziś AI dawało punkty → użytkownik rozstrzygał → **zapisywana była tylko decyzja użytkownika**.
- **Brakuje zapisu samej propozycji AI.** Dlatego następne AI nie wie, **co było proponowane** i co zostało odrzucone.
- To jest dokładnie sekcja **„Options Considered"** z ADR — i dokładnie to, o co użytkownik prosił: „ze wziete to i to i temu".

### KOREKTA — czego ADR/HITL NIE oddaje (użytkownik: „nie rozumiem totalnie tego")

**Cytat użytkownika 1:1:**
> „nie rozumiem totalnie tego. wyjasnij mi ti na przykladzie zywym Z naszej rozmowy. chodzi o to ze ja pisze cos alboAi na oj temat. potem nastepny Ai albo ten sam mi to pisze a ja pisze dokladnie o co mi chodzilo i tak stopniowo POWINNO to tworzyc jakis jakis EFEKT. chodzi o to ze chce miec miejsce ktore ZAWSZE daje mi poczucie ze cos robie do przodu i to faktycznie robie bez myslenia gdzie to wszystko skladowac zapisywac itp i zeby cos sie tworzylo z tego jak myski w glowie, zapisz to iwyjasnij jeszcze raz albo zmien pomysly jesli nie oddaja tego co chce.”

**Czego brakowało:** ADR/HITL opisuje **dokument, który się czyta**. Użytkownik **nie czyta plików nigdy**. Więc połowa wzorca była nie na miejscu.

**Właściwy sens (z jego własnych słów — Wpis 22):**
> „musialbym zrobic kolejny proces ktory kompresuje z human in the loop czyli ze mna”

### SEDNO: pętla z AI w roli „odbijacza"

1. Użytkownik pisze coś (może być nie na temat, może być przykład).
2. AI **oddaje mu to z powrotem** — krótko, jednym zdaniem: „rozumiem tak: ...".
3. Użytkownik mówi: „nie, chodziło mi o..." albo „tak".
4. **Jego korekta zastępuje to, co AI zrozumiało.** Nie nadpisuje po cichu — staje się nową, właściwą wersją.
5. Następne AI dostaje już **wersję po korekcie**.

**Efekt:** z każdym obiegiem obraz użytkownika staje się ostrzejszy. On **nic nie zarządza** — tylko reaguje. Nie musi wiedzieć, gdzie to leży.

**Co się buduje:** nie „pliki", a **coraz ostrzejszy obraz jego samego** → mniej roboty dla niego, lepsze AI. (Jego „matematyka kontekstu".)

**Co z ADR zostaje:** zasada „nie nadpisuj, trzymaj stare wersje".
**Co z ADR wypada:** czytanie dokumentów przez użytkownika. On dostaje **jedno zdanie do reakcji**, nie dokument do lektury.

### ŻYWY PRZYKŁAD Z TEJ ROZMOWY (2026-09-13)

**Obrót 1**
- AI dało ocenę pomysłów użytkownika („mocne / ryzyka").
- Użytkownik: „nie teraz kurwa to tylko dane do wybrania stacka".
- → **Efekt:** AI przestało traktować rzeczy jako decyzje, zaczęło zbierać jako materiał.

**Obrót 2**
- AI dało listę 13 wymagań wobec AI.
- Użytkownik: „5. to jest tylko z 1 wymagan. mam dziesiatki takich pomyslow. to sa ekscesy ktore sie tworzy PO baseline".
- → **Efekt:** lista rozpadła się na **RDZEŃ (5 punktów)** i **EKSESY**. Realna zmiana konstrukcji.

**Obrót 3**
- Użytkownik: „oznacz ten pomysl jako tylko POMYSL propozycja a nie definitywny stack".
- → **Efekt:** każda sekcja w plikach dostała nagłówek **STATUS**.

**Obrót 4**
- AI dało „szufladki" (kategorie).
- Użytkownik: „nie lubie takich szufladek... Ai by kompresowalo i zle segregowalo".
- → **Efekt:** zmiana całego podejścia: zapis ma być **głupi** (bez kategorii), znaczenie liczone przy odczycie.

**Wniosek z przykładu:** trzy/cztery jego reakcje zmieniły realnie strukturę projektu. **To jest ten EFEKT.** Nie „notatka w pliku" — a **zmiana tego, jak system działa**, wywołana jego jednym zdaniem.

### KOREKTA MECHANIKI (AI się myliło)

**Cytat użytkownika 1:1:**
> „mechanika jest bledna. bo proces nie musi byc ten sam. mozna analizowac to co juz pisalem kiedyindziej. i nie trzeba 1 zdaniem.
> i jak wyglada ta korekta w systemie? w tej bazie danych dajmy w praktyce. powiedz mi i co sie potem z tym dzieje bo ot mial byc konkret bo z twojego nic nie zrozumialem. to czy czytam czy nie to musi byc”

**BŁĄD AI:** AI opisało **sztywną pętlę** (1 obieg, 1 zdanie, ten sam proces, zawsze w tej samej chwili). ŹLE.

**Poprawiona mechanika:**
- **Proces nie musi być ten sam.** Analiza nie musi dziać się od razu — można analizować **to, co użytkownik pisał kiedyś** (później, wsadowo, w dowolnym momencie).
- **Nie trzeba jednego zdania.** Może być dłużej, jeśli trzeba.
- **Stały jest tylko jeden niezmiennik:** korekta tworzy **NOWY zapis**, który **wskazuje** na to, co koryguje. Kształt procesu jest dowolny.
- **Zapis musi istnieć niezależnie od tego, czy użytkownik go przeczyta.** Jest dla następnego AI, nie dla jego lektury.

### PRAKTYKA: jak korekta wygląda w bazie

Zapis to jedna linia. Nic się nie edytuje — tylko dopisuje nowe linie. Każda nowa linia **wskazuje numer** linii, którą koryguje.

```
#001  2026-09-13 14:02   TY   "nie lubie takich szufladek. Ai by kompresowalo i zle segregowalo"
#002  2026-09-13 14:05   AI   "rozumiem: użytkownik nie chce kategorii w zapisie"
                              └─ odpowiedź na #001
#003  2026-09-13 14:11   TY   "nie o kategorie chodzi, tylko ze AI wtedy zle rozumie"
                              └─ korekta #002
#004  2026-09-13 14:20   AI   "zapis głupi (bez kategorii); znaczenie liczone przy odczycie"
                              └─ zastępuje #002, oparte na #003
```

**Co się potem dzieje z tym:**
- Gdy AI potrzebuje wiedzieć, co użytkownik myśli o składowaniu → czyta **#004 (najnowszy)**, nie #001–#003.
- Stare linie **zostają**, bo pokazują, **skąd to się wzięło** i co było odrzucone.
- Jeśli #004 okaże się błędne → AI nie edytuje #004. Dopisuje **#005**, które je koryguje. Historia rośnie w jedną stronę.
- **Nic nigdy nie jest kasowane i nic nie jest nadpisywane.**

**Dlaczego akurat tak:** bo żadna wersja nie jest „prawdziwa" na zawsze. Prawdziwa jest **najnowsza**, a wszystkie wcześniejsze są śladem, po którym można wrócić.

### KOREKTA 2 — model „łańcucha korekt" był za prosty

**Cytat użytkownika 1:1:**
> „no dobra ale co jak nie bedzie to taki system co jak w trakcie rozmowy z jarvisem po prostu on powie cos a ja powiem o co mi chodzilO ALBO samemu w polowie wiadomosci innej doprecyzuje cos albo powiem ogolnie. cokolwiek  to to tak nie moze dzialac bo to jest zbyt straight forward twoj sposob, jest glupi w zly sposob po prostu jest prosty i przewidywalny
> ale co dalej sie dzieje z takimi liniami? daje odppwiedz i co? jakis skrpt wykrywa moje odpowiedzi czy co?”

**BŁĄD AI:** model zakładał **jedną, sztywną ścieżkę**: jedno zdanie AI → jedna korekta użytkownika → gotowe. Rzeczywistość:
- doprecyzowanie może być **w środku innej wiadomości**,
- może być **kilka rzeczy naraz** w jednym zdaniu,
- może być **ogólnik** („często widzę, że..."), a nie korekta,
- może paść **przy okazji AI mówiącego o czymś innym**,
- albo **nie być wcale**.

**Poprawiony niezmiennik (to jest jedyne, co stałe):**
1. **Surowe linie zawsze kompletne.** Wszystko wchodzi, bez rozpoznawania i bez klasyfikowania w momencie zapisu.
2. **Linie pochodne zawsze jednorazowe.** Można je skasować i przeliczyć. Surowych nie rusza się nigdy.

Kształt procesu jest dowolny. Nie ma jednej ścieżki.

### KTO ROZPOZNAJE KOREKTĘ — żaden skrypt

**Odpowiedź wprost: nie ma żadnego skryptu.**

Skrypt (regex / słowa kluczowe) tego nie zrobi — bo **doprecyzowanie i dygresja wyglądają identycznie**. Liczby nie ma. Trzeba **zrozumieć zdanie w kontekście**. To potrafi tylko model AI, nie dopasowanie wzorca.

**Kiedy to się dzieje:** **nie w trakcie pisania, tylko obok** — jako osobna robota w tle. W branży nazywa się to **memory extraction**, a zasada brzmi: *„memory maintenance is a background job"* (utrzymanie pamięci to praca w tle, nie część rozmowy).

**Jak leci:**
1. Wszystko wpada jako surowe linie. Bez rozpoznawania. Ty piszesz cokolwiek, gdziekolwiek, jakkolwiek.
2. AI robi **obchód**: czyta nowe surowe linie i tworzy linie pochodne — „zrozumiałem: X", „użytkownik doprecyzował: Y" — każda ze wskazaniem na surową linię.
3. Jeśli AI **nie jest pewne** — pyta **raz**, jednym zdaniem: „miałeś na myśli X czy Y?". To jedyne miejsce, w którym wchodzisz.
4. Jeśli AI zrobi to źle — **linię pochodną się wyrzuca i przelicza od nowa**. Surowe zostają.

**Dlaczego wolno się mylić:** bo zepsucie dotyczy tylko warstwy, którą zawsze można policzyć na nowo. Dlatego AI nie musi trafić za pierwszym razem — i dlatego to może działać przy ludziach, którzy piszą nieprzewidywalnie.

### KOREKTA 3 — powiązania wiele-do-wielu, ZERO klasyfikacji

> ✅ **STATUS: PRZYJĘTE JAKO PUNKT STARTOWY.** Reakcja użytkownika (2026-09-13): „tak. idealnie na start".
> Dotyczy **mechanizmu powiązań** (lineage), nie wyboru stacka.

**Cytat użytkownika 1:1:**
> „to trzeba jakos wlasnie idealnie polaczyc zeby bylo widac jakie linie z danego ekstrakta sa wziete.  cytat orraz co Ai zrobilo z tym cytatem. zeby wlasnie nie bylo sztywnej klasyfikacji NIGDY. tylko 1 dobry mechanizm i dobry lancuch AI ktory robi to bezlblednie. ja moge nadzorowac tez. np wszystkie wyciagniecia  to sa oddzielne grupy ktore moge gdzies patrzyc jakbym zrobil se interfejs do tego
> bo 1 cytat nie musi sie rownac 1 notatka
> 1 notatka moze sie rownac  10 cytatom ktore sa dlugie albo pojedyncze.  to ma byc ekstremalnie elastycznie.  jak sam widzisz.
> dobrze mysle czy masz cos  lepszegoalbo doprecyzowanie? dodanie cokolwiek. oby nie skomplikowane i cos co moge zrozumiec i xzapisz moj cytat”

**Użytkownik myśli dobrze.** AI potwierdza. Poniżej nazwa i dwa doprecyzowania.

**Nazwa tego mechanizmu w branży: `lineage` / `provenance`** (pochodzenie danych) — śledzenie, **z czego co powstało**, gdy powiązań jest wiele.

**Doprecyzowanie 1: powiązań może być dowolnie wiele — w obie strony.**
- 1 cytat → 0, 1 lub 10 notatek.
- 1 notatka → 1, 5 lub 10 cytatów (długich albo pojedynczych).
- To **nie jest lista i nie jest drzewo** — to siatka. Nie ma „właściwej" liczby.
- Dlatego: **link zamiast kategorii.** Kategoria to zamknięta lista (zawsze za mała). Link nie wymaga żadnej listy — po prostu mówi „z tego".

**Doprecyzowanie 2: jedno twarde zabezpieczenie (proste).**
- **Każda linia pochodna MUSI mieć co najmniej jeden link do surowej.**
- Jeśli AI nie umie wskazać, z czego to wyciągnęło → **nie wolno jej zapisać.**
- To jedyne zabezpieczenie potrzebne. Nie ma żadnej klasyfikacji — jest tylko wymóg: **wiem, z czego to wzięte.**

**Dlaczego to jest lepsze niż typy relacji:** zamiast sztywnego „typ: korekta / wniosek / sprzeczność" — **jedno krótkie zdanie własnymi słowami** („zastępuje, bo tamto było o kategoriach, a chodzi o rozumienie"). Wolny tekst, żadnej listy do zamknięcia.

**Grupy / podglądy do nadzoru:**
- Wszystkie wyciągnięcia z danego ekstraktu = **osobny widok** liczony na żądanie.
- Widoki są **jednorazowe** — można je kasować i przeliczać, bo to nie dane.
- Użytkownik **może nadzorować, ale nie musi** — działają też bez jego patrzenia.

### KOREKTA 3a — ŻADNYCH limitów liczby + relacja: materiał → wycinki → pliki

**Cytat użytkownika 1:1:**
> „no ale nie moze byc 0 1 albo10 czy tam 5. moze byc 1 2 3 4 5 6 7 8 9 10 kurwa 200 nawet. 
> no ale ja widze tutaj podstawowa relacje
> Material bazowy -> wycinki/całóść -> pliki o tym tak jak np tworzysz stack na podstawie tego co pisze i badan dajmy  i mozna mieszac. jesli mozna”

**BŁĄD AI:** podanie „0, 1 albo 10" jako przykładu liczby powiązań — **sugerowało ograniczenie**. ŹLE.
- **Liczba powiązań jest nieograniczona.** Może być 1, 2, 3, 7, 10, **200**. Nie ma progu, nie ma sufit, nie ma „właściwej" liczby.
- Liczba jest tylko **liczbą wystąpień**, nigdy regułą.

**Relacja, którą widzi użytkownik (potwierdzona):**
```
Materiał bazowy  →  wycinki / całość  →  pliki o tym
(wszystko surowe)   (wycinki z surowego)  (opracowania, np. stack)
```
- Przykład: stack powstaje z tego, co użytkownik pisze **i** z badań — czyli z różnych materiałów naraz.
- **Można mieszać:** dowolny element może czerpać z dowolnego innego, także z pominięciem „poziomu" i z wielu źródeł jednocześnie.

**Doprecyzowanie AI (proste):**
- „Poziomy" to **nie sztywne trzy piętra** — to tylko **odległość od surowego**. Nic nie musi przechodzić przez środek.
- **Zasada zapisu:** linkuj do tego, czego **faktycznie użyłeś** — nie do wszystkiego, z czego to ostatecznie pochodzi.
- **Zasada bezpieczeństwa:** idąc po linkach w dół, **zawsze da się dojść do materiału bazowego**. Nic nie może wisieć w powietrzu.

---

## 12. OTWARTE PUNKTY — jedna lista (2026-09-13)

> Zbiorczo ze wszystkich plików. Podział na 4 koszyki: **nie wiem JAK** (techniczne), **nie wiem CO** (pojęciowe), **odroczone świadomie**, **docelowo**.
> AI posegregowało — użytkownik może przenieść dowolny punkt.

### A. Nie wiem JAK (techniczne — czekają na stack)

1. **Jak i gdzie AI ma szukać w danych.** Kierunek (hybryda zamiast wektorów) potwierdzony, sposób — nie. *(Korekta 3, sekcja 6)*
2. **Jak baza ma łapać rozmowy, gdy AI nie siedzi w Trae.** Użytkownik sam nie wie. *(slownik: „jak baza ma lapac rozmowy w trae?")*
3. **Jak wchodzić w interakcję z zespołami AI i gdzie.** „Nie widzę tego narazie". *(slownik: KONTROLA NAD AI)*
4. **Jak ma wyglądać to, co zapisane z ekstraktów czatu.** **Najważniejsza rzecz projektu** — i jeszcze niewiadoma. *(slownik: SKŁADOWANIE)*
5. **Techniczne wyglądy.** „nie wiem jakby to wygladalo technicznie" (głęboka warstwa, nie ładowanie wszystkiego naraz). *(slownik: pkt 4)*

### B. Nie wiem CO (pojęciowe — do rozstrzygnięcia z czasem)

6. **Co lepiej zapisać — całe badanie czy ekstrakt z czatu.** *(slownik: SKŁADOWANIE)*
7. **Co robić, gdy nie ma feedbacku albo jest odroczony** (np. oferty Useme). Brak konkretu. Pomysł: **wielu agentów dyskutujących**. *(slownik: brak feedbacku)*
8. **Jak dać agentom „nakurwianie" bez natychmiastowego feedbacku.** Nie nazwane. *(slownik: brak feedbacku)*
9. **„Skąd wiem, że poprawione tak jak chcę?"** — nadal nie widzi. *(slownik: JARVIS, pyt. 4)*
10. **GŁÓWNA ŚCIANA MENTALNA:** przejście od zebranych informacji do gotowego produktu. *(podsumowanie: pkt 1)*
11. **Jak fizycznie wygląda „to" w systemie** — „nie widze tego w moim systemie... ciezko mi sie to wyobrazic". *(slownik: SKŁADOWANIE, pkt 12)*

### C. Odroczone świadomie (użytkownik: „olejmy na razie")

12. ~~**Kto ma rację między zespołami** — nadzorca mówiący „nieprawda" vs ten, co tłumaczy.~~ **SCALONE z 13** *(2026-09-13)*
13. ~~**Co, gdy 2. AI zgłosi sprzeciw** (wizja studiów).~~ **SCALONE z 12** *(2026-09-13)*
14. **Nadzorca nad nadzorcą** — 1 monitoruje 2, 3 monitoruje 1 → pętla bez końca.

**12+13 (scalone) — Kto rozstrzyga, gdy dwa AI się nie zgadzają?**
Odpowiedź użytkownika (1:1): *„moze wchodzi 3 Ai i po prostu sprawdza kto ma racje i daje werdykt. najposciej,"*
→ **Trzecie AI sprawdza i daje werdykt.** Ten sam mechanizm dotyczy obu sytuacji: nadzorcy mówiącego „nieprawda" oraz sprzeciwu 2. AI.
→ Uwaga: **punkt 14 (nadzorca nad nadzorcą) to ten sam problem o poziom wyżej** — czy 3. AI też ma swojego sprawdzającego?

### D. Potwierdzone, ale docelowo (nie teraz)

15. **Wiedza użytkownika o tym, co AI ma załadowane jako kontekst.** Nie priorytet teraz, ale **stack nie może tego uniemożliwiać**. *Decyzja użytkownika: „DOCELOWO moze byc".*

---

## 13. ODPOWIEDZI NA OTWARTE PUNKTY (1:1, 2026-09-13)

**Cytat użytkownika 1:1 (całość):**
> „A.1 - w wielu miejscach to juz nie jest podmiot. ale na przyklad preprinty. posty z reddita. to nie jest potrzebne do stacka. 
> 2. jakbym mial kiedys miejsce ktore jest jak trae np czy antigravity to no chcialbym zeby to sie automatycznie robilo albo jak klikne idk wielej est sposobow napewno
> 3. tego nie wiem wlasnie, nie umiem se tego wyobrazic. wydaje mi sie ze Ai trzeba zakodowac itp interakcje a  dopiero jakbym chcial je zobaczyc to by musial zrobic ten interfejs. czyli nakladke na ten kod
> 4. surowo. no to co zapisze ma byc zapisane po prostu, nie wiem o co pytasz
> 5. idk naprawde wyglad to jest najciezsza rzecz i cos co bysmy musueli na koncu wymyslec 
> 6. to co potrzebne. surowe dane zawsze sa zapisywyane cale
> 7. Nie wiem. ale to juz jest zupelnie inny mechanizm przeciez nie mam stworzonych systemow ktore dochodza do celu jeszcze
> 8.  nie wiem
> 9. albo bym ufal albo bym sprawdzal jak dziala az bym zaufal
> 10. tez nie mam wizji dokladnej, nie dokladne pytanie
> 11. nei wiem. ani nie dokladne pytanie
> 12 nie rozuiem
> 13 tez nie wiem
> 14 nw
> 15. no to taki najdalszy moze”

**Status po odpowiedziach:**

| # | Punkt | Status |
|---|---|---|
| 1 | Jak/gdzie szukać | **NIE DOTYCZY STACKA** — „w wielu miejscach to już nie jest podmiot… preprinty, posty z reddita — to nie jest potrzebne do stacka" |
| 2 | Jak baza łapie rozmowy | **CZĘŚCIOWO** — „automatycznie… albo jak kliknę. Wiele jest sposobów na pewno" |
| 3 | Interakcja z zespołami AI | **CZĘŚCIOWO** — interakcje trzeba **zakodować**; interfejs = **nakładka na ten kod**, robiona dopiero gdy chce je zobaczyć |
| 4 | Jak wygląda to z ekstraktów czatu | ✅ **ZAMKNIĘTE: „surowo"** — ma być po prostu zapisane. *(AI zadało niezrozumiałe pytanie: „nie wiem o co pytasz")* |
| 5 | Techniczne wyglądy | **OTWARTE — na koniec.** „wygląd to jest najcięższa rzecz i co byśmy musieli na końcu wymyślić" |
| 6 | Całe badanie czy ekstrakt | ✅ **ZAMKNIĘTE:** „to co potrzebne. **surowe dane zawsze są zapisywane całe**" |
| 7 | Brak feedbacku | **OTWARTE** — „to już zupełnie inny mechanizm, przecież nie mam stworzonych systemów które dochodzą do celu jeszcze" |
| 8 | „Nakurwianie" bez feedbacku | **OTWARTE** — „nie wiem" |
| 9 | Skąd wiem, że poprawione dobrze | ✅ **ZAMKNIĘTE:** „albo bym ufał, albo bym sprawdzał jak działa, aż bym zaufał" |
| 10 | GŁÓWNA ŚCIANA | **OTWARTE** — „nie mam wizji dokładnej, **nie dokładne pytanie**" |
| 11 | Jak to fizycznie wygląda | **OTWARTE** — „nie wiem. **ani nie dokładne pytanie**" |
| 12 | Kto ma rację między zespołami | **NIEZROZUMIAŁE** — „nie rozumiem" *(punkt AI źle sformułowany)* |
| 13 | Sprzeciw 2. AI | **OTWARTE** — „też nie wiem" |
| 14 | Nadzorca nad nadzorcą | **OTWARTE** — „nw" |
| 15 | Wiedza o załadowanym kontekście | **POTWIERDZONE: najdalszy horyzont** |

**Uwaga AI (do poprawy):** punkty **4, 10, 11, 12** były sformułowane niejasno — użytkownik nie wiedział, o co pyta AI („nie wiem o co pytasz", „nie dokładne pytanie", „nie rozumiem"). To **punkt awarii po stronie AI**, nie użytkownika.**

### Uzupełnienie odpowiedzi (1:1)

> „1 i w wielu innych miejscach
> 12, nie wiem. moze wchodzi  3 Ai i po prostu sprawdza kto ma racje i daje werdykt. najposciej,”

- **Ad 1:** szukanie **nie jest podmiotem w wielu innych miejscach** — nie tylko preprinty/Reddit. (Nie jest sprawą stacka szerzej, niż zapisano.)
- **Ad 12 — rozwiązanie użytkownika:** **wchodzi 3. AI, sprawdza kto ma rację i daje werdykt.** „Najprościej." (Czyli: nie 2, a 3 — trzecie rozstrzyga.)

### PRZEREDAGOWANE PYTANIA 10 i 11 (poprzednie były za ogólne)

**Powód:** użytkownik nie wiedział, o co AI pyta („nie dokładne pytanie"). Poniżej wersje konkretne.

**→ 10 (nowe): „Czego ci brakuje: kroków czy miejsca?"**
Masz zebrane notatki, wnioski, badania. Z tego ma powstać **gotowa rzecz** — np. lepsza oferta, lekcja do nauki, nowy łańcuch AI.
Pytanie: gdy myślisz „nie umiem przejść od zebranych informacji do gotowego produktu" — brakuje ci:
- **(a) KROKÓW** — nie wiesz, co po czym ma się dziać,
- **(b) MIEJSCA** — nie wiesz, gdzie to zobaczysz, gdy będzie gotowe,
- **(c) jednego i drugiego**?

**→ 11 (nowe): „Co chciałbyś zobaczyć na ekranie?"**
Sytuacja: AI właśnie zapisało coś z twojej rozmowy.
Pytanie: **co chciałbyś zobaczyć na ekranie, żeby wiedzieć, że to jest?**
- jedno zdanie?
- krótką listę?
- **nic** — wystarczy, że istnieje i AI to ma?

### ODPOWIEDZI NA PRZEREDAGOWANE PYTANIA (1:1)

> „10. to i to i napewno cos jescze. sprobuj drazyc to glebiej moze cos mi sie przypomni 
> 11. wystarcyz ze istnieje  
> 3 Ai nie ma sprawdzajacego bo Ai zawsze znajdzie jakies ledy to moze isc w nieskonczonosc XD”

| # | Status |
|---|---|
| 10 | **CZĘŚCIOWO:** „to i to i na pewno coś jeszcze" — czyli **kroki + miejsce + coś jeszcze (nienazwane)**. Użytkownik prosi o **drążenie głębiej**, żeby coś sobie przypomniał. |
| 11 | ✅ **ZAMKNIĘTE:** „wystarczy że istnieje" — **nic nie musi być pokazane na ekranie.** |
| 12+13 | ✅ **ZAMKNIĘTE:** trzecie AI daje werdykt, i **nie ma swojego sprawdzającego** — bo „AI zawsze znajdzie jakieś lędy, to może iść w nieskończoność". |
| 14 | ✅ **ZAMKNIĘTE tym samym:** pętla nadzorców **kończy się na trzecim** — nie ma sprawdzającego nad sprawdzającym. Powód użytkownika: inaczej nieskończoność. |

### 10 — ODPOWIEDŹ (1:1): pętla danych → produkt → nowe dane

**Cytat użytkownika:**
> „no tego ze informacje sa rozne. produkty sa rozne i ciezko mi se wyobrzzic wszystko w glowie
> moge se 1 przyklad
> czyli dane to jak cos pisze. Ai robi cos z tym i tworzy produkt ktory sprawia ze np lepiej cos rozumiem. i sprawdza. potem nowe dane przychodza juz z nowa wiedza z produktu. i AI znowu sprawdza i tak w kolko az tego nie wylacze. a krok 6 jest dziwny bo nie umiem se go wyobrazic”

**Co użytkownik podał sam (jego własna pętla):**
```
DANE (to, co piszę)
   → AI robi coś z tym
   → PRODUKT (np. coś, co sprawia, że lepiej rozumiem)
   → AI sprawdza
   → nowe DANE (już z wiedzą z produktu)
   → AI znowu sprawdza
   → ... i tak w kółko, aż tego nie wyłączę
```
- **On kontroluje, kiedy pętla się zatrzymuje** („aż tego nie wyłączę").

**Kluczowe ustalenie — gdzie naprawdę jest ściana (10):**
- **Nie brakuje kroków ani miejsca.**
- **Ściana = „informacje są różne, produkty są różne, ciężko mi to sobie wyobrazić wszystko w głowie".**
- **Na 1 przykładzie idzie bez problemu.** Problem pojawia się, gdy ma objąć **wszystko naraz**.
- **Wniosek:** to jest dokładnie ta robota, po którą jest system — **on trzyma jeden przykład, system trzyma resztę.**
- **Krok 6 uznany za dziwny** przez użytkownika — „nie umiem se go wyobrazić". (Krok 6: „notatki wpadły wcześniej, gdy je pisałeś".)

---

## 8. WYMAGANIA WOBEC AI — uporządkowane (rdzeń vs ekscesy)

> Ustalenie użytkownika (2026-09-13): lista wymagań wobec AI została rozdzielona na **RDZEŃ (baseline)** i **EKScesy (do robienia PO fundamencie)**. Większość pierwotnych punktów to ekscesy, nie fundament.

**Cytat użytkownika (meta-uwaga):**
> „5. to jest tylko z 1 wymagan. mam dziesiatki takich pomyslow. to sa ekscesy ktore sie tworzy PO baseline jak sie stworzy ju fundament”

### RDZEŃ (baseline — minimum dla stacka)

**1. Wymienny model.**
Dziś darmowy z `projects/deep`, jutro lepszy — bez ruszania reszty.

**2. Dostęp do danych na życzenie — bez ładowania wszystkiego naraz.**
(pierwotne punkty 2 i 3 = to samo)

> „punkt 3 to to samo co punkt 2”

**3. Ma dostęp do danych — najważniejsze, że dane są tworzone i dobrze segregowane.**
(pierwotny punkt 10 = to samo co punkty 1–3)

> „10. to samo co pierwsze 3 punkty czyli ma dpstep do danych i najwazniejsze, te dane sa tworze i dobrze segregowane”

**4. Możliwość tworzenia (łańcuchy / agenci).**
Bez filozofowania pod stack.

> „4. MA MOZLIWOSC TWORZENIA ale no normalne ze jak bede uzywal Ai w IDE to moze kodowac wiec no tutaj duzo filozofii do stacku nie trzeba
> albo jak stworze swoje wlasne IDE”
> „11. to to samo co lancuchy tak tak”

*(pierwotny punkt 11 scalony z 4)*

**5. Pełna wolność „nakurwiania" AI.**
Ogólna zasada zastępująca pierwotne punkty 5 i 8.

> „8. to samo co 5, to tylko 1 z ekscesow Ai. ale ogolnie chodzi o pelna wolnosc nakurwiania AI.”

### WŁADZA NAD KOMPUTEREM I ZAPIS (zależne od środowiska)

**6. Władza nad komputerem — naturalna w IDE.**
> „6. naturlanie kazyd AI w IDE ma wladze nad komputerem chyba a moze w wlasnym moglbym cos doladowac wiecej”

**7. Automatyczny zapis rozmów — TYLKO we własnym IDE.**
> „7. tak jesli to rozmowa w wlasnym IDE. 
> bo nw jak tro zrobic np w trae. bardziej manualnuie chyba just export.”

- **Własne IDE:** zapis automatyczny — tak.
- **Trae (dziś):** trudne — raczej **manualnie / export**.

**KOREKTA UŻYTKOWNIKA (do „dostaję za darmo w IDE"):**
> „no i co do ide to dostaje za darmo tylko JARVISA.”
- W IDE użytkownik dostaje **za darmo tylko Jarvisa** (sam czat) — **nie** resztę możliwości.

### EKSESY (po baseline — nie teraz)

- **Nadzorcy / zespoły pilnujące roboty** (pierwotny punkt 5).
- **Pokazywanie sprzeczności z linijką** (pierwotny punkt 8) — eksces.
- **Sceptycyzm wobec tego, co widzi** (pierwotny punkt 9) — **to tylko treść promptu**, nie wymóg stacka. Użytkownik podał to „tak o se, bo się przypomniał".
- **„Nie traktuje wszystkiego jako prawda"** — treść promptu, nie stack.

> „9. to samo eksces. podalem to tylko tak o se bo se przypomnialem. to tylko tresc np promptu”

### SZCZEGÓŁY (nie wymagania stacka)

**12. Wielość chatów — doprecyzowanie, nie wymóg.**
Użytkownik używa AI z webu, które ma jeden kontekst (ten sam, dopóki go nie zmieni). Chodzi tylko o to, żeby AI nie myślało, że chce 1 miejsce na Jarvisa z nieskończonym kontekstem.

> „12. to tez jest juz szczegol zeby nie bylo tak ze AI bedzie myslalo ze chce 1 miejsce na jarvisa i  jarvis ma nieskonczony kontkest XD gdze w rzeczywistosic uzywam Ai z webu ktory ma tam 1 kontekst ten sam jesli nie zmienie”

**13. Osobny sektor (nie wymóg AI jako taki).**
Sektor, który pracowałby nad badaniem użytkownika albo pozwalał mu samemu pisać informacje podczas pracy — a wiedza o nim byłaby storowana w danych.

> „13. to juz bedzie inny sektor tego np ktory by pracowal nad badaniem mnie. albo pozwalalo by mi samemu pisac informacje podczas pracy itp i po prostu ta wiedza o mnie byla by storowana w danych”

---

# CZĘŚĆ B — POMYSŁY AI (NIE ustalone przez użytkownika)

> [!WARNING]
> To wszystko wymyśliło AI. Użytkownik tego NIE potwierdził, części nie rozumie. Zapisywane jako materiał do weryfikacji — NIE jako ustalenia. Zakaz przypisywania użytkownikowi autorstwa.

* ~~**1 Główny AI (Centralny Orkiestrator z wymiennym modelem)**~~ — jeden nadrzędny agent, selektywny dostęp przez tool calle, wymienny model pod spodem.
* ~~**Wielowarstwowość kompresji (głęboka warstwa na surowe dane)**~~ — surowe dane (PDF, zdjęcia, case studies) na głębszej warstwie, AI sięga na żądanie.
* ~~**Moduł Nauki (lekcje + baza umiejętności)**~~ — miejsce na lekcje, rejestr „co już umiem", składowanie preprintów.
* ~~**Autopsja porażek przez AI**~~ — użytkownik tylko oznacza „oferta → porażka", AI bada i wyciąga wnioski.
* ~~**Model Pracy Zadaniowej A (lokalne AI + trwała pamięć)**~~ — praca celowa i zadaniowa, wszystko trwale zapisane na dysku.
* ~~**Gotowe Łańcuchy AI (Skills / Procedury na żądanie)**~~ — wyspecjalizowane łańcuchy, które AI wywołuje samodzielnie.
* ~~**Dwa tryby interakcji:** (1) Atomowy — rzut myśli, cicha zmiana w pliku; (2) Problemowy — czat tylko do pożarów „tu i teraz".~~
* ~~**Zakaz uciekania do IDE** — wszystko w jednej aplikacji.~~
* ~~**Hybryda kosztowa (reguły + AI)** — tanie reguły/regexy gdzie się da, drogie AI tylko gdzie trzeba.~~

(Pełne rozwinięcie techniczne tych pomysłów — patrz `propozycja_architektury_i_stacka.md`. Ten plik jest oznaczony jako pomysł AI, nie stack.)

---

# CZĘŚĆ C — REJESTR SKREŚLONYCH (co odrzucone i dlaczego)

* ~~**Naiwne wyszukiwanie semantyczne (same embeddingi wektorowe)**~~
  > *Dlaczego:* (Wpis 36 + badanie „On the Theoretical Limitations of Embedding-Based Retrieval", 2025). Embeddingi gubią twarde fakty i relacje. Wyszukiwanie musi być hybrydowe.
* ~~**Zastępowanie surowych plików binarnych (PDF, zdjęcia) tekstem lub wektorami**~~
  > *Dlaczego:* (Wpis 36) Surowe dane muszą fizycznie istnieć na głębszej warstwie.
* ~~**Ręczne pisanie analiz porażek przez użytkownika**~~
  > *Dlaczego:* (Wpis 35) Zbędny narzut. Wystarczy `oferta -> porażka`, resztę robi AI.
* ~~**Ręczne przeszukiwanie folderów, plików i zdjęć przez użytkownika**~~
  > *Dlaczego:* (Wpis 35) Użytkownik nienawidzi szukania po katalogach.
* ~~**Sposób C: Wizualne klocki / karty obiektów z góry**~~
  > *Dlaczego:* (Wpis 34) Przekombinowane, sztuczne.
* ~~**Sposób B: Pytanie AI o stan rzeczy bez twardych dowodów**~~
  > *Dlaczego:* (Wpis 34) Brak oparcia w dowodach. Mózg potrzebuje widzieć dowód bez wysiłku.
* ~~**Mechanizmy automatycznego ożywiania myśli**~~
  > *Dlaczego:* (Wpis 33) Nietrafione i sztuczne.
* ~~**Zakładanie, że praca na danych = otwieranie i czytanie plików tekstowych**~~
  > *Dlaczego:* (Wpis 33) Pliki tekstowe wyglądają identycznie, nie chce się ich czytać.
* ~~**Przedwczesne decydowanie o formie fizycznej aplikacji (Alt+Spacja vs karta Chrome)**~~
  > *Dlaczego:* (Wpis 32) Pośpiech AI. Najpierw mechanika i przepływ informacji.
* ~~**Sztywne definiowanie liczby bytów (np. Triada)**~~
  > *Dlaczego:* (Wpis 32) Nie da się określić z góry. Atom = 1 byt, reszta otwarta.
* ~~**Dwupanelowy interfejs (Karta Myśli + Czat)**~~
  > *Dlaczego:* (Wpis 30) Odrzucone („fu nie"). Sztuczny interfejs.
* ~~**Dojrzewanie myśli przez wieloturowe debaty na czacie**~~
  > *Dlaczego:* (Wpis 30) Dojrzewanie = atomowe mikro-operacje, nie tasiemce.
* ~~**Wymóg uciekania do zewnętrznego IDE**~~
  > *Dlaczego:* (Wpis 29) Użytkownik nie chce przeskakiwać między programami.
* ~~**Goły czat jako główny interfejs aplikacji**~~
  > *Dlaczego:* (Wpis 29) Płaski czat = tasiemce i chaos.
* ~~**Zbyt krótkie podsumowania wniosków bez surowych danych źródłowych**~~
  > *Dlaczego:* (Wpis 28) Zbyt syntetyczny wyciąg jest niewiarygodny.
* ~~**Ograniczanie reaktywnego badania wyłącznie do bazy Reddit**~~
  > *Dlaczego:* (Wpis 28) AI musi móc szukać też w otwartym internecie.
* ~~**Ręczne raportowanie statusu prac przez użytkownika**~~
  > *Dlaczego:* (Wpis 27) Sztuczne. AI ma dostęp do danych. Użytkownik rzuca intuicję.
* ~~**Wrzucanie do jednego worka własnych działań i Reddita**~~
  > *Dlaczego:* (Wpis 27) To dwa różne światy. Łączą się dopiero reaktywnie (Świat 3).
* ~~**Wymuszanie natychmiastowego łączenia myśli w relacje**~~
  > *Dlaczego:* (Wpis 26) Mózg pracuje rozerwalnie. Najpierw wylądować, potem łączyć.
* ~~**Założenie, że zawsze istnieje gotowy Baseline**~~
  > *Dlaczego:* (Wpis 26) Na starcie nie ma baseline — wszystko to hipotezy.
* ~~**Sztywne formularze i sztuczne rubryczki**~~
  > *Dlaczego:* (Wpis 26) Zastąpione wolną tablicą „na już".
* ~~**Pospieszne nadpisywanie głównych szablonów przy każdej nowej teorii**~~
  > *Dlaczego:* (Wpis 25) 10 sprzecznych teorii wywróciłoby szablon. Szablon nienaruszony, teorie to równoległe warianty.
* ~~**Sztuczne pola przy teoriach (wagi %, pola 'wątpliwość'/'konsekwencja')**~~
  > *Dlaczego:* (Wpis 25) Akademicki narzut. Dla AI oczywiste z danych.
* ~~**Traktowanie wpisów jako zamkniętych notatek bez wejścia w głąb**~~
  > *Dlaczego:* (Wpis 24) Wpis musi mieć routing — AI wchodzi w surowe źródło, gdy trzeba.
* ~~**Uznanie 4-częściowej delty za uniwersalne „prawo kompresji"**~~
  > *Dlaczego:* (Wpis 21) Nadinterpretacja. To był 1 przykład.
* ~~**Budowanie kombajnu z 1000 parametrów**~~
  > *Dlaczego:* (Wpis 21) Zbędny narzut. Wiele rzeczy robi się oddzielnie w IDE.
* ~~**Teoretyczne odpytywanie o kompresję danych**~~
  > *Dlaczego:* (Wpis 19) Wymusza pamięć → pustka. Badać w działaniu na przykładach.
* ~~**Zapis wyłącznie RAW bez obróbki**~~
  > *Dlaczego:* (Komentarz / Wpis 18) Błąd AI. Użytkownik chce i surowe, i skompresowane.
* ~~**Zarządzanie botami (.bat, konsola)**~~
  > *Dlaczego:* (Wpis 16) Techniczne detale zależne od stacka. Dane ważniejsze.
* ~~**Projektowanie 3-kolumnowego dashboardu z góry**~~
  > *Dlaczego:* (Wpis 15) Pospiech AI. Interfejs narzucony przed zbadaniem danych.
* ~~**Strach przed fizycznym skasowaniem plików**~~
  > *Dlaczego:* (Wpis 17) Użytkownik się tego nie boi.
* ~~**Strach przed słabym modelem AI**~~
  > *Dlaczego:* (Wpis 17) Model w `projects/deep` wystarcza.
* ~~**Wybór sztywnej bazy SQL na początku**~~
  > *Dlaczego:* (Wpis 6) Sztywny stack rozsypie się przy pierwszej nietypowej myśli.
